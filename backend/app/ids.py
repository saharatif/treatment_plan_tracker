from datetime import datetime
import secrets

# Random IDs aren't guaranteed unique on generation; callers should verify against the
# database and retry up to this many times (see app/services/storage.py and
# app/services/vault.py for the uniqueness-checking wrappers).
MAX_UNIQUE_ID_ATTEMPTS = 20


def generate_patient_id() -> str:
    return f"PAT-{datetime.now().year}-{secrets.randbelow(99999):05d}"


def generate_plan_id() -> str:
    return f"PLN-{datetime.now().year}-{secrets.randbelow(999):03d}"


def generate_orb_ref(patient_id: str, orb_number: int) -> str:
    return f"ORB-PAT{patient_id.split('-')[-1]}-{orb_number:03d}"


def generate_token() -> str:
    """Non-deterministic patient token. Never derive tokens from PII (name/DOB) —
    two patients can share both, which would collide on the unique token constraint."""
    return "tok_" + secrets.token_hex(8)
