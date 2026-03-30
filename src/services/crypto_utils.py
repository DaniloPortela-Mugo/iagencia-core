import base64
import hashlib
import os
from typing import Optional

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
except Exception:  # pragma: no cover - fallback when dependency missing
    AESGCM = None


def _load_key() -> Optional[bytes]:
    raw = (os.getenv("IAGENCIA_CRYPTO_KEY") or "").strip()
    if not raw:
        return None
    try:
        if raw.startswith("hex:"):
            key_bytes = bytes.fromhex(raw[4:])
        else:
            padded = raw + "=" * (-len(raw) % 4)
            key_bytes = base64.urlsafe_b64decode(padded.encode())
    except Exception:
        key_bytes = raw.encode()
    if len(key_bytes) != 32:
        key_bytes = hashlib.sha256(key_bytes).digest()
    return key_bytes


def encrypt_secret(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    if not value:
        return value
    if value.startswith("enc:"):
        return value
    key = _load_key()
    if not key or AESGCM is None:
        return value
    nonce = os.urandom(12)
    aes = AESGCM(key)
    ct = aes.encrypt(nonce, value.encode(), None)
    packed = base64.urlsafe_b64encode(nonce + ct).decode().rstrip("=")
    return f"enc:{packed}"


def decrypt_secret(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    if not value:
        return value
    if not value.startswith("enc:"):
        return value
    key = _load_key()
    if not key or AESGCM is None:
        return value
    try:
        data = value[4:]
        padded = data + "=" * (-len(data) % 4)
        raw = base64.urlsafe_b64decode(padded.encode())
        nonce, ct = raw[:12], raw[12:]
        aes = AESGCM(key)
        pt = aes.decrypt(nonce, ct, None)
        return pt.decode()
    except Exception:
        return None
