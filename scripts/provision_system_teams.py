#!/usr/bin/env python3
"""Explicit, idempotent maintainer bootstrap; never creates usable credentials.

Run from the deployed checkout only after its governance protections are live.
Organization IDs are supplied deliberately, not selected by an editable name.
Configuration is a separate, backed-up deployment step. No mail is sent here.
"""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bson import ObjectId
from mielenosoitukset_fi.database_manager import DatabaseManager
from mielenosoitukset_fi.utils.system_teams import SUPER_ROLES, olivia_user_id, team_ids
from mielenosoitukset_fi.utils.time_utils import utcnow
from mielenosoitukset_fi.utils.validators import normalize_email, normalize_username, valid_email, validate_username


def provision(db, *, national_id, board_id, olivia_id, second_id, username, email, apply=False):
    national_id, board_id, olivia_id, second_id = map(ObjectId, map(str, (national_id, board_id, olivia_id, second_id)))
    if national_id == board_id or olivia_id == second_id:
        raise ValueError('Teams and initial approvers must be distinct')
    for uid, expected in ((olivia_id, 'olivia'), (second_id, 'tikrutre')):
        user = db.users.find_one({'_id': uid})
        if (not user or user.get('username') != expected or user.get('active') is False or user.get('banned') is True
                or user.get('confirmed') is not True or not (user.get('role') in SUPER_ROLES or user.get('global_admin') is True)):
            raise ValueError('Bootstrap requires the two explicitly approved existing administrators')
    username, email = normalize_username(username), normalize_email(email)
    if not validate_username(username)[0] or not valid_email(email):
        raise ValueError('Invalid pending account identity')
    matches = list(db.users.find({'$or': [{'username_canonical': username}, {'username': username}, {'email_canonical': email}, {'email': email}]}))
    if matches and (len(matches) != 1 or matches[0].get('username') != username or matches[0].get('email') != email
                    or not (matches[0].get('god_candidate') or matches[0].get('god_security', {}).get('policy') == 1)):
        raise ValueError('Username/email already belongs to another account')
    candidate = matches[0]['_id'] if matches else ObjectId()
    definitions = [(national_id, 'Valtakunnallinen ylläpitotiimi', 'Palvelun valtakunnallinen ylläpito.'),
                   (board_id, 'Hallitus', 'Palvelun hallituksen jäsenet.')]
    for oid, name, _ in definitions:
        org = db.organizations.find_one({'_id': oid})
        if org and org.get('name') != name:
            raise ValueError('Organization ID belongs to another organization')
        unexpected = db.memberships.find_one({'organization_id': {'$in': [oid, str(oid)]},
            'user_id': {'$nin': [olivia_id, second_id, str(olivia_id), str(second_id)]}, 'grant_source': 'maintainer_bootstrap'})
        if unexpected:
            raise ValueError('Unexpected existing bootstrap member')
    if apply:
        configured = team_ids()
        if configured.get('national') != national_id or configured.get('board') != board_id or olivia_user_id() != str(olivia_id):
            raise ValueError('Configure these exact protected IDs before applying bootstrap')
        for oid, name, description in definitions:
            db.organizations.update_one({'_id': oid}, {'$setOnInsert': {'name': name, 'description': description,
                'email': '', 'website': '', 'logo': None, 'verified': True, 'social_media_links': {}, 'invitations': []}}, upsert=True)
            for uid in (olivia_id, second_id):
                db.memberships.update_one({'organization_id': oid, 'user_id': uid}, {'$set': {
                    'governance_approved': True, 'grant_source': 'maintainer_bootstrap'}, '$setOnInsert': {
                    'role': 'member', 'permissions': [], 'created_at': utcnow()}}, upsert=True)
        db.users.update_one({'_id': candidate}, {'$setOnInsert': {'username': username, 'username_canonical': username,
            'email': email, 'email_canonical': email, 'displayname': username, 'password_hash': '!inactive-god-enrollment',
            'active': False, 'confirmed': False, 'banned': False, 'role': 'user', 'global_admin': False,
            'global_permissions': [], 'god_candidate': True, 'created_at': utcnow()}}, upsert=True)
        db.board_audit_logs.insert_one({'user_id': str(candidate), 'action': 'ylläpitotiimien alustuksen tarkistus',
            'granted_by': 'maintainer-bootstrap', 'timestamp': utcnow(),
            'members': [str(olivia_id), str(second_id)], 'organizations': [str(national_id), str(board_id)]})
    return {'applied': apply, 'NATIONAL_ADMIN_ORG_ID': str(national_id), 'BOARD_ORG_ID': str(board_id),
            'OVERRIDE_OLIVIA_USER_ID': str(olivia_id), 'god_candidate_id': str(candidate), 'mail_sent': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ('national_id', 'board_id', 'olivia_id', 'second_id', 'username', 'email'):
        parser.add_argument('--' + field.replace('_', '-'), required=True)
    parser.add_argument('--apply', action='store_true')
    args = vars(parser.parse_args())
    db = DatabaseManager().get_instance().get_db()
    print(json.dumps(provision(db, **args), indent=2))


if __name__ == '__main__':
    main()
