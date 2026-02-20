
# Local development with Docker Compose

Local development depends on following tools:
- Caddy as reverse proxy and TLS certificate provider (using Caddy's local CA)
- LocalStack to provide a local non-persistent AWS environment (just S3 for now)
- reachfive/fake-smtp-server (might change) to provide a local SMTP server for testing email sending

Configuration for backend is in `config.compose.dev.yaml` and mounted as volume mount to the backend container.


## Initial setup
The following steps will set up the necessary environment for local development:

1. Install Docker and Docker Compose on your machine.
2. Clone the repository and navigate to the project directory.
3. Edit `/etc/hosts` file to point `miekkari.localhost` to `127.0.0.1` by adding line:
    ```
    127.0.0.1	miekkari.localhost
    ```
4. Run the following command to start the necessary services:
    ```
    docker compose -f docker-compose.dev.yml up
    ```
5. Wait for services to start up. Get root certificate from Caddy and add it to your system's trusted certificates (Caddy will print instructions on how to do this in the terminal, 
   or check https://caddyserver.com/docs/running#local-https-with-docker) and possibly your browser's trusted certificates as well.
6. Open your browser to access the application
 - `https://miekkari.localhost` goes landing page, do submit a demonstration
 - `http://localhost:1080/` to access the fake SMTP server interface, see email was sent to organizer and admin
 - `https://miekkari.localhost/admin/demo/` to access the admin interface (TODO: create admin user)

NOTE: most services expose default port, so if you have other services running on those ports, you might need to stop them or change the port mappings in `compose.dev.yml`.
