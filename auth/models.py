from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from bson.objectid import ObjectId


class User(UserMixin):
    def __init__(
        self,
        user_id,
        username,
        password_hash,
        email=None,
        displayname=None,
        profile_picture=None,
        bio=None,
        followers=None,
        following=None,
        organizations=None,
        global_admin=False,
        confirmed=False,
        permissions=None,
        global_permissions=None,  # Added global permissions
        role=None,
    ):
        self.id = str(user_id)
        self.username = username
        self.email = email
        self.password_hash = password_hash
        self.displayname = displayname
        self.profile_picture = profile_picture
        self.bio = bio
        self.followers = followers or []
        self.following = following or []
        self.organizations = organizations or []
        self.global_admin = global_admin
        self.confirmed = confirmed
        self.permissions = permissions or {}
        self.global_permissions = global_permissions or []  # Ensure it's a list
        self.role = role or "member"

    @staticmethod
    def from_db(user_doc):
        """
        Create a User instance from a database document.
        """
        global_admin = user_doc.get("global_admin", False)
        if user_doc.get("role") == "global_admin":
            global_admin = True

        return User(
            user_id=user_doc["_id"],
            username=user_doc["username"],
            email=user_doc.get("email", None),
            password_hash=user_doc["password_hash"],
            displayname=user_doc.get("displayname", None),
            profile_picture=user_doc.get("profile_picture", None),
            bio=user_doc.get("bio", None),
            followers=user_doc.get("followers", []),
            following=user_doc.get("following", []),
            organizations=user_doc.get("organizations", []),
            global_admin=global_admin,
            confirmed=user_doc.get("confirmed", False),
            permissions=user_doc.get("permissions", {}),
            global_permissions=user_doc.get(
                "global_permissions", []
            ),  # Fetch global permissions
            role=user_doc.get("role", "member"),
        )

    def check_password(self, password):
        """
        Verify the provided password against the stored password hash.
        """
        return check_password_hash(self.password_hash, password)

    @staticmethod
    def create_user(
        username, password, email, displayname=None, profile_picture=None, bio=None
    ):
        """
        Create a new user dictionary with a hashed password.
        """
        password_hash = generate_password_hash(password)
        return {
            "username": username,
            "password_hash": password_hash,
            "email": email,
            "displayname": displayname,
            "profile_picture": profile_picture,
            "bio": bio,
            "followers": [],
            "organizations": [],
            "global_admin": False,
            "confirmed": False,
            "permissions": [],
            "global_permissions": [],  # Initialize global permissions,
            "following": [],
        }

    def add_organization(self, db, organization_id, role="member", permissions=None):
        """
        Add or update an organization for the user, including role and permissions.
        """
        existing_org = next(
            (org for org in self.organizations if org["org_id"] == organization_id),
            None,
        )

        if not existing_org:
            self.organizations.append(
                {
                    "org_id": organization_id,
                    "role": role,
                    "permissions": permissions or [],
                }
            )
        else:
            existing_org["role"] = role
            existing_org["permissions"] = permissions or existing_org.get(
                "permissions", []
            )

        # Ensure atomicity during the database update
        db.users.update_one(
            {"_id": ObjectId(self.id)},
            {"$set": {"organizations": self.organizations}},
        )

    def is_member_of_organization(self, organization_id):
        """
        Check if the user is a member of a specific organization.
        """
        return any(org["org_id"] == str(organization_id) for org in self.organizations)

    def change_password(self, db, new_password):
        """
        Change the user's password and update the database.
        """
        new_password_hash = generate_password_hash(new_password)
        self.password_hash = new_password_hash

        # Update the password hash in the database
        db.users.update_one(
            {"_id": ObjectId(self.id)}, {"$set": {"password_hash": self.password_hash}}
        )
        print("Password updated successfully.")

    def update_displayname(self, db, displayname):
        """
        Update the user's display name and database record.
        """
        self.displayname = displayname
        db.users.update_one(
            {"_id": ObjectId(self.id)}, {"$set": {"displayname": self.displayname}}
        )
        print("Display name updated successfully.")

    def update_profile_picture(self, db, profile_picture):
        """
        Update the user's profile picture and database record.
        """
        self.profile_picture = profile_picture
        db.users.update_one(
            {"_id": ObjectId(self.id)},
            {"$set": {"profile_picture": self.profile_picture}},
        )
        print("Profile picture updated successfully.")

    def update_bio(self, db, bio):
        """
        Update the user's bio and database record.
        """
        self.bio = bio
        db.users.update_one({"_id": ObjectId(self.id)}, {"$set": {"bio": self.bio}})
        print("Bio updated successfully.")

    def follow_user(self, db, user_id_to_follow):
        """
        Add a user to the followers list of this user.
        """
        if user_id_to_follow not in self.following:
            self.following.append(user_id_to_follow)
            db.users.update_one(
                {"_id": ObjectId(self.id)},
                {"$set": {"following": self.following}},
            )
            print("Started following user successfully.")

    def unfollow_user(self, db, user_id_to_unfollow):
        """
        Remove a user from the followers list of this user.
        """
        if user_id_to_unfollow in self.following:
            self.following.remove(user_id_to_unfollow)
            db.users.update_one(
                {"_id": ObjectId(self.id)},
                {"$set": {"following": self.following}},
            )
            print("Stopped following user successfully.")

    def has_permission(self, organization_id, permission):
        """
        Check if the user has a specific permission in a given organization or globally.
        """
        # Check global permissions first
        if permission in self.global_permissions:
            return True

        # Check organization-specific permissions
        for org in self.organizations:
            if org["org_id"] == str(organization_id):
                return permission in org.get("permissions", [])

        return False

    def is_following(self, user_id):
        """Check if this user is following another user."""
        if isinstance(user_id, User):
            user_id = user_id.id

        return user_id in self.following

    def __repr__(self):
        return f"<User(username={self.username}, email={self.email}, global_admin={self.global_admin})>"
