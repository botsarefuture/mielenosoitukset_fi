from utils.logger import logger
from flask import Flask, render_template, request


def register_error_handlers(app: Flask):
    """
    Register error handlers for different HTTP error codes.

    Args:
        app (Flask): The Flask application instance to register the error handlers with.

    Handlers:
        400: Bad Request - Renders a custom 400 error page.
        401: Unauthorized - Logs the unauthorized access attempt and renders a custom 401 error page.
        403: Forbidden - Logs the forbidden access attempt and renders a custom 403 error page.
        404: Not Found - Logs the not found error and renders a custom 404 error page.
        500: Internal Server Error - Logs the internal server error and renders a custom 500 error page.
    """

    @app.errorhandler(400)
    def bad_request(error):
        """
        Handle Bad Request (400) errors.

        Args:
            error: The error object containing details of the bad request.

        Returns:
            A tuple containing the rendered template for the 400 error page and the HTTP status code 400.
        """
        return render_template("errors/400.html"), 400

    @app.errorhandler(401)
    def unauthorized(error):
        """
        Handle Unauthorized (401) errors.

        This function logs the details of the 401 Unauthorized error, including the
        request path and the remote address of the client that attempted the request.
        Optionally, it can send this data to a monitoring service.

        Args:
            error (Exception): The exception object representing the 401 error.

        Returns:
            tuple: A tuple containing the rendered 401 error template and the HTTP status code 401.
        """
        # Log the 401 error details
        logger.warning(
            f"401 Unauthorized: {request.path} attempted by {request.remote_addr}\n{error}"
        )

        # You could also send this data to a monitoring service, e.g.:
        # monitor_service.log_401_error(path=request.path, ip=request.remote_addr)

        return render_template("errors/401.html"), 401

    @app.errorhandler(403)
    def forbidden(error):
        """Handle Forbidden (403) errors."""
        logger.critical(error)
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(error):
        """Handle Not Found (404) errors."""
        logger.warning(error)
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def internal_server_error(error):
        """Handle Internal Server Error (500) errors."""
        logger.error(error)
        return render_template("errors/500.html"), 500
