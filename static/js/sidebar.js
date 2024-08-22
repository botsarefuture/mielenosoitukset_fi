document.addEventListener('DOMContentLoaded', () => {
    const sidebar = document.querySelector('.sidebar');
    const toggleButton = document.querySelector('.sidebar-toggle');
    const hiddenIcons = document.querySelector('.hidden-icons');
    const hiddenToggleButton = document.getElementById('hiddentoggle');
    const mainContent = document.querySelector('.main-content');

    // Load the saved sidebar state from localStorage
    const isSidebarHidden = localStorage.getItem('sidebarHidden') === 'true';
    if (isSidebarHidden) {
        sidebar.classList.add('hidden');
        hiddenIcons.style.display = 'flex'; // Show hidden icons
        mainContent.classList.add('shifted'); // Shift main content
    } else {
        sidebar.classList.remove('hidden');
        hiddenIcons.style.display = 'none'; // Hide hidden icons
        mainContent.classList.remove('shifted'); // Remove shift from main content
    }

    // Function to toggle the sidebar and shift main content
    const toggleSidebar = () => {
        const isHidden = sidebar.classList.toggle('hidden');
        localStorage.setItem('sidebarHidden', isHidden); // Save sidebar state

        if (isHidden) {
            hiddenIcons.style.display = 'flex'; // Show hidden icons
            mainContent.classList.add('shifted'); // Shift main content
        } else {
            hiddenIcons.style.display = 'none'; // Hide hidden icons
            mainContent.classList.remove('shifted'); // Remove shift from main content
        }
    };

    // Add event listener for the sidebar toggle button in the sidebar
    toggleButton.addEventListener('click', toggleSidebar);

    // Add event listener for the sidebar toggle button in the hidden icons
    hiddenToggleButton.addEventListener('click', toggleSidebar);
});
