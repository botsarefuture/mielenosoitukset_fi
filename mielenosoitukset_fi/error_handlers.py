from mielenosoitukset_fi.utils.logger import logger
from flask import Flask, render_template, request


def register_error_handlers(app: Flask):
    """

    Parameters
    ----------
    app : Flask :

    app: Flask :


    Returns
    -------


    """

    @app.errorhandler(400)
    def bad_request(error):
        """Handle Bad Request (400) errors.

        Parameters
        ----------
        error :
            The error object containing details of the bad request.

        Returns
        -------


        """
        return render_template("errors/400.html"), 400

    @app.errorhandler(401)
    def unauthorized(error):
        """Handle Unauthorized (401) errors.

        This function logs the details of the 401 Unauthorized error, including the
        request path and the remote address of the client that attempted the request.
        Optionally, it can send this data to a monitoring service.

        Parameters
        ----------
        error : Exception
            The exception object representing the 401 error.

        Returns
        -------


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
        """Handle Forbidden (403) errors.

        Parameters
        ----------
        error :


        Returns
        -------


        """
        logger.critical(error)
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(error):
        """Handle Not Found (404) errors.

        Parameters
        ----------
        error :


        Returns
        -------


        """
        logger.warning(error)
        return render_template("errors/404.html"), 404

    @app.errorhandler(429)
    def too_many_requests(error):
        """Handle Too Many Requests (429) errors.

        Parameters
        ----------
        error :


        Returns
        -------


        """
        logger.warning(error)
        return render_template("errors/429.html"), 429

    @app.errorhandler(500)
    def internal_server_error(error):
        """Handle Internal Server Error (500) errors.

        Parameters
        ----------
        error :


        Returns
        -------


        """
        logger.error(error)
        return render_template("errors/500.html"), 500
