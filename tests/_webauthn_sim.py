"""A tiny in-memory WebAuthn authenticator for tests.

Builds ``"none"``-attestation registration credentials and ES256 assertion
credentials that a real browser/authenticator would produce, so the full
registration → login → step-up flows can be exercised without a device.
"""

import hashlib
import json
import secrets

from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import hashes
from webauthn.helpers import bytes_to_base64url, encode_cbor

COSE_ES256 = -7
COSE_P256 = 1
COSE_KTY_EC2 = 2


def generate_key():
    """Return a fresh P-256 ES256 private key."""
    return ec.generate_private_key(ec.SECP256R1())


def public_cose_key(public_key) -> dict:
    numbers = public_key.public_numbers()
    return {
        1: COSE_KTY_EC2,
        3: COSE_ES256,
        -1: COSE_P256,
        -2: numbers.x.to_bytes(32, "big"),
        -3: numbers.y.to_bytes(32, "big"),
    }


def _rp_id_hash(rp_id: str) -> bytes:
    return hashlib.sha256(rp_id.encode()).digest()


def authenticator_data(
    rp_id: str,
    flags: int,
    counter: int,
    *,
    credential_id: bytes = None,
    public_key=None,
) -> bytes:
    data = _rp_id_hash(rp_id) + bytes([flags]) + counter.to_bytes(4, "big")
    if credential_id is not None:
        data += b"\x00" * 16  # AAGUID
        data += len(credential_id).to_bytes(2, "big")
        data += credential_id
        data += encode_cbor(public_cose_key(public_key))
    return data


def client_data_json(challenge_b64url: str, origin: str, typ: str) -> bytes:
    payload = {
        "type": typ,
        "challenge": challenge_b64url,
        "origin": origin,
        "crossOrigin": False,
    }
    return json.dumps(payload, separators=(",", ":")).encode()


def registration_credential_json(
    options: dict,
    key,
    *,
    origin: str,
    credential_id: bytes = None,
    transports=None,
) -> dict:
    credential_id = credential_id or secrets.token_bytes(32)
    client_data = client_data_json(options["challenge"], origin, "webauthn.create")
    auth_data = authenticator_data(
        options["rp"]["id"],
        flags=0x45,  # UP | UV | AT
        counter=0,
        credential_id=credential_id,
        public_key=key.public_key(),
    )
    attestation_object = encode_cbor({"fmt": "none", "attStmt": {}, "authData": auth_data})
    return {
        "id": bytes_to_base64url(credential_id),
        "rawId": bytes_to_base64url(credential_id),
        "type": "public-key",
        "response": {
            "clientDataJSON": bytes_to_base64url(client_data),
            "attestationObject": bytes_to_base64url(attestation_object),
            "transports": transports if transports is not None else ["usb"],
        },
    }


def assertion_credential_json(
    options: dict,
    key,
    *,
    origin: str,
    credential_id: str,
    counter: int = 1,
) -> dict:
    client_data = client_data_json(options["challenge"], origin, "webauthn.get")
    auth_data = authenticator_data(options["rpId"], flags=0x03, counter=counter)  # UP | UV
    client_data_hash = hashlib.sha256(client_data).digest()
    # ECDSA(SHA256) hashes the data internally: sign authData || clientDataHash.
    signature = key.sign(auth_data + client_data_hash, ec.ECDSA(hashes.SHA256()))
    return {
        "id": credential_id,
        "rawId": credential_id,
        "type": "public-key",
        "response": {
            "clientDataJSON": bytes_to_base64url(client_data),
            "authenticatorData": bytes_to_base64url(auth_data),
            "signature": bytes_to_base64url(signature),
        },
    }