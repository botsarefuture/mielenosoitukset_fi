# Mielenosoitukset.fi

Mielenosoitukset.fi is an open-source platform for discovering and submitting demonstrations in Finland. Users can browse upcoming events, submit new demonstrations, and administrators can manage and approve submissions. The project is actively maintained and welcomes new contributors — see the Contributing section below for how to help.

---

- [Features](#features)
- [Technologies](#technologies)
- [Getting Started](#getting-started)
- [Usage](#usage)
- [Contributing](#contributing)
- [License](#license)
- [Translating](#translating)

---

## Features

- **Search:** Easily find demonstrations by title, location, or organizer.
- **Submit:** Users can submit new demonstrations with detailed event information.
- **Admin Dashboard:** Admins can approve, reject, or manage submitted demonstrations.
- **Responsive Design:** Mobile-friendly, ensuring a seamless browsing experience on all devices.

---

## Technologies

- **Flask**: A lightweight backend framework for Python.
- **MongoDB**: A NoSQL database for storing event details and user submissions.
- **Bootstrap**: For a mobile-first, responsive front-end design.
- **Flask-Mail**: For sending email notifications (optional, based on configuration).
- **Jinja2**: For dynamic templating in Flask.

---

## Getting Started

### Prerequisites

To run this project locally you'll typically need:

- Python 3.10+ (3.11 recommended)
- MongoDB (or a compatible hosted MongoDB URI)
- Flask
- Project dependencies (installable via `requirements.txt`)

### Installation

1. Clone the repository:

    ```bash
    git clone https://github.com/botsarefuture/mielenosoitukset_fi.git
    cd mielenosoitukset_fi
    ```

2. Create and activate a virtual environment:

    ```bash
    python3 -m venv venv
    source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
    ```

3. Install the required packages:

    ```bash
    pip install -r requirements.txt
    ```


4. Configure your environment variables. The project uses `config.py` and `config.yaml` for configuration; a simple example would be:

    ```python
    class Config:
        SECRET_KEY = 'your-secret-key'  # Set this to a secure, random value
        MONGO_URI = 'mongodb://localhost:27017/your-db-name'  # Replace with your MongoDB URI
        MAIL_SERVER = 'smtp.yourmailserver.com'
        MAIL_PORT = 587
        MAIL_USE_TLS = True
        MAIL_USERNAME = 'your-email@example.com'
        MAIL_PASSWORD = 'your-email-password'
    ```

5. Run the application. You can start the app either with Flask or by running the project's runner:

    ```bash
    # Option A: use the flask CLI
    export FLASK_APP=run.py
    flask run

    # Option B: run the bundled runner directly
    python3 run.py
    ```

6. Open your browser and navigate to [http://127.0.0.1:5000/](http://127.0.0.1:5000/) to start using the platform.

### Run with Docker (development-only)

A lightweight Docker Compose setup is included for local development. It starts MongoDB, seeds development data, and runs the Flask app in debug mode.

1. Build and start the stack:

   ```bash
   docker-compose -f docker-compose.dev.yml up --build
   ```

   This will also run a one-time seeding job that creates an admin user (`admin` / `admin`) and a handful of sample demonstrations.

2. Visit the app at [http://localhost:5000](http://localhost:5000).

The Compose file mounts `docker/config.dev.yaml` as `config.yaml` inside the container so you can tweak connection strings or ports without touching your local configuration.

---

## Usage

### Submitting a Demonstration

1. Visit the home page and click the “Ilmoita mielenosoituksesta” button to begin.
2. Fill out the form with details about the demonstration (location, time, description, etc.).
3. Submit the form to add your demonstration to the pending list.

### Searching for Demonstrations

1. Use the search bar on the homepage to search for upcoming demonstrations by title, topic, or location.
   
### Admin Features

1. Admins can log in to access the admin dashboard and manage submissions.
2. Admins can approve, reject, or edit submitted demonstrations directly from the dashboard.

---

## Contributing

We welcome contributions to Mielenosoitukset.fi! Please follow these steps to contribute:

1. Fork the repository.
2. Create a new branch for your feature:  
   `git checkout -b feature/YourFeature`
3. Commit your changes:  
   `git commit -m 'Add some feature'`
4. Push to your forked repository:  
   `git push origin feature/YourFeature`
5. Open a pull request on the main repository.

We will review and merge your changes after testing.

> [!NOTE](Contributing)
> We're actively looking for new contributors!
>
> If you'd like to help — whether with code, translations, documentation, testing, design, or moderation — please get in touch. You can:
>
> - Open an issue or a pull request on GitHub to start a discussion.
- Reach out directly to Emilia at emilia@mielenosoitukset.fi to talk about ways to contribute or to be added to the contributor channels.

Suggested first tasks:

- Fix small bugs or typos in the docs
- Add or improve tests and CI
- Help translate the UI (see `TRANSLATING.md`)
- Improve the admin moderation flow or onboarding docs

---

## Translating

For translation guidelines, please refer to the [TRANSLATING.md][translations] file.

---

## License

This project is licensed under the Apache License, Version 2.0. See the [LICENSE](LICENSE) file for more information.

[translations]: TRANSLATING.md
---

## Contact

If you have any questions, suggestions, or feedback, feel free to reach out to us:

- Email: tuki@mielenosoitukset.fi
- Email: emilia@mielenosoitukset.fi (for contributor enquiries)

- GitHub Issues: [https://github.com/botsarefuture/mielenosoitukset_fi/issues](https://github.com/botsarefuture/mielenosoitukset_fi/issues)

We appreciate your input and support!

---

## Changelog

See the [CHANGELOG.md](CHANGELOG.md) file for details on the latest updates and changes to the project.