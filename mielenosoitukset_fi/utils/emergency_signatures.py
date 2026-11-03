"""Purpose-bound Ed25519 messages shared by panel, USB signer and verifier."""
import base64
import hashlib
import json

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

PANEL_DOMAIN = "mielenosoitukset.fi/god-emergency-panel/v1"
USB_DOMAIN = "mielenosoitukset.fi/god-emergency-usb/v1"


def canonical(message):
    return json.dumps(message, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def public_key_id(key):
    raw = key.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return hashlib.sha256(raw).hexdigest()


def encode(value):
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def decode(value, maximum=4096):
    if not isinstance(value, str) or not value or len(value) > maximum:
        raise ValueError("Virheellinen allekirjoitus.")
    return base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)


def sign(key, message):
    return {"key_id": public_key_id(key.public_key()), "message": message, "signature": encode(key.sign(canonical(message)))}


def verify(proof, trusted_keys, domain):
    if not isinstance(proof, dict) or not isinstance(trusted_keys, dict):
        raise ValueError("Allekirjoituksen luottamusasetukset puuttuvat.")
    key_id = proof.get("key_id")
    pem = trusted_keys.get(key_id) if isinstance(key_id, str) else None
    message = proof.get("message")
    if not isinstance(pem, str) or not isinstance(message, dict) or message.get("domain") != domain:
        raise ValueError("Allekirjoitusta ei tunnistettu.")
    try:
        key = serialization.load_pem_public_key(pem.encode("ascii"))
        if not isinstance(key, Ed25519PublicKey) or public_key_id(key) != key_id:
            raise ValueError("Virheellinen allekirjoitusavain.")
        key.verify(decode(proof.get("signature"), 128), canonical(message))
    except (InvalidSignature, TypeError, UnicodeError) as exc:
        raise ValueError("Virheellinen allekirjoitus.") from exc
    return message
