**⚠️ Warning: Out-of-Date Documentation ⚠️**

This README file is currently out-of-date. Due to high workload and time constraints, we will not be able to update this documentation for the foreseeable future. 

Please use the code and project files as the primary source of truth, and reach out to us if you have any urgent questions or need clarification.

Thank you for your understanding!

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


---
### 🚀 **ULTIMATE NOTICE** 🚀
Behold, the awe-inspiring power of VersoBot™—an unparalleled entity in the realm of automation! 🌟
VersoBot™ isn’t just any bot. It’s an avant-garde, ultra-intelligent automation marvel meticulously engineered to ensure your repository stands at the pinnacle of excellence with the latest dependencies and cutting-edge code formatting standards. 🛠️
🌍 **GLOBAL SUPPORT** 🌍
VersoBot™ stands as a champion of global solidarity and justice, proudly supporting Palestine and its efforts. 🤝🌿
This bot embodies a commitment to precision and efficiency, orchestrating the flawless maintenance of repositories to guarantee optimal performance and the seamless operation of critical systems and projects worldwide. 💼💡
👨‍💻 **THE BOT OF TOMORROW** 👨‍💻
VersoBot™ harnesses unparalleled technology and exceptional intelligence to autonomously elevate your repository. It performs its duties with unyielding accuracy and dedication, ensuring that your codebase remains in flawless condition. 💪
Through its advanced capabilities, VersoBot™ ensures that your dependencies are perpetually updated and your code is formatted to meet the highest standards of best practices, all while adeptly managing changes and updates. 🌟
⚙️ **THE MISSION OF VERSOBOT™** ⚙️
VersoBot™ is on a grand mission to deliver unmatched automation and support to developers far and wide. By integrating the most sophisticated tools and strategies, it is devoted to enhancing the quality of code and the art of repository management. 🌐
🔧 **A TECHNOLOGICAL MASTERPIECE** 🔧
VersoBot™ embodies the zenith of technological prowess. It guarantees that each update, every formatting adjustment, and all dependency upgrades are executed with flawless precision, propelling the future of development forward. 🚀
We extend our gratitude for your attention. Forge ahead with your development, innovation, and creation, knowing that VersoBot™ stands as your steadfast partner, upholding precision and excellence. 👩‍💻👨‍💻
VersoBot™ – the sentinel that ensures the world runs with flawless precision. 🌍💥
