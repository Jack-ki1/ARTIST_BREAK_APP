import json
import os

from cryptography.fernet import Fernet, InvalidToken


def _fernet() -> Fernet:
    key = os.getenv("PROVIDER_SECRETS_KEY")
    if not key:
        raise RuntimeError(
            "Set PROVIDER_SECRETS_KEY in backend/.env before saving provider credentials"
        )
    try:
        return Fernet(key.encode("ascii"))
    except (ValueError, UnicodeEncodeError) as exc:
        raise RuntimeError("PROVIDER_SECRETS_KEY is not a valid Fernet key") from exc


def encrypt_credentials(credentials: dict[str, str]) -> str:
    payload = json.dumps(credentials, separators=(",", ":"), sort_keys=True).encode()
    return _fernet().encrypt(payload).decode("ascii")


def decrypt_credentials(encrypted: str | None) -> dict[str, str]:
    if encrypted is None:
        return {}
    try:
        payload = _fernet().decrypt(encrypted.encode("ascii"))
        credentials = json.loads(payload)
    except (InvalidToken, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            "Could not decrypt saved provider credentials; verify PROVIDER_SECRETS_KEY"
        ) from exc
    if not isinstance(credentials, dict) or not all(
        isinstance(key, str) and isinstance(value, str)
        for key, value in credentials.items()
    ):
        raise RuntimeError("Saved provider credentials have an invalid format")
    return credentials
