/**
 * Initializes the sidebar functionality once the DOM content is loaded.
 * 
 * This script handles the toggling of the sidebar visibility and adjusts the main content accordingly.
 * It also saves the sidebar state in localStorage to persist the user's preference.
 * 
 * Elements:
 * - sidebar: The sidebar container element.
 * - toggleButton: The main toggle button for the sidebar.
 * - hiddenIcons: The container for hidden icons.
 * - hiddenToggleButton: The toggle button for hidden icons.
 * - mainContent: The main content container element.
 * - headerbar: The header bar element.
 * 
 * Logic:
 * - Checks if all required elements exist before proceeding.
 * - Loads the saved sidebar state from localStorage and applies the appropriate classes/styles.
 * - Defines a function to toggle the sidebar visibility and update localStorage.
 * - Adds event listeners to the toggle buttons to handle sidebar toggling.
 */

document.addEventListener('DOMContentLoaded', () => {
    // Select elements based on the updated class names
    const sidebar = document.querySelector('.container-sidebar');
    const toggleButton = document.getElementById('maintoggle');
    const hiddenIcons = document.querySelector('.hidden-icons');
    const hiddenToggleButton = document.getElementById('hiddentoggle');
    const mainContent = document.querySelector('.container-main-content');
    const headerbar = document.getElementById('headerbar');

    // Ensure the required elements exist before running logic
    if (!sidebar || !toggleButton || !hiddenIcons || !hiddenToggleButton || !mainContent) {
        console.error('Required elements are missing. Please check the element selectors.');
        return;
    }

    // Load the saved sidebar state from localStorage
    const isSidebarHidden = localStorage.getItem('sidebarHidden') === 'true';
    if (isSidebarHidden) {
        sidebar.classList.add('hidden');
        hiddenIcons.style.display = 'flex'; // Show hidden icons
        mainContent.classList.remove('shifted'); // Remove shift from main content
        headerbar.classList.remove("shifted");
    } else {
        sidebar.classList.remove('hidden');
        hiddenIcons.style.display = 'none'; // Hide hidden icons
        mainContent.classList.add('shifted'); // Shift main content
        headerbar.classList.add('shifted');
    }

    // Function to toggle the sidebar and adjust main content
    const toggleSidebar = () => {
        const isHidden = sidebar.classList.toggle('hidden');
        localStorage.setItem('sidebarHidden', isHidden); // Save sidebar state

        if (isHidden) {
            hiddenIcons.style.display = 'flex'; // Show hidden icons
            mainContent.classList.remove('shifted'); // Remove shift from main content
            headerbar.classList.remove("shifted");
        } else {
            hiddenIcons.style.display = 'none'; // Hide hidden icons
            mainContent.classList.add('shifted'); // Shift main content
            headerbar.classList.add('shifted');
        }
    };

    // Add event listener for the sidebar toggle button
    toggleButton.addEventListener('click', toggleSidebar);

    // Add event listener for the hidden icons toggle button
    hiddenToggleButton.addEventListener('click', toggleSidebar);
});
