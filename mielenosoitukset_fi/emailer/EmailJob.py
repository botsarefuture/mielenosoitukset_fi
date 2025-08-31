import uuid


class Sender:
    """Encapsulates SMTP server details and credentials for an email sender."""

    def __init__(self, email_server, email_port, username, password, use_tls, email_address):
        self.email_server = email_server
        self.email_port = email_port
        self.username = username
        self.password = password
        self.use_tls = use_tls
        self.email_address = email_address

    def to_dict(self):
        return {
            "email_server": self.email_server,
            "email_port": self.email_port,
            "username": self.username,
            "password": self.password,  # ⚠️ Be careful storing raw passwords!
            "use_tls": self.use_tls,
            "email_address": self.email_address,
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            email_server=data.get("email_server"),
            email_port=data.get("email_port"),
            username=data.get("username"),
            password=data.get("password"),
            use_tls=data.get("use_tls"),
            email_address=data.get("email_address"),
        )


class EmailJob:
    """Represents an email task, encapsulating everything needed to send an email.

    Parameters
    ----------
    subject : str
        The subject of the email.
    recipients : list of str
        Recipient email addresses.
    body : str, optional
        Plain text body of the email.
    html : str, optional
        HTML body of the email.
    sender : Sender, optional
        Sender instance.
    attachments : list of dict, optional
        Attachments, each with 'filename', 'content', and 'mime_type'.
    extra_headers : dict, optional
        Additional email headers to include.
    instance_id : str, optional
        ID of the instance that queued this job.
    """

    def __init__(
        self,
        subject,
        recipients,
        body=None,
        html=None,
        sender=None,
        attachments=None,
        extra_headers=None,
        instance_id=None,
    ):
        self.subject = subject
        self.recipients = recipients
        self.body = body
        self.html = html
        self.sender = sender
        self.attachments = attachments or []
        self.extra_headers = extra_headers or {}
        self.instance_id = instance_id or str(uuid.uuid4())  # default to a unique ID

    def to_dict(self):
        """Convert the job into a serializable dict for MongoDB storage."""
        return {
            "subject": self.subject,
            "recipients": self.recipients,
            "body": self.body,
            "html": self.html,
            "sender": self.sender.to_dict() if self.sender else None,
            "attachments": self.attachments,
            "extra_headers": self.extra_headers,
            "instance_id": self.instance_id,
        }

    @classmethod
    def from_dict(cls, data):
        sender_data = data.get("sender")
        sender = Sender.from_dict(sender_data) if sender_data else None
        return cls(
            subject=data.get("subject"),
            recipients=data.get("recipients"),
            body=data.get("body"),
            html=data.get("html"),
            sender=sender,
            attachments=data.get("attachments", []),
            extra_headers=data.get("extra_headers", {}),
            instance_id=data.get("instance_id"),
        )
