document.addEventListener('DOMContentLoaded', () => {
    // Select elements based on the updated class names
    const sidebar = document.querySelector('.container-sidebar');
    const toggleButton = document.getElementById('maintoggle');
    const hiddenIcons = document.querySelector('.hidden-icons');
    const hiddenToggleButton = document.getElementById('hiddentoggle');
    const mainContent = document.querySelector('.container-main-content');

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
    } else {
        sidebar.classList.remove('hidden');
        hiddenIcons.style.display = 'none'; // Hide hidden icons
        mainContent.classList.add('shifted'); // Shift main content
    }

    // Function to toggle the sidebar and adjust main content
    const toggleSidebar = () => {
        const isHidden = sidebar.classList.toggle('hidden');
        localStorage.setItem('sidebarHidden', isHidden); // Save sidebar state

        if (isHidden) {
            hiddenIcons.style.display = 'flex'; // Show hidden icons
            mainContent.classList.remove('shifted'); // Remove shift from main content
        } else {
            hiddenIcons.style.display = 'none'; // Hide hidden icons
            mainContent.classList.add('shifted'); // Shift main content
        }
    };

    // Add event listener for the sidebar toggle button
    toggleButton.addEventListener('click', toggleSidebar);

    // Add event listener for the hidden icons toggle button
    hiddenToggleButton.addEventListener('click', toggleSidebar);
});
