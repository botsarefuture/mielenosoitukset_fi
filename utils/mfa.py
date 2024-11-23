import pyotp
from bson.objectid import ObjectId
from database_manager import DatabaseManager
from users.models import User


class MFA:
    """
    A class to manage Multi-Factor Authentication (MFA) for users.

    This class provides methods to enable, disable, and verify MFA for a user, as well as to load and manage MFA secrets.

    Parameters
    ----------
    user : User, dict, or ObjectId
        The user for whom MFA is being managed. This can be a User object, a dictionary representing the user, or an ObjectId of the user.

    Raises
    ------
    ValueError
        If the user parameter is not a User object, a dict, or an ObjectId.
    """

    def __init__(self, user=None):
        if isinstance(user, dict):
            self.user = User.from_db(user)
        elif isinstance(user, User):
            self.user = user
        elif isinstance(user, ObjectId):
            user = User.from_db(
                DatabaseManager().get_instance().get_db().users.find_one({"_id": user})
            )
        else:
            raise ValueError("User must be a User object, a dict, or an ObjectId")

        self.db = DatabaseManager().get_instance().get_db()
        self.secrets = self.load_secrets()

    def load_secrets(self):
        """
        Load MFA secrets for the user from the database.

        Returns
        -------
        list
            A list of MFA secrets for the user.
        """
        mfas = self.db.mfas.find({"user_id": self.user.id})
        return [mfa["secret"] for mfa in mfas]

    def check_for_mfa(self):
        """
        Check if MFA is enabled for the user.

        Returns
        -------
        bool
            True if MFA is enabled, False otherwise.
        """
        return self.user.mfa_enabled

    def enable_mfa(self):
        """
        Enable MFA for the user.

        This method generates a new MFA secret, stores it in the database, and enables MFA for the user.
        """
        self.user.mfa_enabled = True
        new_secret = pyotp.random_base32()
        self.db.mfas.insert_one({"user_id": self.user.id, "secret": new_secret})
        self.secrets.append(new_secret)
        self.user.save()

    def disable_mfa(self):
        """
        Disable MFA for the user.

        This method removes all MFA secrets from the database and disables MFA for the user.
        """
        self.user.mfa_enabled = False
        self.db.mfas.delete_many({"user_id": self.user.id})
        self.secrets = []
        self.user.save()

    def get_mfa_uri(self, secret):
        """
        Get the MFA provisioning URI for a given secret.

        Parameters
        ----------
        secret : str
            The MFA secret.

        Returns
        -------
        str
            The provisioning URI for the given secret.
        """
        return pyotp.totp.TOTP(secret).provisioning_uri(
            name=self.user.username, issuer_name="Mielenosoitukset.fi"
        )

    def verify_mfa(self, token):
        """
        Verify an MFA token.

        Parameters
        ----------
        token : str
            The MFA token to verify.

        Returns
        -------
        bool
            True if the token is valid for any of the user's secrets, False otherwise.
        """
        for secret in self.secrets:
            if pyotp.TOTP(secret).verify(token):
                return True
        return False

    def get_secrets(self):
        """
        Get the MFA secrets for the user.

        Returns
        -------
        list
            A list of MFA secrets for the user.
        """
        return self.secrets
