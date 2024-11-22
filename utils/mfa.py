import pyotp
from users.models import User

from bson.objectid import ObjectId
from database_manager import DatabaseManager

class MFA:
    """ """
    def __init__(self, user=None):
        if isinstance(user, dict):
            self.user = User.from_db(user)
        elif isinstance(user, User):
            self.user = user
        elif isinstance(user, ObjectId):
            user = User.from_db(DatabaseManager().get_instance().get_db().users.find_one({"_id": user}))
        else:
            raise ValueError("User must be a User object, a dict, or an ObjectId")

        self.db = DatabaseManager().get_instance().get_db()
        self.secrets = self.load_secrets()

    def load_secrets(self):
        """ """
        mfas = self.db.mfas.find({"user_id": self.user.id})
        return [mfa["secret"] for mfa in mfas]

    def check_for_mfa(self):
        """ """
        return self.user.mfa_enabled

    def enable_mfa(self):
        """ """
        self.user.mfa_enabled = True
        new_secret = pyotp.random_base32()
        self.db.mfas.insert_one({"user_id": self.user.id, "secret": new_secret})
        self.secrets.append(new_secret)
        self.user.save()

    def disable_mfa(self):
        """ """
        self.user.mfa_enabled = False
        self.db.mfas.delete_many({"user_id": self.user.id})
        self.secrets = []
        self.user.save()

    def get_mfa_uri(self, secret):
        """

        Parameters
        ----------
        secret :
            

        Returns
        -------

        
        """
        return pyotp.totp.TOTP(secret).provisioning_uri(name=self.user.username, issuer_name="Mielenosoitukset.fi")

    def verify_mfa(self, token):
        """

        Parameters
        ----------
        token :
            

        Returns
        -------

        
        """
        for secret in self.secrets:
            if pyotp.TOTP(secret).verify(token):
                return True
        return False

    def get_secrets(self):
        """ """
        return self.secrets