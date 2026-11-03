import json
import time

import pytest
from cryptography.hazmat.primitives import serialization
from mielenosoitukset_fi.utils.emergency_signatures import USB_DOMAIN, verify
from scripts.god_emergency_usb import KEY_FILE, initialize, sign_request


def test_usb_key_is_encrypted_exclusive_and_signs_only_bound_challenges(tmp_path):
    password = b'synthetic-test-key-password-32chars-only'
    registration = initialize(tmp_path, password)
    data = (tmp_path / KEY_FILE).read_bytes()
    assert b'BEGIN ENCRYPTED PRIVATE KEY' in data
    with pytest.raises(TypeError):
        serialization.load_pem_private_key(data, password=None)
    with pytest.raises(FileExistsError):
        initialize(tmp_path, password)
    challenge = {'domain': USB_DOMAIN, 'request_id': 'a' * 32, 'candidate_id': 'b' * 24,
        'expires_at': int(time.time()) + 300, 'reason': 'Synthetic emergency signing test', 'nonce': 'c' * 43}
    proof = sign_request(tmp_path, password, challenge)
    assert verify(proof, {registration['key_id']: registration['public_key']}, USB_DOMAIN) == challenge
    with pytest.raises(ValueError):
        sign_request(tmp_path, password, {**challenge, 'domain': 'other-purpose'})
    with pytest.raises(ValueError):
        sign_request(tmp_path, password, {**challenge, 'expires_at': int(time.time()) - 1})


def test_usb_signer_refuses_symlink_key(tmp_path):
    outside = tmp_path / 'outside'
    outside.write_bytes(b'not a key')
    directory = tmp_path / 'usb'
    directory.mkdir()
    (directory / KEY_FILE).symlink_to(outside)
    with pytest.raises(OSError):
        sign_request(directory, b'test password', {'domain': USB_DOMAIN, 'request_id': 'a' * 32,
            'candidate_id': 'b' * 24, 'expires_at': int(time.time()) + 300})
