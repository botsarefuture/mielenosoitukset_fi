import jwt
import datetime
from flask import current_app

def generate_reset_token(email):
    return jwt.encode(
        {
            "email": email,
            "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=1),
        },
        current_app.config["SECRET_KEY"],
        algorithm="HS256",
    )


def verify_reset_token(token):
    try:
        data = jwt.decode(token, current_app.config["SECRET_KEY"], algorithms=["HS256"])
        return data["email"]
    except Exception:
        return None


def generate_confirmation_token(email):
    return jwt.encode(
        {
            "email": email,
            "exp": datetime.datetime.utcnow()
            + datetime.timedelta(hours=1),  # Korjattu rivi
        },
        current_app.config["SECRET_KEY"],
        algorithm="HS256",
    )


def verify_confirmation_token(token):
    try:
        data = jwt.decode(token, current_app.config["SECRET_KEY"], algorithms=["HS256"])
        return data["email"]
    except Exception:
        return None
