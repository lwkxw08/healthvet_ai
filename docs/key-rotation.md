# Key Rotation Procedure

## Overview

Viper AI uses two critical secrets that must be rotated periodically:

| Secret | Purpose | Recommended rotation |
|--------|---------|---------------------|
| `JWT_SECRET` | Signs access & refresh tokens | Every 90 days |
| `ENCRYPTION_KEY` | Encrypts payment provider API keys at rest (Fernet) | Every 180 days or on compromise |

## JWT_SECRET Rotation (Zero-Downtime)

The backend supports **dual-key verification**: it tries the current `JWT_SECRET`
first, then falls back to `JWT_SECRET_PREVIOUS`. This lets you rotate without
logging out every user.

### Steps

1. **Generate a new key:**
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(64))"
   ```

2. **Copy the current key to the previous slot:**
   - In Railway → Variables, copy the current `JWT_SECRET` value
   - Set `JWT_SECRET_PREVIOUS` = (old value)

3. **Set the new key:**
   - Set `JWT_SECRET` = (new value from step 1)

4. **Deploy.** The backend will:
   - Sign all **new** tokens with the new key
   - Accept tokens signed with **either** key during verification

5. **Wait for old tokens to expire** (default: access tokens 15 min, refresh tokens 7 days).

6. **Remove the previous key** (optional, after 7+ days):
   - Delete the `JWT_SECRET_PREVIOUS` environment variable

### Rollback

If something breaks, swap the values back:
- Set `JWT_SECRET` = (old value from `JWT_SECRET_PREVIOUS`)
- Remove `JWT_SECRET_PREVIOUS`

---

## ENCRYPTION_KEY Rotation (Fernet — Re-encryption Required)

Unlike JWT rotation, Fernet keys cannot be dual-stacked natively. Rotating the
encryption key requires a re-encryption migration.

### Steps

1. **Generate a new Fernet key:**
   ```bash
   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```

2. **Set the transition environment variables:**
   ```
   ENCRYPTION_KEY_NEW = <new key from step 1>
   ENCRYPTION_KEY     = <current key — keep it while migrating>
   ```

3. **Run the re-encryption migration** (one-time script):
   ```python
   """Re-encrypt payment_provider_config rows with the new key."""
   import os
   from cryptography.fernet import Fernet

   old_fernet = Fernet(os.environ["ENCRYPTION_KEY"].encode())
   new_fernet = Fernet(os.environ["ENCRYPTION_KEY_NEW"].encode())

   # For each encrypted column in payment_provider_config:
   #   1. Decrypt with old key
   #   2. Re-encrypt with new key
   #   3. UPDATE the row
   # Columns: api_key_encrypted, api_secret_encrypted, webhook_secret
   ```

4. **Swap the keys:**
   - Set `ENCRYPTION_KEY` = (new key)
   - Remove `ENCRYPTION_KEY_NEW`

5. **Verify** by checking that provider config pages load correctly and
   Stripe test connectivity still works.

### Key-Versioning Envelope (Future Enhancement)

For non-disruptive rotation without re-encryption, prepend a key version to
ciphertext: `v2:<base64-ciphertext>`. The decrypt function checks the prefix
and selects the correct Fernet instance. This is recommended once the number
of encrypted columns grows.

---

## Audit Trail

Every key rotation should be recorded:

1. Create an entry in the audit trail:
   - Action: `key_rotation`
   - Entity: `jwt_secret` or `encryption_key`
   - Details: timestamp, rotated_by, previous key fingerprint (SHA-256 of first 8 chars)

2. Notify the team via the standard incident channel.

---

## Schedule

| Quarter | Action |
|---------|--------|
| Q1 | Rotate JWT_SECRET |
| Q2 | Rotate ENCRYPTION_KEY + re-encrypt |
| Q3 | Rotate JWT_SECRET |
| Q4 | Rotate ENCRYPTION_KEY + re-encrypt |

Add calendar reminders for the ops team.
