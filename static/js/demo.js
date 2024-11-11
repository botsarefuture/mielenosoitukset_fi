// Select all grid-items
document.querySelectorAll('.grid-item').forEach(item => {
    item.addEventListener('click', function(e) {
        // Check if the clicked element is not a tag link
        if (!e.target.closest('a')) {
            const href = this.getAttribute('data-href');
            if (isValidUrl(href)) {
                window.location.href = href;
            } else {
               console.error('Invalid URL:', href);
           }
       }
   });
});

function isValidUrl(url) {
    try {
        new URL(url);
        return true;
    } catch (e) {
        return false;
    }
}
