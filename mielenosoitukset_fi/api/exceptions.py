class Message:
    def __init__(self, message: str, code: str):
        """
        Represents an error message.

        Parameters
        ----------
        message : str
            A human-readable description of the error.
        code : str
            A machine-readable error code.
        """
        self.message = message  # Human-readable
        self.code = code        # Machine-readable

    def to_dict(self) -> dict:
        """
        Converts the Message instance to a dictionary.

        Returns
        -------
        dict
            A dictionary representation of the Message.
        """
        return {
            "message": self.message,
            "code": self.code
        }

    def __str__(self) -> str:
        """
        Returns a string representation of the Message.

        Returns
        -------
        str
            A string containing the error code and message.
        """
        return f"{self.code}: {self.message}"


class ApiException(Exception):
    """
    Custom exception class for API errors.

    Attributes
    ----------
    message : Message
        An instance of the Message class containing error details.
    status_code : int
        The HTTP status code associated with the error.
    """

    def __init__(self, message: Message, status_code: int):
        """
        Initializes an ApiException.

        Parameters
        ----------
        message : Message
            The error message object.
        status_code : int
            The HTTP status code associated with the error.
        """
        self.message = message
        self.status_code = status_code

    def to_dict(self) -> dict:
        """
        Converts the ApiException to a dictionary.

        Returns
        -------
        dict
            A dictionary representation of the error, including the message and status code.
        """
        return {
            "error": self.message.to_dict(),
            "status_code": self.status_code
        }

    def __str__(self) -> str:
        """
        Returns a string representation of the ApiException.

        Returns
        -------
        str
            A string containing the status code and the error message.
        """
        return f"{self.status_code}: {self.message}"


class BadRequestException(ApiException):
    """
    Exception for a 400 Bad Request error.
    """
    def __init__(self, message: Message):
        super().__init__(message, 400)


class DemoNotFoundException(ApiException):
    """
    Exception for a 404 Not Found error for demonstrations.
    """
    def __init__(self):
        message = Message(
            "Mielenosoitusta ei löytynyt tai sitä ei ole vielä hyväksytty.",
            "demo_not_found"
        )
        super().__init__(message, 404)


class DemoNotApprovedException(ApiException):
    """
    Exception for a 403 Forbidden error when a demonstration is not approved.
    """
    def __init__(self):
        message = Message(
            "Mielenosoitusta ei ole vielä hyväksytty.",
            "demo_not_approved"
        )
        super().__init__(message, 403)
