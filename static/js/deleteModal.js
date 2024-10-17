// Flag to indicate if fast delete mode is active
let fastDeleteMode = false;

// Enable fast delete mode when the Shift key is pressed
document.addEventListener('keydown', (event) => {
    if (event.key === 'Shift') {
        fastDeleteMode = true; 
        updateDeleteButtonTexts(); // Update button texts on Shift press
        log('Fast delete mode enabled.'); // Logging
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
function openModal(event, demoTitle, demoId) {
    event.preventDefault(); // Prevent the default action, like opening a link
    log(`Attempting to open modal for demo ID: ${demoId}`); // Logging
    if (fastDeleteMode) {
        removeDemo(demoId); // Call the remove function for fast delete mode
    } else {
        // Display the modal with demo title
        document.getElementById('demoTitle').textContent = demoTitle;
        document.getElementById('confirmDelete').setAttribute('data-demo-id', demoId);
        document.getElementById('deleteModal').classList.remove('hidden');
        log(`Opened modal for demo: ${demoTitle}`); // Logging
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

// Update delete button texts based on fast delete mode
function updateDeleteButtonTexts() {
    const deleteLinks = document.querySelectorAll('.delete-text');
    deleteLinks.forEach((element) => {
        element.textContent = fastDeleteMode ? 'Pikapoisto' : 'Poista';
    });
}

// Event listener for the confirm delete button
document.getElementById('confirmDelete').addEventListener('click', function() {
    const demoId = this.getAttribute('data-demo-id');
    log(`Confirming deletion for demo ID: ${demoId}`); // Logging
    removeDemo(demoId); // Execute the remove function on button click
});

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
window.onclick = function(event) {
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
