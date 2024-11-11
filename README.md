# ⚠️ **Warning: Out-of-Date Documentation** ⚠️

**This README file is currently out-of-date.**  
Due to high workload and time constraints, we will not be able to update this documentation in the near future. 

**Please use the code and project files as the primary source of truth**. If you have any urgent questions or need clarification, feel free to reach out to us.

Thank you for your understanding!

---

# Mielenosoitukset.fi

Mielenosoitukset.fi is an open-source platform for discovering and submitting demonstrations in Finland. Users can browse upcoming events, submit new demonstrations, and administrators can manage and approve submissions.

---

## Table of Contents

- [⚠️ Warning: Out-of-Date Documentation](#️-warning-out-of-date-documentation)
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

To run this project, you’ll need the following installed:

- Python 3.7+
- MongoDB
- Flask
- Any required dependencies, which can be installed via `requirements.txt`.

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

4. Configure your environment variables in `config.py`:

    ```python
    class Config:
        SECRET_KEY = 'your-secret-key'  # Set this to a secure, random value
        MONGO_URI = 'mongodb://localhost:27017/your-db-name'  # Replace with your MongoDB URI
        MAIL_SERVER = 'smtp.yourmailserver.com'  # Use your mail server details
        MAIL_PORT = 587
        MAIL_USE_TLS = True
        MAIL_USERNAME = 'your-email@example.com'
        MAIL_PASSWORD = 'your-email-password'
    ```

5. Run the application:

    ```bash
    flask run
    ```

6. Open your browser and navigate to [http://127.0.0.1:5000/](http://127.0.0.1:5000/) to start using the platform.

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

---

## Translating

> **HOX**: this has been transferred:
[TRANSLATING.md][translations]



## License

This project is licensed under the Apache License, Version 2.0. See the [LICENSE](LICENSE) file for more information.

Copyright 2024 Verso Vuorenmaa

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.

[translations]: TRANSLATING.md
