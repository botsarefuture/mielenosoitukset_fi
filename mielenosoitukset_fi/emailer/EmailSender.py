import threading
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from jinja2 import Environment, FileSystemLoader
from mielenosoitukset_fi.database_manager import DatabaseManager
from .EmailJob import EmailJob
import time
from config import Config
from mielenosoitukset_fi.utils.logger import logger


class EmailSender:
    """The EmailSender class handles sending emails by processing email jobs from a queue.
    It uses SMTP to send emails and supports templated email content.

    Parameters
    ----------
    config : Config
        The configuration object for email settings.

    Returns
    -------
    None
    """

    def __init__(self, config=Config):
        """
        Initializes the EmailSender instance with the Flask app configuration.

        Parameters
        ----------
        config : Config
            The configuration object for email settings.
        """
        self._config = Config()
        self._db_manager = DatabaseManager().get_instance()
        self._db = self._db_manager.get_db()
        self._queue_collection = self._db["email_queue"]
        self._env = Environment(
            loader=FileSystemLoader("mielenosoitukset_fi/templates/emails")
        )
        self._logger = logger
        self._mailer_name = getattr(self._config, "MAILER_NAME", "MielenosoituksetMail")
        self._mailer_version = getattr(self._config, "MAILER_VERSION", "1.0")
        self.start_worker()

    def start_worker(self):
        """Starts a background thread to process the email queue.

        Returns
        -------
        None
        """
        worker_thread = threading.Thread(target=self.process_queue)
        worker_thread.daemon = True
        worker_thread.start()

    def process_queue(self):
        """Continuously processes email jobs from the queue and sends them.

        Returns
        -------
        None
        """
        while True:
            email_job_data = self._queue_collection.find_one_and_delete({})
            if email_job_data:
                email_job = EmailJob.from_dict(email_job_data)
                self.send_email(email_job)
            time.sleep(5)  # Sleep for 5 seconds before checking the queue again

    def send_email(self, email_job):
        """
        Sends an email using the details from the EmailJob instance.

        Parameters
        ----------
        email_job : EmailJob
            The EmailJob instance containing the email details.

        Returns
        -------
        None
        """
        try:
            # Determine SMTP settings and sender information
            if email_job.sender:
                sender_address = email_job.sender.email_address
                smtp_server = email_job.sender.email_server
                smtp_port = email_job.sender.email_port
                smtp_username = email_job.sender.username
                smtp_password = email_job.sender.password
                use_tls = email_job.sender.use_tls
            else:
                sender_address = self._config.MAIL_DEFAULT_SENDER
                smtp_server = self._config.MAIL_SERVER
                smtp_port = self._config.MAIL_PORT
                smtp_username = self._config.MAIL_USERNAME
                smtp_password = self._config.MAIL_PASSWORD
                use_tls = (
                    self._config.MAIL_USE_TLS or True
                )  # Default to True if not specified

            has_attachments = bool(getattr(email_job, "attachments", []))
            if has_attachments:
                msg = MIMEMultipart("mixed")
                alt_part = MIMEMultipart("alternative")
            else:
                msg = MIMEMultipart("alternative")
                alt_part = msg

            msg["Subject"] = email_job.subject
            msg["From"] = sender_address
            msg["To"] = ", ".join(email_job.recipients)
            msg["X-Mailer"] = f"{self._mailer_name}/{self._mailer_version}"

            if email_job.body:
                alt_part.attach(MIMEText(email_job.body, "plain"))
            if email_job.html:
                alt_part.attach(MIMEText(email_job.html, "html"))

            if has_attachments:
                msg.attach(alt_part)
                for attachment in email_job.attachments:
                    from email.mime.base import MIMEBase
                    from email import encoders
                    maintype, subtype = attachment["mime_type"].split("/")
                    part = MIMEBase(maintype, subtype, name=attachment["filename"])
                    part.set_payload(attachment["content"])
                    encoders.encode_base64(part)
                    part.add_header(
                        "Content-Disposition",
                        f'attachment; filename="{attachment["filename"]}"',
                    )
                    if attachment["mime_type"] == "text/calendar":
                        part.add_header(
                            "Content-Type",
                            f'text/calendar; method=REQUEST; charset=UTF-8; name="{attachment["filename"]}"'
                        )
                    else:
                        part.add_header("Content-Type", attachment["mime_type"])
                    msg.attach(part)

            with smtplib.SMTP(smtp_server, smtp_port) as server:
                if use_tls:
                    server.starttls()
                server.login(smtp_username, smtp_password)
                server.sendmail(sender_address, email_job.recipients, msg.as_string())

        except Exception as e:
            self._logger.error(f"Failed to send email: {str(e)}")
            # Optionally, requeue the email or log the error

    def queue_email(self, template_name, subject, recipients, context, sender=None, attachments=None):
        """Queues an email for sending using the provided template and context.

        Parameters
        ----------
        template_name : str
            The name of the email template file.
        subject : str
            The subject of the email.
        recipients : list[str]
            A list of recipient email addresses.
        context : dict
            A dictionary of context variables to render the email template.
        sender : Sender, optional
            An instance of the Sender class. Defaults to None.
        attachments : list[dict], optional
            List of attachments (dicts with filename, content, mime_type).

        Returns
        -------
        None
        """
        template = self._env.get_template(template_name)
        body = template.render(context)
        email_job = EmailJob(
            subject=subject, recipients=recipients, body=body, html=body, sender=sender, attachments=attachments
        )
        retry_attempts = 3
        def attempt_insert(attempt):
            try:
                self._queue_collection.insert_one(email_job.to_dict())
            except Exception as e:
                print(f"Failed to queue email: {str(e)}")  # TODO: Log the error
                if attempt < retry_attempts - 1:
                    print("Retrying in 1 hour...")
                    threading.Timer(3600, attempt_insert, [attempt + 1]).start()
                else:
                    print("Max retry attempts reached. Email not queued.")
        attempt_insert(0)

    def send_now(self, template_name, subject, recipients, context, sender=None, attachments=None):
        """Sends an email immediately using the provided template and context.

        Parameters
        ----------
        template_name : str
            The name of the email template file.
        subject : str
            The subject of the email.
        recipients : list[str]
            A list of recipient email addresses.
        context : dict
            A dictionary of context variables to render the email template.
        sender : Sender, optional
            An instance of the Sender class. Defaults to None.
        attachments : list[dict], optional
            List of attachments (dicts with filename, content, mime_type).

        Returns
        -------
        None
        """
        template = self._env.get_template(template_name)
        body = template.render(context)
        email_job = EmailJob(
            subject=subject, recipients=recipients, body=body, html=body, sender=sender, attachments=attachments
        )
        retry_attempts = 3
        def attempt_send(attempt):
            try:
                self.send_email(email_job)
            except Exception as e:
                print(
                    f"Failed to send email immediately: {str(e)}"
                )  # TODO: Log the error
                if attempt < retry_attempts - 1:
                    print("Retrying in 1 hour...")
                    threading.Timer(3600, attempt_send, [attempt + 1]).start()
                else:
                    print("Max retry attempts reached. Email not sent.")
        attempt_send(0)

    def _die_when_no_jobs(self):
        """Waits until there are no email jobs in the queue, then stops the sender.

        Returns
        -------
        bool
            True if the queue became empty and the sender should stop, False otherwise.
        """
        while self._queue_collection.count_documents({}) > 0:
            time.sleep(1)
        self._logger.info("No email jobs in the queue. Stopping EmailSender.")
        return True