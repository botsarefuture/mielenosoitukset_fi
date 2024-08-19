document.addEventListener('DOMContentLoaded', () => {
    const sidebar = document.querySelector('.sidebar');
    sidebar.classList.add('hidden');
    const toggleButton = document.querySelector('.sidebar-toggle');

    // Load the saved sidebar state from localStorage
    const isSidebarHidden = localStorage.getItem('sidebarHidden') === 'true';
    if (isSidebarHidden) {
        sidebar.classList.add('hidden');
    } else {
        sidebar.classList.remove('hidden');
    }

    // Add event listener for the toggle button
    toggleButton.addEventListener('click', () => {
        const isHidden = sidebar.classList.toggle('hidden');
        // Save the sidebar state to localStorage
        localStorage.setItem('sidebarHidden', isHidden);
    });
});
