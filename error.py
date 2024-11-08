from flask import Flask, render_template


def register_error_handlers(app: Flask):
    """Register error handlers for different HTTP error codes."""

    @app.errorhandler(400)
    def bad_request(error):
        """Handle Bad Request (400) errors."""
        return render_template("errors/400.html"), 400

    @app.errorhandler(401)
    def unauthorized(error):
        """Handle Unauthorized (401) errors."""
        return render_template("errors/401.html"), 401

    @app.errorhandler(403)
    def forbidden(error):
        """Handle Forbidden (403) errors."""
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(error):
        """Handle Not Found (404) errors."""
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def internal_server_error(error):
        """Handle Internal Server Error (500) errors."""
        return render_template("errors/500.html"), 500
