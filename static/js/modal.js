/**
 * Initializes modal functionality when the DOM content is loaded.
 * 
 * - Adds click event listeners to open modal buttons to open the respective modal.
 * - Adds click event listener to the overlay to close all active modals.
 * - Adds click event listeners to close modal buttons to close the respective modal.
 * 
 * @event DOMContentLoaded
 */

/**
 * Opens the specified modal and activates the overlay.
 * 
 * @param {HTMLElement} modal - The modal element to be opened.
 */

/**
 * Closes the specified modal and deactivates the overlay.
 * 
 * @param {HTMLElement} modal - The modal element to be closed.
 */


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

    function openModal(modal) {
        if (modal == null) return;
        modal.classList.add('active');
        overlay.classList.add('active');
    }

    function closeModal(modal) {
        if (modal == null) return;
        modal.classList.remove('active');
        overlay.classList.remove('active');
    }
});