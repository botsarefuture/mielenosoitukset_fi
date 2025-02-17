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
                window.location.href = this.getAttribute('data-href');
            }
        });
    });
}


setup_grid_navigation()