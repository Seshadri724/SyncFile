import base64
import hashlib
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from app.config import settings

def get_tenant_key(org_id: str | None) -> bytes:
    # Derive a 32-byte key from org_id (or default "solo") and the system API_TOKEN
    org = org_id or "solo"
    h = hashlib.sha256(f"{org}:{settings.API_TOKEN}".encode("utf-8")).digest()
    return h

def pad(data: bytes) -> bytes:
    pad_len = 16 - (len(data) % 16)
    return data + bytes([pad_len] * pad_len)

def unpad(data: bytes) -> bytes:
    pad_len = data[-1]
    if pad_len < 1 or pad_len > 16:
        raise ValueError("Invalid PKCS7 padding")
    return data[:-pad_len]

def encrypt_deterministic(plaintext: str | None, key: bytes) -> str | None:
    if plaintext is None:
        return None
    data = plaintext.encode("utf-8")
    # Derive IV deterministically from MD5 of data to ensure identical text maps to identical cipher
    iv = hashlib.md5(data).digest()
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    ciphertext = encryptor.update(pad(data)) + encryptor.finalize()
    return base64.urlsafe_b64encode(iv + ciphertext).decode("utf-8")

def decrypt_deterministic(ciphertext_str: str | None, key: bytes) -> str | None:
    if ciphertext_str is None:
        return None
    try:
        raw = base64.urlsafe_b64decode(ciphertext_str.encode("utf-8"))
        if len(raw) < 16:
            return ciphertext_str
        iv = raw[:16]
        ciphertext = raw[16:]
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
        decryptor = cipher.decryptor()
        decrypted = decryptor.update(ciphertext) + decryptor.finalize()
        return unpad(decrypted).decode("utf-8")
    except Exception:
        # Fallback to returning original string if not encrypted
        return ciphertext_str
