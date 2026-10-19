"""Sandbox SMTP adapter. Explicit sender profiles cannot override Mailpit."""


def delivery_settings(config, sender=None):
    if config.MAIL_SERVER != "127.0.0.1" or config.MAIL_PORT != 1025:
        raise RuntimeError("Sandbox mail must stay on loopback Mailpit")
    return {
        "sender_address": "sandbox@example.invalid",
        "smtp_server": "127.0.0.1",
        "smtp_port": 1025,
        "smtp_username": config.MAIL_USERNAME,
        "smtp_password": config.MAIL_PASSWORD,
        "use_tls": False,
    }
