// Select all grid-items
document.querySelectorAll('.grid-item').forEach(item => {
    item.addEventListener('click', function(e) {
        // Check if the clicked element is not a tag link
        if (!e.target.closest('a')) {
            window.location.href = this.getAttribute('data-href');
        }
    });
});
