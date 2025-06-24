/**
 * Adds click event listeners to grid items for navigation
 * 
 * Parameters
 * ----------
 * selector : str
 *     CSS selector for grid items
 *
 * Notes
 * -----
 * Clicking anywhere on the grid item (except links) will navigate
 * to the URL specified in data-href attribute
 */
function setup_grid_navigation(selector = '.grid-item') {
    document.querySelectorAll(selector).forEach(item => {
        item.addEventListener('click', function(e) {
            if (!e.target.closest('a')) {
                const href = this.getAttribute('data-href');
                try {
                    const url = new URL(href, window.location.origin);
                    if (url.origin === window.location.origin) {
                        window.location.href = url.href;
                    } else {
                        console.error('Invalid URL:', href);
                    }
                } catch (e) {
                    console.error('Malformed URL:', href);
                }
            }
        });
    });
}


setup_grid_navigation()