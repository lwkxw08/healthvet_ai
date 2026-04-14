"""
Email Rules Engine
Maps business actions (triggers) to email templates with conditions.
Allows admin to configure which template fires for which action,
add conditions, set priority, and enable/disable rules.
"""
import json
import logging
from datetime import datetime, timezone
from app.database import get_db
from app.utils.auth import generate_id

logger = logging.getLogger(__name__)

# ── Default Rules ──────────────────────────────────────────────────────────────
# These seed the database on first run. Each maps an action_trigger to a template_key.

DEFAULT_RULES = [
    {
        "action_trigger": "verification_requested",
        "name": "Employment Verification Request",
        "description": "Sent to the employer/referee when an agency requests employment verification for a candidate.",
        "template_key": "employment_verification_request",
        "recipient_type": "referee",
        "conditions": {},
        "priority": 0,
    },
    {
        "action_trigger": "reference_requested",
        "name": "Reference Request",
        "description": "Sent to the referee when an agency requests a professional reference for a candidate.",
        "template_key": "reference_request",
        "recipient_type": "referee",
        "conditions": {},
        "priority": 0,
    },
    {
        "action_trigger": "verification_reminder",
        "name": "Verification Reminder",
        "description": "Sent as a follow-up when a verification or reference request has not been responded to within the configured time.",
        "template_key": "verification_reminder",
        "recipient_type": "referee",
        "conditions": {"min_days_since_request": 7},
        "priority": 0,
    },
    {
        "action_trigger": "credential_expiring",
        "name": "Expiry Warning \u2014 Agency",
        "description": "Sent to the agency when one or more candidate credentials are approaching expiry.",
        "template_key": "expiry_warning_agency",
        "recipient_type": "agency",
        "conditions": {},
        "priority": 0,
    },
    {
        "action_trigger": "credential_expiring",
        "name": "Expiry Warning \u2014 Candidate",
        "description": "Sent to the candidate when their credential is approaching expiry.",
        "template_key": "expiry_warning_candidate",
        "recipient_type": "candidate",
        "conditions": {},
        "priority": 0,
    },
    {
        "action_trigger": "monitoring_alerts_detected",
        "name": "Monitoring Alert Summary",
        "description": "Sent to the agency when automated monitoring detects compliance issues for their candidates.",
        "template_key": "monitoring_alert_summary",
        "recipient_type": "agency",
        "conditions": {},
        "priority": 0,
    },
    {
        "action_trigger": "invoice_created",
        "name": "Invoice Notification",
        "description": "Sent to the agency when a new invoice is generated.",
        "template_key": "invoice_notification",
        "recipient_type": "agency",
        "conditions": {},
        "priority": 0,
    },
    {
        "action_trigger": "payment_overdue",
        "name": "Payment Reminder",
        "description": "Sent to the agency when an invoice payment is overdue.",
        "template_key": "payment_reminder",
        "recipient_type": "agency",
        "conditions": {},
        "priority": 0,
    },
    {
        "action_trigger": "candidate_invited",
        "name": "Candidate Portal Invite",
        "description": "Sent to a candidate when they are invited to the portal by an agency.",
        "template_key": "candidate_invite",
        "recipient_type": "candidate",
        "conditions": {},
        "priority": 0,
    },
    {
        "action_trigger": "subscription_purchased",
        "name": "Subscription Confirmation",
        "description": "Sent to the agency when they purchase or renew a subscription or credit pack.",
        "template_key": "subscription_confirmation",
        "recipient_type": "agency",
        "conditions": {},
        "priority": 0,
    },
]

# All known action triggers with descriptions for the UI
ACTION_TRIGGERS = {
    "verification_requested": {
        "label": "Verification Requested",
        "description": "Fires when an agency requests employment or qualification verification.",
        "category": "verification",
    },
    "reference_requested": {
        "label": "Reference Requested",
        "description": "Fires when an agency requests a professional reference check.",
        "category": "verification",
    },
    "verification_reminder": {
        "label": "Verification Reminder",
        "description": "Fires when a verification/reference request has had no response after a set number of days.",
        "category": "verification",
    },
    "credential_expiring": {
        "label": "Credential Expiring",
        "description": "Fires when a candidate's credential (DBS, RTW, etc.) is approaching its expiry date.",
        "category": "compliance",
    },
    "monitoring_alerts_detected": {
        "label": "Monitoring Alerts Detected",
        "description": "Fires when the automated monitoring system detects compliance issues.",
        "category": "compliance",
    },
    "invoice_created": {
        "label": "Invoice Created",
        "description": "Fires when a new invoice is generated for an agency.",
        "category": "billing",
    },
    "payment_overdue": {
        "label": "Payment Overdue",
        "description": "Fires when an invoice payment is overdue.",
        "category": "billing",
    },
    "candidate_invited": {
        "label": "Candidate Invited",
        "description": "Fires when a candidate is invited to the portal by an agency.",
        "category": "onboarding",
    },
    "subscription_purchased": {
        "label": "Subscription Purchased",
        "description": "Fires when an agency purchases or renews a subscription or credit pack.",
        "category": "billing",
    },
}


class EmailRulesService:
    """Manages email rules: action-to-template mappings with conditions."""

    @staticmethod
    def seed_defaults():
        """Seed default email rules if table is empty."""
        with get_db() as db:
            db.execute("SELECT COUNT(*) as cnt FROM email_rules")
            count = db.fetchone()
            if dict(count)["cnt"] > 0:
                return  # Already seeded

            now = datetime.now(timezone.utc).isoformat()
            for rule in DEFAULT_RULES:
                db.execute(
                    """INSERT INTO email_rules
                       (id, action_trigger, name, description, template_key,
                        recipient_type, conditions, priority, is_active, created_at, updated_at)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 1, %s, %s)""",
                    (
                        generate_id(),
                        rule["action_trigger"],
                        rule["name"],
                        rule["description"],
                        rule["template_key"],
                        rule["recipient_type"],
                        json.dumps(rule["conditions"]),
                        rule["priority"],
                        now, now,
                    ),
                )
            logger.info(f"Seeded {len(DEFAULT_RULES)} default email rules")

    # ── CRUD ────────────────────────────────────────────────────────────

    @staticmethod
    def get_all_rules() -> list:
        with get_db() as db:
            db.execute(
                "SELECT * FROM email_rules ORDER BY action_trigger, priority"
            )
            rows = db.fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def get_rule(rule_id: str) -> dict:
        with get_db() as db:
            db.execute(
                "SELECT * FROM email_rules WHERE id=%s", (rule_id,)
            )
            row = db.fetchone()
            return dict(row) if row else None

    @staticmethod
    def get_rules_for_trigger(action_trigger: str) -> list:
        """Get all active rules for a given action trigger, ordered by priority."""
        with get_db() as db:
            db.execute(
                """SELECT r.*, t.name as template_name, t.is_active as template_active
                   FROM email_rules r
                   LEFT JOIN email_templates t ON r.template_key = t.template_key
                   WHERE r.action_trigger=%s AND r.is_active=1
                   ORDER BY r.priority ASC""",
                (action_trigger,),
            )
            rows = db.fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def create_rule(
        action_trigger: str,
        name: str,
        template_key: str,
        description: str = "",
        recipient_type: str = "primary",
        conditions: dict = None,
        priority: int = 0,
    ) -> dict:
        rule_id = generate_id()
        now = datetime.now(timezone.utc).isoformat()
        with get_db() as db:
            db.execute(
                """INSERT INTO email_rules
                   (id, action_trigger, name, description, template_key,
                    recipient_type, conditions, priority, is_active, created_at, updated_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 1, %s, %s)""",
                (
                    rule_id, action_trigger, name, description,
                    template_key, recipient_type,
                    json.dumps(conditions or {}),
                    priority, now, now,
                ),
            )
            db.execute(
                "SELECT * FROM email_rules WHERE id=%s", (rule_id,)
            )
            row = db.fetchone()
            return dict(row)

    @staticmethod
    def update_rule(
        rule_id: str,
        name: str = None,
        description: str = None,
        template_key: str = None,
        recipient_type: str = None,
        conditions: dict = None,
        priority: int = None,
        is_active: bool = None,
    ) -> dict:
        now = datetime.now(timezone.utc).isoformat()
        with get_db() as db:
            db.execute(
                "SELECT * FROM email_rules WHERE id=%s", (rule_id,)
            )
            row = db.fetchone()
            if not row:
                return None
            current = dict(row)

            db.execute(
                """UPDATE email_rules SET
                   name=%s, description=%s, template_key=%s, recipient_type=%s,
                   conditions=%s, priority=%s, is_active=%s, updated_at=%s
                   WHERE id=%s""",
                (
                    name if name is not None else current["name"],
                    description if description is not None else current["description"],
                    template_key if template_key is not None else current["template_key"],
                    recipient_type if recipient_type is not None else current["recipient_type"],
                    json.dumps(conditions) if conditions is not None else current["conditions"],
                    priority if priority is not None else current["priority"],
                    (1 if is_active else 0) if is_active is not None else current["is_active"],
                    now,
                    rule_id,
                ),
            )
            db.execute(
                "SELECT * FROM email_rules WHERE id=%s", (rule_id,)
            )
            row = db.fetchone()
            return dict(row)

    @staticmethod
    def delete_rule(rule_id: str) -> bool:
        with get_db() as db:
            db.execute(
                "SELECT * FROM email_rules WHERE id=%s", (rule_id,)
            )
            row = db.fetchone()
            if not row:
                return None
            db.execute("DELETE FROM email_rules WHERE id=%s", (rule_id,))
            return True

    @staticmethod
    def get_action_triggers() -> dict:
        """Return all known action triggers with metadata."""
        return ACTION_TRIGGERS

    # ── Rule Evaluation ─────────────────────────────────────────────────

    @staticmethod
    def evaluate_conditions(conditions_json: str, context: dict) -> bool:
        """Evaluate whether rule conditions are met given the context.

        Supported conditions:
        - min_days_since_request: int — only fire if days_since >= value
        - max_days_left: int — only fire if days_left <= value
        - check_types: list — only fire if check_type is in the list
        - urgency: str — only fire if urgency matches
        """
        try:
            conditions = json.loads(conditions_json) if isinstance(conditions_json, str) else conditions_json
        except (json.JSONDecodeError, TypeError):
            return True  # No conditions or invalid = always fire

        if not conditions:
            return True

        for key, value in conditions.items():
            if key == "min_days_since_request":
                days = context.get("days_since_request", 0)
                if days < value:
                    return False
            elif key == "max_days_left":
                days_left = context.get("days_left", 999)
                if days_left > value:
                    return False
            elif key == "check_types":
                check_type = context.get("check_type", "")
                if isinstance(value, list) and check_type not in value:
                    return False
            elif key == "urgency":
                if context.get("urgency", "") != value:
                    return False

        return True

    @staticmethod
    def resolve_template_for_action(
        action_trigger: str,
        recipient_type: str = None,
        context: dict = None,
    ) -> list:
        """Resolve which template(s) to use for a given action.

        Returns a list of dicts: [{template_key, recipient_type, rule_id, rule_name}]
        Multiple rules can match (e.g. send to both agency AND candidate).
        """
        rules = EmailRulesService.get_rules_for_trigger(action_trigger)
        context = context or {}
        matched = []

        for rule in rules:
            # Filter by recipient_type if specified
            if recipient_type and rule["recipient_type"] != recipient_type:
                continue

            # Check if the template is also active
            if rule.get("template_active") == 0:
                continue

            # Evaluate conditions
            if EmailRulesService.evaluate_conditions(rule["conditions"], context):
                matched.append({
                    "template_key": rule["template_key"],
                    "recipient_type": rule["recipient_type"],
                    "rule_id": rule["id"],
                    "rule_name": rule["name"],
                })

        return matched
