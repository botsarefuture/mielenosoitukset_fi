# Mielenosoitukset.fi

Mielenosoitukset.fi is a platform for finding and submitting demonstrations in Finland. Users can browse upcoming events, submit new demonstrations, and admins can manage and approve submissions.

## Table of Contents
- [Features](#features)
- [Technologies](#technologies)
- [Getting Started](#getting-started)
- [Usage](#usage)
- [Contributing](#contributing)
- [License](#license)

## Features
- **Search**: Find demonstrations by title, location, or organizer.
- **Submit**: Allow users to submit new demonstrations with detailed information.
- **Admin Dashboard**: Admins can approve or reject demonstrations.
- **Responsive Design**: Mobile-friendly interface for easier browsing on all devices.

## Technologies
- **Flask**: Backend framework.
- **MongoDB**: Database for storing demonstration details.
- **Bootstrap**: For responsive front-end design.
- **Flask-Mail**: For sending confirmation emails (optional).

## Getting Started

### Prerequisites
- Python 3.7+
- MongoDB
- Flask

### Installation

1. Clone the repository:

    ```bash
    git clone https://github.com/botsarefuture/mielenosoitukset_fi.git
    cd mielenosoitukset_fi
    ```

2. Create a virtual environment and activate it:

    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

3. Install the required packages:

    ```bash
    pip install -r requirements.txt
    ```

4. Configure your environment variables in `config.py`:

    ```python
    class Config:
        SECRET_KEY = 'your-secret-key'
        MONGO_URI = 'mongodb://localhost:27017/your-db-name'
        MAIL_SERVER = 'smtp.yourmailserver.com'
        MAIL_PORT = 587
        MAIL_USE_TLS = True
        MAIL_USERNAME = 'your-email@example.com'
        MAIL_PASSWORD = 'your-email-password'
    ```

5. Run the application:

    ```bash
    flask run
    ```

6. Open your browser and navigate to `http://127.0.0.1:5000/`.

## Usage

### Submitting a Demonstration
1. Visit the home page and click on "Ilmoita mielenosoituksesta".
2. Fill out the form with the necessary details.
3. Submit the form to add the demonstration to the pending list.

### Searching for Demonstrations
1. Use the search bar on the home page to search for demonstrations by title, topic, or location.

### Admin Features
1. Log in as an admin to access the dashboard.
2. Approve or reject submitted demonstrations.

## Contributing

1. Fork the repository.
2. Create your feature branch: `git checkout -b feature/YourFeature`.
3. Commit your changes: `git commit -m 'Add some feature'`.
4. Push to the branch: `git push origin feature/YourFeature`.
5. Open a pull request.

## License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
