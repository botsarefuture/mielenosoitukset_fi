import jwt
import datetime
from flask import current_app

def generate_reset_token(email):
    """

    Parameters
    ----------
    email :
        

    Returns
    -------

    
    """
    return jwt.encode(
        {
            "email": email,
            "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=1),
        },
        current_app.config["SECRET_KEY"],
        algorithm="HS256",
    )


def verify_reset_token(token):
    """

    Parameters
    ----------
    token :
        

    Returns
    -------

    
    """
    try:
        data = jwt.decode(token, current_app.config["SECRET_KEY"], algorithms=["HS256"])
        return data["email"]
    except Exception:
        return None


def generate_confirmation_token(email):
    """

    Parameters
    ----------
    email :
        

    Returns
    -------

    
    """
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
    """
    Verify the confirmation token.
    
    This function decodes the provided token using the application's secret key and the HS256 algorithm.
    If the token is valid, it returns the email address associated with the token. Otherwise, it returns None.
    
    Parameters
    ----------
    token : str
        The confirmation token to be verified.
        
    Returns
    -------
    str or None
        The email address associated with the token if the token is valid, otherwise None.
    
    Raises
    ------
    jwt.ExpiredSignatureError
        If the token has expired.
        
    jwt.InvalidTokenError
        If the token is invalid.
    """
    
    try:
        data = jwt.decode(token, current_app.config["SECRET_KEY"], algorithms=["HS256"])
        return data["email"]
    except Exception:
        return None
