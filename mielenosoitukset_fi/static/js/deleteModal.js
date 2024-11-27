// Flag to indicate if fast delete mode is active
let fastDeleteMode = false;

// Enable fast delete mode when the Shift key is pressed
document.addEventListener('keydown', (event) => {
    if (event.key === 'Shift') {
        fastDeleteMode = true;
        updateDeleteButtonTexts(); // Update button texts on Shift press
        log('Fast delete mode enabled.'); // Logging
    }

    // Close the modal when the Escape key is pressed
    if (event.key === 'Escape') {
        closeModal(); // Call closeModal function to hide the modal
        log('Modal closed using Escape key.'); // Logging
    }
});

// Disable fast delete mode when the Shift key is released
document.addEventListener('keyup', (event) => {
    if (event.key === 'Shift') {
        fastDeleteMode = false;
        updateDeleteButtonTexts(); // Update button texts on Shift release
        log('Fast delete mode disabled.'); // Logging
    }
});

// Open modal or execute fast delete action
function openModal(event, title, _id, type = 'demo') {
    event.preventDefault(); // Prevent the default action, like opening a link
    log(`Attempting to open modal for ${type} ID: ${_id}`); // Logging
    if (fastDeleteMode) {
        if (type === 'demo') {
            removeDemo(_id); // Call the remove function for fast delete mode
        } else if (type === 'user') {
            removeUser(_id); // Call the remove function for fast delete mode
        } else if (type === 'organization') {
            removeComment(_id); // Call the remove function for fast delete mode
        } else if (type === 'recurring_demo') {
            removeRecurringDemo(_id); // Call the remove function for fast delete mode
        } else {
            console.error('Error: Invalid type for fast delete mode.'); // Log error to the console
            alert(`Virhe poistaessa. ${type} ei ole olemassa.`); // General error message
            log(`Failed to delete ${type} ID ${_id}. Error: Invalid type for fast delete mode.`); // Logging
        }

    } else {
        // Display the modal with demo title

        if (type === 'demo') {
        document.getElementById('demoTitle').textContent = title;
        document.getElementById('confirmDelete').setAttribute('data-demo-id', _id);
        document.getElementById('deleteModal').classList.remove('hidden');
        log(`Opened modal for demo: ${demoTitle}`); // Logging
        } else if (type === 'user') {
        document.getElementById('userTitle').textContent = title;
        document.getElementById('confirmDelete').setAttribute('data-user-id', _id);
        document.getElementById('deleteModal').classList.remove('hidden');
        log(`Opened modal for user: ${userTitle}`); // Logging
        } else if (type === 'organization') {
        document.getElementById('organizationTitle').textContent = organizationTitle;
        document.getElementById('confirmDelete').setAttribute('data-organization-id', organizationId);
        document.getElementById('deleteModal').classList.remove('hidden');
        log(`Opened modal for organization: ${organizationTitle}`); // Logging
        } else if (type === 'recurring_demo') {
        document.getElementById('recurringDemoTitle').textContent = title;
        document.getElementById('confirmDelete').setAttribute('data-recurring-demo-id', _id);
        document.getElementById('deleteModal').classList.remove('hidden');
        log(`Opened modal for recurring demo: ${recurringDemoTitle}`); // Logging
        }

        // Event listener for the confirm delete button
        document.getElementById('confirmDelete').addEventListener('click', function () {
            if (type === 'demo') {
                const demoId = this.getAttribute('data-demo-id');
                log(`Confirming deletion for demo ID: ${demoId}`); // Logging
                removeDemo(demoId); // Execute the remove function on button click
            }

            if (type === 'user') {
                const userId = this.getAttribute('data-user-id');
                log(`Confirming deletion for user ID: ${userId}`); // Logging
                removeUser(userId); // Execute the remove function on button click
            }

            if (type === 'organization') {
                const organizationId = this.getAttribute('data-organization-id');
                log(`Confirming deletion for organization ID: ${organizationId}`); // Logging
                removeOrganization(organizationId); // Execute the remove function on button click
            }

            if (type === 'recurring_demo') {
                const recurringDemoId = this.getAttribute('data-recurring-demo-id');
                log(`Confirming deletion for recurring demo ID: ${recurringDemoId}`); // Logging
                removeRecurringDemo(recurringDemoId); // Execute the remove function on button click
            }
        });


    }
}

// Remove the demonstration by sending a delete request
function removeDemo(demoId) {
    log(`Sending delete request for demo ID: ${demoId}`); // Logging
    fetch("/admin/demo/delete_demo", {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ demo_id: demoId }),
        redirect: 'manual'
    })
        .then(response => response.json().then(data => {
            if (response.ok) {
                // Remove the demo row from the table and close the modal
                document.getElementById('demo-' + demoId).remove();
                closeModal();
                alert(data.status || 'Mielenosoitus poistettu onnistuneesti.'); // Success message
                log(`Successfully deleted demo ID: ${demoId}`); // Logging
            } else {
                alert(data.status || 'Virhe mielenosoituksen poistossa.'); // Error message
                log(`Error deleting demo ID ${demoId}: ${data.status}`); // Logging error
            }
        }))
        .catch(error => {
            console.error('Error:', error); // Log error to the console
            alert('Virhe mielenosoituksen poistossa.'); // General error message
            log(`Failed to delete demo ID ${demoId}. Error: ${error}`); // Logging error
        });
}

function removeUser(userId) {
    log(`Sending delete request for user ID: ${userId}`); // Logging
    fetch("/admin/user/delete_user", {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ user_id: userId }),
        redirect: 'manual'
    })
        .then(response => response.json().then(data => {
            if (response.ok) {
                // Remove the user row from the table and close the modal
                document.getElementById('user-' + userId).remove();
                closeModal();
                alert(data.status || 'Käyttäjä poistettu onnistuneesti.'); // Success message
                log(`Successfully deleted user ID: ${userId}`); // Logging
            } else {
                alert(data.status || 'Virhe käyttäjän poistossa.'); // Error message
                log(`Error deleting user ID ${userId}: ${data.status}`); // Logging error
            }
        })
        )
        .catch(error => {
            console.error('Error:', error); // Log error to the console
            alert('Virhe käyttäjän poistossa.'); // General error message
            log(`Failed to delete user ID ${userId}. Error: ${error}`); // Logging error
        });
}

// Update delete button texts based on fast delete mode
function updateDeleteButtonTexts() {
    const deleteLinks = document.querySelectorAll('.delete-text');
    deleteLinks.forEach((element) => {
        element.textContent = fastDeleteMode ? 'Pikapoisto' : 'Poista';
    });
}


// Close the modal
function closeModal() {
    document.getElementById('deleteModal').classList.add('hidden');
    log('Modal closed.'); // Logging
}

// Function to shake the modal content for visual feedback
function shakeModal() {
    const modalContent = document.querySelector(".modal-content");
    modalContent.classList.add("shake"); // Add shake animation class
    log('Modal content shaken for visual feedback.'); // Logging

    // Remove the shake class after the animation duration (500ms)
    setTimeout(() => {
        modalContent.classList.remove("shake");
    }, 500);
}

// Event listener for clicks outside the modal content
window.onclick = function (event) {
    const modal = document.getElementById("deleteModal");
    if (event.target === modal) {
        shakeModal(); // Trigger shake effect if clicked outside the modal
        log('Clicked outside the modal, triggering shake effect.'); // Logging
    }
};

// Logging function that checks for dev_mode
function log(message) {
    if (localStorage.getItem("dev_mode") === "true") {
        console.log(message);
    }
}
