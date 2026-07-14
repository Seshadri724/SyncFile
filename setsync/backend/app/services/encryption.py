import base64
import hashlib
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from app.config import settings

def get_tenant_key(org_id: str | None) -> bytes:
    """Derive a 32-byte key from org_id and the system API_TOKEN.
    This is the FALLBACK path used when no client-provided key is available.
    WARNING: This is NOT zero-knowledge — the server can derive and decrypt."""
    org = org_id or "solo"
    h = hashlib.sha256(f"{org}:{settings.API_TOKEN}".encode("utf-8")).digest()
    return h

def get_tenant_key_from_header(tenant_key_hex: str | None, org_id: str | None) -> bytes:
    """Resolve the encryption key with zero-knowledge priority:
    1. If a client-provided key is present (64-char hex), use it directly.
       This key is NEVER persisted — it exists only in RAM for the request duration.
    2. Otherwise fall back to server-derived key for backward compatibility."""
    if tenant_key_hex and len(tenant_key_hex) == 64:
        try:
            return bytes.fromhex(tenant_key_hex)
        except ValueError:
            pass
    return get_tenant_key(org_id)

def pad(data: bytes) -> bytes:
    pad_len = 16 - (len(data) % 16)
    return data + bytes([pad_len] * pad_len)

def unpad(data: bytes) -> bytes:
    pad_len = data[-1]
    if pad_len < 1 or pad_len > 16:
        raise ValueError("Invalid PKCS7 padding")
    return data[:-pad_len]

import hmac

def get_context_key(base_key: bytes, context: str) -> bytes:
    """Derive a context-specific subkey from base_key and current folder path using HMAC-SHA256."""
    return hmac.new(base_key, context.encode("utf-8"), hashlib.sha256).digest()

def encrypt_component(component: str, key: bytes) -> str:
    """Encrypt a single path component using a given key."""
    data = component.encode("utf-8")
    iv = hashlib.md5(data).digest()
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    ciphertext = encryptor.update(pad(data)) + encryptor.finalize()
    return base64.urlsafe_b64encode(iv + ciphertext).decode("utf-8")

def decrypt_component(ciphertext_str: str, key: bytes) -> str:
    """Decrypt a single path component using a given key."""
    raw = base64.urlsafe_b64decode(ciphertext_str.encode("utf-8"))
    if len(raw) < 16:
        raise ValueError("Ciphertext component too short")
    iv = raw[:16]
    ciphertext = raw[16:]
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    decryptor = cipher.decryptor()
    decrypted = decryptor.update(ciphertext) + decryptor.finalize()
    return unpad(decrypted).decode("utf-8")

def encrypt_deterministic(plaintext: str | None, key: bytes) -> str | None:
    if plaintext is None:
        return None
    if not plaintext:
        return ""
    
    parts = plaintext.split("/")
    encrypted_parts = []
    current_context = ""
    
    for part in parts:
        level_key = get_context_key(key, current_context)
        enc = encrypt_component(part, level_key)
        encrypted_parts.append(enc)
        if current_context:
            current_context += "/" + part
        else:
            current_context = part
            
    return "/".join(encrypted_parts)

def decrypt_deterministic(ciphertext_str: str | None, key: bytes) -> str | None:
    if ciphertext_str is None:
        return None
    if not ciphertext_str:
        return ""
        
    try:
        parts = ciphertext_str.split("/")
        decrypted_parts = []
        current_context = ""
        
        for part in parts:
            level_key = get_context_key(key, current_context)
            dec = decrypt_component(part, level_key)
            decrypted_parts.append(dec)
            if current_context:
                current_context += "/" + dec
            else:
                current_context = dec
                
        return "/".join(decrypted_parts)
    except Exception:
        # Fallback for raw/unencrypted strings
        return ciphertext_str

def compute_tenant_key_check_hash(key: bytes) -> str:
    """Computes a deterministic hash to verify key consistency without exposing the key."""
    cipher_text = encrypt_component("SetSyncTenantKeyVerificationStringConstant", key)
    return hashlib.sha256(cipher_text.encode("utf-8")).hexdigest()
