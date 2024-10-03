function openModal(title, demoId) {
    document.getElementById('demoTitle').innerText = title;
    document.getElementById('demo_id').value = demoId;
    document.getElementById('deleteModal').classList.remove('hidden');
}

function closeModal() {
    document.getElementById('deleteModal').classList.add('hidden');
}

// Function to shake the modal
function shakeModal() {
    const modalContent = document.querySelector(".modal-content");
    modalContent.classList.add("shake"); // Add shake class

    // Remove shake class after animation ends
    setTimeout(() => {
        modalContent.classList.remove("shake");
    }, 500); // Match duration of the animation
}

// Event listener for clicks outside the modal
window.onclick = function(event) {
    const modal = document.getElementById("deleteModal");
    // Check if the click is outside the modal content
    if (event.target === modal) {
        shakeModal(); // Shake the modal
    }
};