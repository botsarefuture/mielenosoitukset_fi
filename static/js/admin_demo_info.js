async function fetchDemoInfo(demoId) {
    try {
        const response = await fetch(`/api/admin/demo/info/${demoId}`);
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

function updateModalContent(demo_info) {
    // insert the modal into the document if it doesn't exist
    if (!document.querySelector('.modal')) {
        document.body.innerHTML += `
            <div class="modal">
                <div class="modal-content">
                    <div class="modal-header">
                        <h2></h2>
                        <span class="close-button">&times;</span>
                    </div>
                    <div class="modal-body">
                        <p></p>
                    </div>
                    <div class="modal-footer">
                    </div>
                </div>
            </div>
        `;
    }
    // update modal content
    document.querySelector('.modal-header h2').textContent = demo_info.title;
    document.querySelector('.modal-body p').textContent = demo_info.description || 'No description available';
    const modal_footer = document.querySelector('.modal-footer');
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
        <label>Recurring:</label> <p>${demo_info.recurring}</p>
        <label>Repeat Schedule:</label> <div>
            <p>Frequency: ${demo_info.repeat_schedule.frequency}</p>
            <p>Interval: ${demo_info.repeat_schedule.interval}</p>
            <p>End Date: ${demo_info.repeat_schedule.end_date}</p>
            <p>Weekday: ${demo_info.repeat_schedule.weekday}</p>
        </div>
    
        <label>Organizers:</label> <p>${demo_info.organizers.map(org => org.name).join(', ')}</p>
        <button class="download-button">Download</button>
    `;
    document.querySelector('.download-button').addEventListener('click', function () {
        downloadDemoFile();
    });
    // add event listener to close the modal
    document.querySelector('.close-button').addEventListener('click', function () {
        closeModal();
    });
}

function showModal() {
    document.querySelector('.modal').classList.add("display");
}

function closeModal() {
    document.querySelector('.modal').classList.remove("display");
}

// when control + i is pressed, the modal will appear, and use demoId (global variable) to fetch the demo info
document.addEventListener('keydown', function (event) {
    if (event.ctrlKey && event.key === 'i' && event.altKey) {
        fetchDemoInfo(demoId);
    }
});