class Sender:
    """The Sender class encapsulates the information related to an email sender, including the
    SMTP server details and the sender's email credentials.

    Parameters
    ----------

    Returns
    -------


    """

    def __init__(
        self, email_server, email_port, username, password, use_tls, email_address
    ):
        """
        Initializes a new Sender instance with the given SMTP and sender details.

        Args:
            email_server (str): The SMTP server address.
            email_port (int): The port to connect to the SMTP server.
            username (str): The username for SMTP authentication.
            password (str): The password for SMTP authentication.
            use_tls (bool): Whether to use TLS for the SMTP connection.
            email_address (str): The sender's email address.
        """
        self.email_server = email_server
        self.email_port = email_port
        self.username = username
        self.password = password
        self.use_tls = use_tls
        self.email_address = email_address

    def to_dict(self):
        """Converts the Sender instance to a dictionary format."""
        return {
            "email_server": self.email_server,
            "email_port": self.email_port,
            "username": self.username,
            "password": self.password,  # Note: Be careful with storing passwords!
            "use_tls": self.use_tls,
            "email_address": self.email_address,
        }

    @classmethod
    def from_dict(cls, data):
        """Creates a Sender instance from a dictionary.

        Parameters
        ----------
        data : dict
            A dictionary containing sender information.

        Returns
        -------


        """
        return cls(
            email_server=data.get("email_server"),
            email_port=data.get("email_port"),
            username=data.get("username"),
            password=data.get("password"),  # Make sure passwords are handled securely!
            use_tls=data.get("use_tls"),
            email_address=data.get("email_address"),
        )


class EmailJob:
    """The EmailJob class represents an email task, encapsulating all the details required to send an email.

    Parameters
    ----------
    subject : str
        The subject of the email.
    recipients : list of str
        List of recipient email addresses.
    body : str, optional
        Plain text body of the email.
    html : str, optional
        HTML content of the email.
    sender : Sender, optional
        Sender instance.
    attachments : list of dict, optional
        List of attachments, each as dict with keys: filename, content, mime_type.
    """

    def __init__(
        self, subject, recipients, body=None, html=None, sender=None, attachments=None
    ):
        """
        Initializes an EmailJob instance with the provided details.

        Args:
            subject (str): The subject of the email.
            recipients (list[str]): A list of recipient email addresses.
            body (str, optional): The plain text body of the email. Defaults to None.
            html (str, optional): The HTML content of the email. Defaults to None.
            sender (Sender, optional): An instance of the Sender class. Defaults to None.
            attachments (list[dict], optional): A list of attachments for the email. Each attachment
                should be a dictionary containing 'filename', 'content', and 'mime_type' keys.
                Defaults to None.
        """
        self.subject = subject
        self.recipients = recipients
        self.body = body
        self.html = html
        self.sender = sender  # Store a Sender instance if provided
        self.attachments = attachments or []  # Initialize attachments as an empty list if None

    def to_dict(self):
        """Converts the EmailJob instance to a dictionary format for storage in a database."""
        return {
            "subject": self.subject,
            "recipients": self.recipients,
            "body": self.body,
            "html": self.html,
            "sender": self.sender.to_dict() if self.sender else None,
            "attachments": self.attachments,
        }

    @classmethod
    def from_dict(cls, data):
        """Creates an EmailJob instance from a dictionary.

        Parameters
        ----------
        data : dict
            A dictionary containing email job details.

        Returns
        -------
        EmailJob
            The created EmailJob instance.
        """
        sender_data = data.get("sender")
        sender = Sender.from_dict(sender_data) if sender_data else None
        return cls(
            subject=data.get("subject"),
            recipients=data.get("recipients"),
            body=data.get("body"),
            html=data.get("html"),
            sender=sender,
            attachments=data.get("attachments", []),
        )
