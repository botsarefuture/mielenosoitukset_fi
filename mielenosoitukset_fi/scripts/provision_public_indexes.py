"""Provision public query indexes explicitly, before application worker reload."""

from mielenosoitukset_fi.database_manager import DatabaseManager
from mielenosoitukset_fi.utils.public_pagination import ensure_public_demo_pagination_index


def main():
    """Fail deployment on provisioning errors without interrupting old workers."""
    ensure_public_demo_pagination_index(DatabaseManager.get_instance().get_db())


if __name__ == "__main__":
    main()
