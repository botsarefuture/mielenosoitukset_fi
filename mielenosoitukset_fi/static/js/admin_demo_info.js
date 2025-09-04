/**
 * Fetches demonstration information and updates the modal content.
 *
 * Parameters
 * ----------
 * demo_id : str
 *     The ID of the demonstration to fetch information for.
 */
async function fetchDemoInfo(demo_id) {
    try {
        const response = await fetch(`/api/admin/demo/info/${demo_id}`);
        if (!response.ok) {
            throw new Error('Network response was not ok');
        }
        const demo_info = await response.json();
        console.log(demo_info);
        updateModalContent(demo_info);
        showModal();
    } catch (error) {
        console.error('There was a problem with the fetch operation:', error);
    }
}
/**
 * Updates the content of the modal with demonstration information.
 *
 * Parameters
 * ----------
 * demo_info : Object
 *     The demonstration information object.
 */
function updateModalContent(demo_info) {
    // insert the modal into the document if it doesn't exist
    if (!document.querySelector('#demo-modal')) {
        document.body.innerHTML += `
            <div class="modal" id="demo-modal">
                    <div class="modal-header">
                        <h2></h2>
                        <span class="close-button" data-close-button>&times;</span>
                    </div>
                    <div class="modal-body">
                        <p></p>
                    </div>
                    <div class="modal-footer">
                    </div>
            </div>
        `;
    }
    // update modal content
    document.querySelector('#demo-modal .modal-header h2').textContent = demo_info.title;
    document.querySelector('#demo-modal .modal-body p').textContent = demo_info.description || 'No description available';
    const modal_footer = document.querySelector('#demo-modal .modal-footer');
    modal_footer.innerHTML = `
        <label>ID:</label> <p>${demo_info._id}</p>
        <label>Address:</label> <p>${demo_info.address}</p>
        <label>City:</label> <p>${demo_info.city}</p>
        <label>Date:</label> <p>${demo_info.date}</p>
        <label>End Time:</label> <p>${demo_info.end_time}</p>
        <label>Event Type:</label> <p>${demo_info.event_type}</p>
        <label>Facebook:</label> <p>${demo_info.facebook}</p>
        <label>Latitude:</label> <p>${demo_info.latitude}</p>
        <label>Longitude:</label> <p>${demo_info.longitude}</p>
        <label>Start Time:</label> <p>${demo_info.start_time}</p>
        <label>Tags:</label> <p>${demo_info.tags.join(', ')}</p>
        <label>Title:</label> <p>${demo_info.title}</p>
        <label>Recurring:</label> <p>${demo_info.recurs}</p>
        <label>Repeat Schedule:</label> <div>
        ${demo_info.repeat_schedule != null ? `
            <p>Frequency: ${demo_info.repeat_schedule.frequency}</p>
            <p>Interval: ${demo_info.repeat_schedule.interval}</p>
            <p>End Date: ${demo_info.repeat_schedule.end_date}</p>
            <p>Weekday: ${demo_info.repeat_schedule.weekday}</p>` : "Not repeating"}
        </div>
    
        <label>Organizers:</label> <p>${demo_info.organizers.map(org => org.name).join(', ')}</p>
        <button class="download-button">Download</button>
    `;
    document.querySelector('.download-button').addEventListener('click', function () {
        downloadDemoFile();
    });

    // Initialize modal functionality
    document.addEventListener('DOMContentLoaded', () => {
        const closeModalButtons = document.querySelectorAll('[data-close-button]');
        const overlay = document.getElementById('overlay');

        closeModalButtons.forEach(button => {
            button.addEventListener('click', () => {
                const modal = button.closest('.modal');
                closeModal(modal);
            });
        });

        overlay.addEventListener('click', () => {
            const modals = document.querySelectorAll('.modal.active');
            modals.forEach(modal => {
                closeModal(modal);
            });
        });
    });
}

/**
 * Displays the modal.
 */
function showModal() {
    const modal = document.querySelector('#demo-modal');
    modal.classList.add("display", "active");
    // Activate overlay to hide other content
    const overlay = document.getElementById('overlay');
    if (overlay) {
        overlay.style.display = 'block';
    }
}

/**
 * Closes the modal and hides the overlay.
 */
function closeModal(modal) {
    modal.classList.remove("active", "display");
    const overlay = document.getElementById('overlay');
    if (overlay) {
        overlay.style.display = 'none';
    }
}

if (localStorage.getItem('user_role') && localStorage.getItem('user_role').includes('admin')) {
    // when control + i is pressed, the modal will appear, and use demoId (global variable) to fetch the demo info
    document.addEventListener('keydown', function (event) {
        if (event.ctrlKey && event.key === 'i' && event.altKey) {
            fetchDemoInfo(demoId);
        }
    });
}