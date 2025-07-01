/**
 * Opens the specified modal and activates the overlay.
 * 
 * @param {jQuery} modal - The modal element to be opened.
 */


// when this is loaded on the page, insert jquery and css to the page
// this is a hacky way to make sure that the modal works on the page

// insert jquery
const jqueryScript = document.createElement('script');
jqueryScript.src = "/static/js/jQuery/jq.min.js";
document.head.appendChild(jqueryScript);

// wait for jQuery to load before using it
jqueryScript.onload = function () {
    $(document).ready(() => {
        const openModalButtons = $('[data-modal-target]');
        const closeModalButtons = $('[data-close-button]');
        const overlay = $('#overlay');

        openModalButtons.each(function () {
            $(this).on('click', function () {
                const modal = $($(this).data('modal-target'));
                openModal(modal);
                console.log("Opened modal", $(this).data('modal-target'))
            });
        });

        overlay.on('click', function () {
            const modals = $('.modal.active');
            modals.each(function () {
                closeModal($(this));
            });
        });

        closeModalButtons.each(function () {
            $(this).on('click', function () {
                console.log('close button clicked');
                const modal = $(this).closest('.modal');
                console.log(modal);
                closeModal(modal);
            });
        });
    });
};


function openModal(modal) {
    console.log(modal.length);
    if (modal.length === 0) return;
    modal.addClass('active');
    // force modal to have the highest z-index value out of all items on the page
    modal.css('z-index', 1000 * 1000);

    if ($('#overlay').length) {
        $('#overlay').addClass('active');
    } else {
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
 * @param {jQuery} modal - The modal element to be closed.
 */
async function closeModal(modal) {
    if (modal.length === 0) {
        console.error("Modal not found.");
        return;
    }
    console.log(modal);
    modal.removeClass('active');
    const activeModals = $('.modal.active');
    if (activeModals.length === 0) {
        $('#overlay').removeClass('active');
    }
}

// if $ is not defined, wait for it to be defined
let interval = setInterval(() => {
    if (window.$) {
        clearInterval(interval);

        $(document).ready(() => {
            const openModalButtons = $('[data-modal-target]');
            const closeModalButtons = $('[data-close-button]');
            const overlay = $('#overlay');

            openModalButtons.each(function () {
                $(this).on('click', function () {
                    const modal = $($(this).data('modal-target'));
                    openModal(modal);
                });
            });

            overlay.on('click', function () {
                const modals = $('.modal.active');
                modals.each(function () {
                    closeModal($(this));
                });
            });


            /**
             * Closes the specified modal and deactivates the overlay.
             * 
             * @param {jQuery} modal - The modal element to be closed.
             */
            async function closeModal(modal) {
                if (modal.length === 0) {
                    console.error("Modal not found.");
                    return;
                }
                modal.removeClass('active');
                const activeModals = $('.modal.active');
                if (activeModals.length === 0) {
                    $('#overlay').removeClass('active');
                }
            }

            closeModalButtons.each(function () {
                $(this).on('click', async function () {
                    const modal = $(this).closest('.modal');
                    await closeModal(modal);
                });
            });
        });

    }
}, 100);

/**
 * Initializes modal functionality for opening and closing modals.
 *
 * Parameters
 * ----------
 * None.
 *
 * Returns
 * -------
 * None.
 */
document.addEventListener("DOMContentLoaded", () => {
  const overlay = document.getElementById("overlay");
  const modals = document.querySelectorAll(".modal");
  const closeButtons = document.querySelectorAll("[data-close-modal]");

  // Close modal function
  function closeModal() {
    modals.forEach((modal) => modal.classList.remove("active"));
    overlay.classList.remove("active");
  }

  // Attach close event to close buttons and overlay
  closeButtons.forEach((button) =>
    button.addEventListener("click", closeModal)
  );
  overlay.addEventListener("click", closeModal);

  // Open modal function
  //function openModal(modalId) {
  //  const modal = document.getElementById(modalId);
  //  if (modal) {
  //    modal.classList.add("active");
  //    overlay.classList.add("active");
  //  }
  //}
  function openModal(modal) {
    console.log(modal.length);
    if (modal.length === 0) return;
    modal.addClass('active');
    // force modal to have the highest z-index value out of all items on the page
    modal.css('z-index', 1000 * 1000);

    if ($('#overlay').length) {
        $('#overlay').addClass('active');
    } else {
        console.log("Overlay not found. Waiting for it to be loaded...");
        // wait for the overlay to be loaded
        setTimeout(() => {
            openModal(modal);
        }, 100);
    }
}

  // Expose openModal globally for external use
  window.openModal = openModal;
});
