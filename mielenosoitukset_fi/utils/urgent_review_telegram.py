"""Outbound-only Telegram adapter. Never expose provider exceptions/URLs."""

import re

import requests


class DeliveryFailure(Exception):
    def __init__(self, code, *, retry_after=None, uncertain=False):
        super().__init__(code)
        self.code = code
        self.retry_after = retry_after
        self.uncertain = uncertain


class TelegramReviewTransport:
    def __init__(self, token, chat_id):
        if not isinstance(token, str) or not re.fullmatch(r"[0-9]+:[A-Za-z0-9_-]+", token):
            raise ValueError("Urgent Telegram credentials are not configured")
        self._token = token
        try:
            self.chat_id = int(chat_id)
        except (TypeError, ValueError):
            raise ValueError("Urgent Telegram target is not configured") from None
        if self.chat_id >= 0:
            raise ValueError("Urgent Telegram target must be a channel/group ID")

    def deliver(self, text, message_id=None):
        method = "editMessageText" if message_id is not None else "sendMessage"
        payload = {
            "chat_id": self.chat_id, "text": text, "parse_mode": "HTML",
            "link_preview_options": {"is_disabled": True},
        }
        if message_id is not None:
            payload["message_id"] = message_id
        try:
            response = requests.post(
                f"https://api.telegram.org/bot{self._token}/{method}",
                json=payload, timeout=(5, 15), allow_redirects=False,
            )
            body = response.json()
        except (requests.RequestException, ValueError):
            # A timeout/invalid acknowledgement may follow provider acceptance.
            # Only editing a known message is safe to repeat automatically.
            raise DeliveryFailure("unconfirmed_response", uncertain=message_id is None,
                                  retry_after=60 if message_id is not None else None) from None
        if not isinstance(body, dict):
            raise DeliveryFailure("invalid_response", uncertain=message_id is None,
                                  retry_after=60 if message_id is not None else None)
        if body.get("ok") is True:
            result = body.get("result")
            provider_id = result.get("message_id") if isinstance(result, dict) else None
            if isinstance(provider_id, int) and not isinstance(provider_id, bool) and provider_id > 0:
                if message_id is None or provider_id == message_id:
                    return provider_id
            raise DeliveryFailure("invalid_receipt", uncertain=message_id is None,
                                  retry_after=60 if message_id is not None else None)
        code = body.get("error_code", response.status_code)
        if message_id is not None and code == 400 and "message is not modified" in str(body.get("description", "")).lower():
            return message_id
        if code == 429:
            parameters = body.get("parameters")
            delay = parameters.get("retry_after") if isinstance(parameters, dict) else None
            if isinstance(delay, int) and not isinstance(delay, bool) and delay > 0:
                raise DeliveryFailure("rate_limited", retry_after=delay)
            raise DeliveryFailure("rate_limited", retry_after=60)
        if code in {400, 401, 403, 404}:
            raise DeliveryFailure("provider_rejected")
        raise DeliveryFailure("provider_unavailable", uncertain=message_id is None, retry_after=60)
