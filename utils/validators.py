import re
from utils.variables import EVENT_TYPES

def valid_email(email):
    """Check if the given email address is valid.
    
    Args:
        email (str): The email address to validate.
    
    Returns:
        bool: True if the email is valid, False otherwise.
    
    Changelog:
    ----------
    v2.4.0:
        - Added this function.

    Parameters
    ----------
    email :
        

    Returns
    -------

    
    """
    # Regular expression for validating an email
    email_regex = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return re.match(email_regex, email) is not None

def valid_event_type(event_type):
    """Check if the given event type is valid.
    
    Args:
        event_type (str): The event type to validate.
    
    Returns:
        bool: True if the event type is valid, False otherwise.
    
    Changelog:
    ----------
    v2.6.0:
        - Added this function.

    Parameters
    ----------
    event_type :
        

    Returns
    -------

    
    """
    return event_type in EVENT_TYPES

def return_exists(var1, var2, default=None):
    """

    Parameters
    ----------
    var1 :
        param var2:
    default :
        Default value = None)
    var2 :
        

    Returns
    -------

    
    """
    if var1 and var2:
        return var1, var2
    
    elif var1 and not var2:
        return var1, var1
    
    elif var2 and not var1:
        return var2, var2
    
    else:
        return default, default