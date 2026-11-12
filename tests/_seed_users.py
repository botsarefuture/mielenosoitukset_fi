"""Reuse expensive, real user templates only for synthetic test fixtures."""
from copy import deepcopy
from functools import lru_cache


@lru_cache(maxsize=32)
def _user_template(username, email, password, displayname):
    from mielenosoitukset_fi.users.models import User

    # Use the production constructor and password algorithm. Never patch hashing
    # or verification: authentication tests continue exercising the real code.
    return User.create_user(
        username=username, password=password, email=email, displayname=displayname
    )


def seed_user_document(username, email, password, displayname):
    """Return a fresh document; Mongo IDs and nested mutations cannot leak back."""
    return deepcopy(_user_template(username, email, password, displayname))
