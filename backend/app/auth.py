import hashlib

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from . import config

SESSION_COOKIE = "session"
SESSION_MAX_AGE = 60 * 60 * 24 * 30  # 30 Tage
RESET_MAX_AGE = 60 * 60 * 24  # 24 Stunden

_ph = PasswordHasher()
_serializer = URLSafeTimedSerializer(config.SECRET_KEY, salt="session")
_reset_serializer = URLSafeTimedSerializer(config.SECRET_KEY, salt="password-reset")


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _ph.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def create_session_token(user_id: int) -> str:
    return _serializer.dumps(user_id)


def read_session_token(token: str) -> int | None:
    try:
        value = _serializer.loads(token, max_age=SESSION_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None
    return value if isinstance(value, int) else None


def password_fingerprint(password_hash: str) -> str:
    return hashlib.sha256(password_hash.encode()).hexdigest()[:16]


def create_reset_token(user_id: int, password_hash: str) -> str:
    # Der Fingerprint bindet den Token ans aktuelle Passwort: nach einer
    # Änderung passt er nicht mehr — Einmal-Nutzung ohne Token-Tabelle.
    return _reset_serializer.dumps([user_id, password_fingerprint(password_hash)])


def read_reset_token(token: str) -> tuple[int, str] | None:
    try:
        value = _reset_serializer.loads(token, max_age=RESET_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None
    if (
        isinstance(value, list)
        and len(value) == 2
        and isinstance(value[0], int)
        and isinstance(value[1], str)
    ):
        return value[0], value[1]
    return None
