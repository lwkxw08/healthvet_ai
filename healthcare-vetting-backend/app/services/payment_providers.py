"""
Payment Provider Service
Manages Stripe and GoCardless provider configuration, connectivity testing,
and payment processing. Admin configures providers and routing from the UI —
no hardcoded API keys.
"""
import json
import logging
from datetime import datetime, timezone
from typing import Optional
from app.database import get_db
from app.utils.auth import generate_id
from app.utils.encryption import encrypt_value, decrypt_value

logger = logging.getLogger(__name__)

# Provider capabilities — what each provider can do
PROVIDER_CAPABILITIES = {
    "stripe": {
        "display_name": "Stripe",
        "supports": [
            "credit_pack_purchase",
            "payg_invoice",
            "subscription_recurring",
            "refund",
        ],
        "payment_methods": ["card", "bank_transfer"],
        "description": "Card payments, subscriptions, and one-off invoices via Stripe Checkout.",
    },
    "gocardless": {
        "display_name": "GoCardless",
        "supports": [
            "direct_debit",
            "subscription_recurring",
            "payg_invoice",
            "refund",
        ],
        "payment_methods": ["direct_debit"],
        "description": "Direct Debit collections via GoCardless. Lower fees, ideal for recurring UK payments.",
    },
}


class PaymentProviderService:
    """Manages payment provider configuration and payment processing."""

    # ── Provider Configuration ────────────────────────────────────────

    @staticmethod
    def get_providers() -> list:
        """Get all configured payment providers with masked keys."""
        with get_db() as db:
            rows = db.execute(
                "SELECT * FROM payment_provider_config ORDER BY provider"
            ).fetchall()
            providers = []
            for row in rows:
                r = dict(row)
                caps = PROVIDER_CAPABILITIES.get(r["provider"], {})
                r["capabilities"] = caps.get("supports", [])
                r["payment_methods"] = caps.get("payment_methods", [])
                r["capability_description"] = caps.get("description", "")
                # Mask API keys
                r["api_key_masked"] = _mask_key(r.get("api_key_encrypted"))
                r["api_secret_masked"] = _mask_key(r.get("api_secret_encrypted"))
                del r["api_key_encrypted"]
                del r["api_secret_encrypted"]
                r["config"] = json.loads(r.get("config_json") or "{}")
                providers.append(r)
            return providers

    @staticmethod
    def get_provider(provider: str) -> Optional[dict]:
        """Get a single provider config (internal — includes decrypted keys)."""
        with get_db() as db:
            row = db.execute(
                "SELECT * FROM payment_provider_config WHERE provider=?",
                (provider,),
            ).fetchone()
            if not row:
                return None
            d = dict(row)
            d["api_key_encrypted"] = decrypt_value(d.get("api_key_encrypted") or "")
            d["api_secret_encrypted"] = decrypt_value(d.get("api_secret_encrypted") or "")
            d["webhook_secret"] = decrypt_value(d.get("webhook_secret") or "")
            return d

    @staticmethod
    def connect_provider(provider: str, api_key: str, api_secret: str = "",
                         webhook_secret: str = "", environment: str = "live") -> dict:
        """Connect a payment provider by saving API credentials and testing connectivity."""
        if provider not in PROVIDER_CAPABILITIES:
            raise ValueError(f"Unknown provider: {provider}. Supported: {', '.join(PROVIDER_CAPABILITIES.keys())}")

        now = datetime.now(timezone.utc).isoformat()

        # Test the connection before saving
        test_result = PaymentProviderService._test_provider_connection(
            provider, api_key, api_secret, environment
        )

        with get_db() as db:
            row = db.execute(
                "SELECT id FROM payment_provider_config WHERE provider=?", (provider,)
            ).fetchone()

            if row:
                db.execute(
                    """UPDATE payment_provider_config
                       SET api_key_encrypted=?, api_secret_encrypted=?, webhook_secret=?,
                           environment=?, api_key_set=1, is_enabled=?,
                           account_id=?, account_name=?,
                           last_tested_at=?, test_status=?,
                           connected_at=?, updated_at=?
                       WHERE provider=?""",
                    (encrypt_value(api_key), encrypt_value(api_secret), encrypt_value(webhook_secret),
                     environment, 1 if test_result["success"] else 0,
                     test_result.get("account_id", ""),
                     test_result.get("account_name", ""),
                     now, "ok" if test_result["success"] else test_result.get("error", "failed"),
                     now if test_result["success"] else None, now,
                     provider),
                )
            else:
                pid = generate_id()
                display_name = PROVIDER_CAPABILITIES[provider]["display_name"]
                db.execute(
                    """INSERT INTO payment_provider_config
                       (id, provider, display_name, api_key_encrypted, api_secret_encrypted,
                        webhook_secret, environment, api_key_set, is_enabled,
                        account_id, account_name,
                        last_tested_at, test_status, connected_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?)""",
                    (pid, provider, display_name, encrypt_value(api_key), encrypt_value(api_secret),
                     encrypt_value(webhook_secret), environment,
                     1 if test_result["success"] else 0,
                     test_result.get("account_id", ""),
                     test_result.get("account_name", ""),
                     now, "ok" if test_result["success"] else test_result.get("error", "failed"),
                     now if test_result["success"] else None, now),
                )

        return {
            "provider": provider,
            "connected": test_result["success"],
            "account_id": test_result.get("account_id"),
            "account_name": test_result.get("account_name"),
            "environment": environment,
            "message": test_result.get("message", ""),
        }

    @staticmethod
    def disconnect_provider(provider: str) -> dict:
        """Disconnect a payment provider (remove credentials)."""
        now = datetime.now(timezone.utc).isoformat()
        with get_db() as db:
            db.execute(
                """UPDATE payment_provider_config
                   SET api_key_encrypted=NULL, api_secret_encrypted=NULL,
                       webhook_secret=NULL, api_key_set=0, is_enabled=0,
                       account_id=NULL, account_name=NULL,
                       test_status=NULL, connected_at=NULL, updated_at=?
                   WHERE provider=?""",
                (now, provider),
            )
            # Remove this provider from any routing
            db.execute(
                "UPDATE payment_routing SET provider=NULL, updated_at=? WHERE provider=?",
                (now, provider),
            )
            db.execute(
                "UPDATE payment_routing SET fallback_provider=NULL, updated_at=? WHERE fallback_provider=?",
                (now, provider),
            )
        return {"provider": provider, "disconnected": True}

    @staticmethod
    def test_provider(provider: str) -> dict:
        """Test an already-connected provider's connectivity."""
        config = PaymentProviderService.get_provider(provider)
        if not config or not config.get("api_key_encrypted"):
            return {"success": False, "error": "Provider not configured — no API key set."}

        result = PaymentProviderService._test_provider_connection(
            provider,
            config["api_key_encrypted"],
            config.get("api_secret_encrypted") or "",
            config.get("environment", "live"),
        )

        now = datetime.now(timezone.utc).isoformat()
        with get_db() as db:
            db.execute(
                "UPDATE payment_provider_config SET last_tested_at=?, test_status=?, updated_at=? WHERE provider=?",
                (now, "ok" if result["success"] else result.get("error", "failed"), now, provider),
            )

        return result

    @staticmethod
    def _test_provider_connection(provider: str, api_key: str,
                                   api_secret: str, environment: str) -> dict:
        """Test connectivity to a payment provider."""
        if provider == "stripe":
            return PaymentProviderService._test_stripe(api_key, environment)
        elif provider == "gocardless":
            return PaymentProviderService._test_gocardless(api_key, environment)
        return {"success": False, "error": f"Unknown provider: {provider}"}

    @staticmethod
    def _test_stripe(api_key: str, environment: str) -> dict:
        """Test Stripe API connectivity."""
        try:
            import stripe
            stripe.api_key = api_key
            account = stripe.Account.retrieve()
            return {
                "success": True,
                "account_id": account.get("id", ""),
                "account_name": account.get("settings", {}).get("dashboard", {}).get("display_name")
                    or account.get("business_profile", {}).get("name")
                    or account.get("id", ""),
                "message": f"Connected to Stripe account: {account.get('id', '')}",
            }
        except Exception as e:
            error_msg = str(e)
            if "Invalid API Key" in error_msg or "authentication" in error_msg.lower():
                error_msg = "Invalid API key. Check your Stripe secret key."
            return {"success": False, "error": error_msg, "message": f"Stripe connection failed: {error_msg}"}

    @staticmethod
    def _test_gocardless(access_token: str, environment: str) -> dict:
        """Test GoCardless API connectivity."""
        try:
            import gocardless_pro
            env = "sandbox" if environment == "sandbox" else "live"
            client = gocardless_pro.Client(
                access_token=access_token,
                environment=env,
            )
            # List creditors to verify connectivity
            creditors = client.creditors.list(params={"limit": 1})
            creditor = creditors.records[0] if creditors.records else None
            account_name = creditor.name if creditor else "Unknown"
            account_id = creditor.id if creditor else ""
            return {
                "success": True,
                "account_id": account_id,
                "account_name": account_name,
                "message": f"Connected to GoCardless creditor: {account_name}",
            }
        except Exception as e:
            error_msg = str(e)
            if "unauthorized" in error_msg.lower() or "authentication" in error_msg.lower():
                error_msg = "Invalid access token. Check your GoCardless credentials."
            return {"success": False, "error": error_msg, "message": f"GoCardless connection failed: {error_msg}"}

    # ── Payment Routing ───────────────────────────────────────────────

    @staticmethod
    def get_routing() -> list:
        """Get all payment routing rules."""
        with get_db() as db:
            rows = db.execute(
                "SELECT * FROM payment_routing ORDER BY payment_type"
            ).fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def update_routing(payment_type: str, provider: Optional[str],
                       fallback_provider: Optional[str] = None) -> dict:
        """Update which provider handles a specific payment type."""
        now = datetime.now(timezone.utc).isoformat()

        # Validate providers exist and are enabled
        if provider:
            _validate_provider_enabled(provider)
        if fallback_provider:
            _validate_provider_enabled(fallback_provider)
        if provider and fallback_provider and provider == fallback_provider:
            raise ValueError("Primary and fallback provider cannot be the same.")

        with get_db() as db:
            row = db.execute(
                "SELECT * FROM payment_routing WHERE payment_type=?", (payment_type,)
            ).fetchone()
            if not row:
                raise ValueError(f"Payment type '{payment_type}' not found.")

            db.execute(
                "UPDATE payment_routing SET provider=?, fallback_provider=?, updated_at=? WHERE payment_type=?",
                (provider, fallback_provider, now, payment_type),
            )
            row = db.execute(
                "SELECT * FROM payment_routing WHERE payment_type=?", (payment_type,)
            ).fetchone()
            return dict(row)

    # ── Payment Processing ────────────────────────────────────────────

    @staticmethod
    def create_checkout(agency_id: str, invoice_id: str, amount: float,
                        payment_type: str, description: str,
                        success_url: str, cancel_url: str,
                        currency: str = "GBP") -> dict:
        """Create a payment checkout session using the configured provider for this payment type."""
        provider = _resolve_provider(payment_type)
        if not provider:
            raise ValueError(
                f"No payment provider configured for '{payment_type}'. "
                "Go to Settings → Payment Providers to connect and assign a provider."
            )

        config = PaymentProviderService.get_provider(provider)
        if not config or not config.get("api_key_encrypted"):
            raise ValueError(f"Provider '{provider}' has no API key configured.")

        now = datetime.now(timezone.utc).isoformat()
        txn_id = generate_id()

        if provider == "stripe":
            result = PaymentProviderService._stripe_create_checkout(
                config["api_key_encrypted"], amount, currency,
                description, success_url, cancel_url,
                metadata={"invoice_id": invoice_id, "agency_id": agency_id},
            )
        elif provider == "gocardless":
            result = PaymentProviderService._gocardless_create_payment(
                config["api_key_encrypted"], config.get("environment", "live"),
                amount, currency, description,
                metadata={"invoice_id": invoice_id, "agency_id": agency_id},
            )
        else:
            raise ValueError(f"Unsupported provider: {provider}")

        # Log transaction
        with get_db() as db:
            db.execute(
                """INSERT INTO payment_transactions
                   (id, agency_id, invoice_id, provider, payment_type, amount, currency,
                    status, provider_payment_id, provider_session_url, metadata_json, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (txn_id, agency_id, invoice_id, provider, payment_type, amount, currency,
                 result.get("status", "pending"),
                 result.get("payment_id", ""),
                 result.get("checkout_url", ""),
                 json.dumps(result.get("metadata", {})),
                 now),
            )

        return {
            "transaction_id": txn_id,
            "provider": provider,
            "checkout_url": result.get("checkout_url"),
            "payment_id": result.get("payment_id"),
            "status": result.get("status", "pending"),
        }

    @staticmethod
    def confirm_payment(provider: str, provider_payment_id: str) -> dict:
        """Confirm a payment has been completed (called from webhook or polling)."""
        now = datetime.now(timezone.utc).isoformat()
        with get_db() as db:
            txn = db.execute(
                "SELECT * FROM payment_transactions WHERE provider_payment_id=?",
                (provider_payment_id,),
            ).fetchone()
            if not txn:
                return {"confirmed": False, "error": "Transaction not found"}
            t = dict(txn)

            db.execute(
                "UPDATE payment_transactions SET status='completed', completed_at=? WHERE id=?",
                (now, t["id"]),
            )

            # Mark the invoice as paid
            if t.get("invoice_id"):
                db.execute(
                    "UPDATE invoices SET status='paid', paid_at=?, payment_method=?, stripe_payment_intent_id=? WHERE id=?",
                    (now, provider, provider_payment_id, t["invoice_id"]),
                )

            return {
                "confirmed": True,
                "transaction_id": t["id"],
                "invoice_id": t.get("invoice_id"),
                "amount": t["amount"],
            }

    @staticmethod
    def process_refund(transaction_id: str, amount: Optional[float] = None) -> dict:
        """Process a refund for a completed payment."""
        with get_db() as db:
            txn = db.execute(
                "SELECT * FROM payment_transactions WHERE id=? AND status='completed'",
                (transaction_id,),
            ).fetchone()
            if not txn:
                raise ValueError("Transaction not found or not completed.")
            t = dict(txn)

            config = PaymentProviderService.get_provider(t["provider"])
            if not config:
                raise ValueError(f"Provider '{t['provider']}' not configured.")

            refund_amount = amount or t["amount"]

            if t["provider"] == "stripe":
                result = PaymentProviderService._stripe_refund(
                    config["api_key_encrypted"],
                    t["provider_payment_id"],
                    refund_amount,
                    t.get("currency", "GBP"),
                )
            elif t["provider"] == "gocardless":
                result = PaymentProviderService._gocardless_refund(
                    config["api_key_encrypted"],
                    config.get("environment", "live"),
                    t["provider_payment_id"],
                    refund_amount,
                )
            else:
                raise ValueError(f"Refund not supported for provider: {t['provider']}")

            now = datetime.now(timezone.utc).isoformat()
            refund_id = generate_id()
            db.execute(
                """INSERT INTO payment_transactions
                   (id, agency_id, invoice_id, provider, payment_type, amount, currency,
                    status, provider_payment_id, metadata_json, created_at, completed_at)
                   VALUES (?, ?, ?, ?, 'refund', ?, ?, ?, ?, ?, ?, ?)""",
                (refund_id, t["agency_id"], t.get("invoice_id"), t["provider"],
                 refund_amount, t.get("currency", "GBP"),
                 "completed" if result.get("success") else "failed",
                 result.get("refund_id", ""),
                 json.dumps({"original_transaction_id": transaction_id}),
                 now, now if result.get("success") else None),
            )

            return {
                "refund_id": refund_id,
                "amount": refund_amount,
                "status": "completed" if result.get("success") else "failed",
                "error": result.get("error"),
            }

    @staticmethod
    def get_transactions(agency_id: Optional[str] = None, limit: int = 50) -> list:
        """Get payment transaction history."""
        with get_db() as db:
            if agency_id:
                rows = db.execute(
                    "SELECT * FROM payment_transactions WHERE agency_id=? ORDER BY created_at DESC LIMIT ?",
                    (agency_id, limit),
                ).fetchall()
            else:
                rows = db.execute(
                    "SELECT * FROM payment_transactions ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            return [dict(r) for r in rows]

    # ── Stripe Helpers ────────────────────────────────────────────────

    @staticmethod
    def _stripe_create_checkout(api_key: str, amount: float, currency: str,
                                 description: str, success_url: str,
                                 cancel_url: str, metadata: dict = None) -> dict:
        """Create a Stripe Checkout Session."""
        try:
            import stripe
            stripe.api_key = api_key
            session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                line_items=[{
                    "price_data": {
                        "currency": currency.lower(),
                        "product_data": {"name": description},
                        "unit_amount": int(amount * 100),  # Stripe uses pence/cents
                    },
                    "quantity": 1,
                }],
                mode="payment",
                success_url=success_url + "?session_id={CHECKOUT_SESSION_ID}",
                cancel_url=cancel_url,
                metadata=metadata or {},
            )
            return {
                "checkout_url": session.url,
                "payment_id": session.id,
                "status": "pending",
                "metadata": metadata,
            }
        except Exception as e:
            logger.error(f"Stripe checkout creation failed: {e}")
            raise ValueError(f"Stripe error: {e}")

    @staticmethod
    def _stripe_refund(api_key: str, payment_intent_id: str,
                        amount: float, currency: str) -> dict:
        """Process a Stripe refund."""
        try:
            import stripe
            stripe.api_key = api_key
            # For checkout sessions, we need to get the payment intent first
            if payment_intent_id.startswith("cs_"):
                session = stripe.checkout.Session.retrieve(payment_intent_id)
                payment_intent_id = session.payment_intent

            refund = stripe.Refund.create(
                payment_intent=payment_intent_id,
                amount=int(amount * 100),
            )
            return {"success": True, "refund_id": refund.id}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ── GoCardless Helpers ────────────────────────────────────────────

    @staticmethod
    def _gocardless_create_payment(access_token: str, environment: str,
                                    amount: float, currency: str,
                                    description: str, metadata: dict = None) -> dict:
        """Create a GoCardless payment (requires an existing mandate)."""
        try:
            import gocardless_pro
            env = "sandbox" if environment == "sandbox" else "live"
            client = gocardless_pro.Client(access_token=access_token, environment=env)

            # For GoCardless, we create a billing request flow for new customers
            # which handles mandate creation and first payment
            billing_request = client.billing_requests.create(
                params={
                    "payment_request": {
                        "description": description,
                        "amount": int(amount * 100),  # GoCardless uses pence
                        "currency": currency.upper(),
                        "metadata": metadata or {},
                    },
                    "mandate_request": {
                        "scheme": "bacs",
                    },
                }
            )

            # Create a billing request flow (hosted page)
            flow = client.billing_request_flows.create(
                params={
                    "redirect_uri": metadata.get("success_url", "https://healthvet.ai/payment/success") if metadata else "https://healthvet.ai/payment/success",
                    "exit_uri": metadata.get("cancel_url", "https://healthvet.ai/payment/cancel") if metadata else "https://healthvet.ai/payment/cancel",
                    "links": {
                        "billing_request": billing_request.id,
                    },
                }
            )

            return {
                "checkout_url": flow.authorisation_url,
                "payment_id": billing_request.id,
                "status": "pending",
                "metadata": metadata,
            }
        except Exception as e:
            logger.error(f"GoCardless payment creation failed: {e}")
            raise ValueError(f"GoCardless error: {e}")

    @staticmethod
    def _gocardless_refund(access_token: str, environment: str,
                            payment_id: str, amount: float) -> dict:
        """Process a GoCardless refund."""
        try:
            import gocardless_pro
            env = "sandbox" if environment == "sandbox" else "live"
            client = gocardless_pro.Client(access_token=access_token, environment=env)

            # For billing requests, we need to find the payment first
            refund = client.refunds.create(
                params={
                    "amount": int(amount * 100),
                    "links": {"payment": payment_id},
                    "metadata": {"reason": "admin_refund"},
                }
            )
            return {"success": True, "refund_id": refund.id}
        except Exception as e:
            return {"success": False, "error": str(e)}


# ── Helper Functions ──────────────────────────────────────────────────

def _mask_key(key: Optional[str]) -> Optional[str]:
    """Mask an API key for display (show last 4 chars)."""
    if not key:
        return None
    if len(key) <= 8:
        return "••••" + key[-2:]
    return "••••••••" + key[-4:]


def _validate_provider_enabled(provider: str):
    """Raise if provider is not connected and enabled."""
    with get_db() as db:
        row = db.execute(
            "SELECT is_enabled, api_key_set FROM payment_provider_config WHERE provider=?",
            (provider,),
        ).fetchone()
        if not row:
            raise ValueError(f"Provider '{provider}' not found.")
        r = dict(row)
        if not r.get("api_key_set"):
            raise ValueError(f"Provider '{provider}' has no API key configured. Connect it first.")
        if not r.get("is_enabled"):
            raise ValueError(f"Provider '{provider}' is not enabled.")


def _resolve_provider(payment_type: str) -> Optional[str]:
    """Resolve which provider should handle a given payment type."""
    with get_db() as db:
        row = db.execute(
            "SELECT provider, fallback_provider FROM payment_routing WHERE payment_type=? AND is_enabled=1",
            (payment_type,),
        ).fetchone()
        if not row:
            return None
        r = dict(row)
        provider = r.get("provider")
        if provider:
            # Verify provider is still enabled
            prow = db.execute(
                "SELECT is_enabled FROM payment_provider_config WHERE provider=? AND is_enabled=1",
                (provider,),
            ).fetchone()
            if prow:
                return provider
        # Try fallback
        fallback = r.get("fallback_provider")
        if fallback:
            prow = db.execute(
                "SELECT is_enabled FROM payment_provider_config WHERE provider=? AND is_enabled=1",
                (fallback,),
            ).fetchone()
            if prow:
                return fallback
        return None
