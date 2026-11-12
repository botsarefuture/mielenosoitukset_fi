#!/usr/bin/env python3
"""Enroll or use a separate encrypted appointment key on a mounted Mac USB.

Never use the unrelated SessionVault key. Private bytes and passwords are never
printed or uploaded. The output is public registration data or a request-bound
signature, which still needs a fresh complete god login to approve anything.
"""
import argparse
import getpass
import json
import os
from pathlib import Path
import plistlib
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from mielenosoitukset_fi.utils.emergency_signatures import USB_DOMAIN, public_key_id, sign

KEY_FILE = 'mielenosoitukset-god-emergency-v1.encrypted.pem'


def usb_root(volume, expected_uuid):
    root = Path(volume).resolve(strict=True)
    result = subprocess.run(['diskutil', 'info', '-plist', str(root)], check=True, capture_output=True)
    info = plistlib.loads(result.stdout)
    if (info.get('BusProtocol') != 'USB' or info.get('Internal') is not False
            or info.get('RemovableMedia') is not True or info.get('VolumeUUID') != expected_uuid
            or info.get('MountPoint') != str(root)):
        raise ValueError('The expected external USB volume is not mounted here')
    return root


def password(dialog=False, confirm=False):
    def read(prompt):
        if dialog:
            # Only the local process receives the hidden native-dialog result.
            # It is never placed in command arguments, logs or tool output.
            script = 'text returned of (display dialog ' + json.dumps(prompt) + ' default answer "" with hidden answer buttons {"Cancel", "OK"} default button "OK" giving up after 300)'
            try:
                return subprocess.run(['osascript', '-e', script], check=True, capture_output=True, text=True).stdout.rstrip('\n')
            except subprocess.CalledProcessError as exc:
                raise ValueError('Password entry was cancelled or timed out') from exc
        return getpass.getpass(prompt + ': ')
    value = read('Mielenosoitukset.fi USB key password (32+ characters)')
    if len(value) < 32:
        raise ValueError('Use at least 32 characters for the USB encryption password')
    if confirm and read('Confirm the new USB key password') != value:
        raise ValueError('Passwords do not match')
    return value.encode('utf-8')


def initialize(root, secret):
    key = Ed25519PrivateKey.generate()
    encrypted = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                  serialization.BestAvailableEncryption(secret))
    # Exclusive/no-follow creation never replaces an existing key or symlink.
    descriptor = os.open(root / KEY_FILE, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'wb') as target:
        target.write(encrypted)
        target.flush()
        os.fsync(target.fileno())
    return {'key_id': public_key_id(key.public_key()), 'public_key': key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode('ascii')}


def sign_request(root, secret, challenge):
    if (not isinstance(challenge, dict) or challenge.get('domain') != USB_DOMAIN
            or not isinstance(challenge.get('expires_at'), int) or not time.time() < challenge['expires_at'] <= time.time() + 901
            or not isinstance(challenge.get('candidate_id'), str) or len(challenge['candidate_id']) != 24
            or not isinstance(challenge.get('request_id'), str) or len(challenge['request_id']) != 32):
        raise ValueError('Invalid or expired appointment challenge')
    descriptor = os.open(root / KEY_FILE, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor, 'rb') as source:
        encrypted = source.read(16385)
    if len(encrypted) > 16384:
        raise ValueError('Unexpected key file size')
    key = serialization.load_pem_private_key(encrypted, password=secret)
    if not isinstance(key, Ed25519PrivateKey):
        raise ValueError('Unexpected key type')
    return sign(key, challenge)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['init', 'sign'])
    parser.add_argument('--volume', required=True)
    parser.add_argument('--volume-uuid', required=True)
    parser.add_argument('--challenge', type=Path)
    parser.add_argument('--macos-dialog', action='store_true')
    args = parser.parse_args()
    root = usb_root(args.volume, args.volume_uuid)
    if args.command == 'init':
        secret = password(args.macos_dialog, confirm=True)
        root = usb_root(args.volume, args.volume_uuid)
        result = initialize(root, secret)
    else:
        if not args.challenge or args.challenge.stat().st_size > 16384:
            raise ValueError('Supply the small JSON challenge downloaded from the HTTPS administration page')
        challenge = json.loads(args.challenge.read_text())
        print('Appointment target: ' + str(challenge.get('candidate_id')), file=sys.stderr)
        print('Emergency reason: ' + str(challenge.get('reason')), file=sys.stderr)
        if input('Type the complete target account ID to authorize signing: ').strip() != challenge.get('candidate_id'):
            raise ValueError('Signing cancelled')
        secret = password(args.macos_dialog)
        usb_root(args.volume, args.volume_uuid)
        result = sign_request(root, secret, challenge)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
