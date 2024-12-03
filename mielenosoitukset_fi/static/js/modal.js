/**
 * Opens the specified modal and activates the overlay.
 * 
 * @param {HTMLElement} modal - The modal element to be opened.
 */
function openModal(modal) {
    if (modal == null) return;
    modal.classList.add('active');
    // force modal to have the highest z-index value out of all items on the pag
    modal.style.zIndex = 1000*1000;

    if (overlay) {
    overlay.classList.add('active');}
    else {
        console.log("Overlay not found. Waiting for it to be loaded...");
        // wait for the overlay to be loaded
        setTimeout(() => {
            openModal(modal);
        }, 100);
    }
}

/**
 * Closes the specified modal and deactivates the overlay.
 * 
 * @param {HTMLElement} modal - The modal element to be closed.
 */
function closeModal(modal) {
    if (modal == null) return;
    modal.classList.remove('active');
    if (overlay) {
    overlay.classList.remove('active');}
    else {
        console.log("Overlay not found. Waiting for it to be loaded...");
        // wait for the overlay to be loaded
        setTimeout(() => {
            closeModal(modal);
        }, 100);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const openModalButtons = document.querySelectorAll('[data-modal-target]');
    const closeModalButtons = document.querySelectorAll('[data-close-button]');
    const overlay = document.getElementById('overlay');

    openModalButtons.forEach(button => {
        button.addEventListener('click', () => {
            const modal = document.querySelector(button.dataset.modalTarget);
            openModal(modal);
        });
    });

    overlay.addEventListener('click', () => {
        const modals = document.querySelectorAll('.modal.active');
        modals.forEach(modal => {
            closeModal(modal);
        });
    });

    closeModalButtons.forEach(button => {
        button.addEventListener('click', () => {
            const modal = button.closest('.modal');
            closeModal(modal);
        });
    });
});
