if (localStorage.getItem('user_role')?.includes('admin')) {
    // When Ctrl + Alt + I is pressed, open the edit demo page in a popup
    document.addEventListener('keydown', function(event) {
        if (event.ctrlKey && event.altKey && event.key.toLowerCase() === 'i') {
            const demoId = window.demoId;  // Ensure `demoId` is globally available
            if (!demoId) return console.warn("demoId not defined");

            // Flask's URL for edit page
            const editUrl = `/admin/demo/edit_demo/${demoId}`;

            // Open a popup window
            window.open(
                editUrl,
                "EditDemo",
                "width=1000,height=800,resizable=yes,scrollbars=yes"
            );
        }
    });

    function fetchDemoInfo() {
        const demoId = window.demoId;  // Ensure `demoId` is globally available
            if (!demoId) return console.warn("demoId not defined");

            // Flask's URL for edit page
            const editUrl = `/admin/demo/edit_demo/${demoId}`;

            // Open a popup window
            window.open(
                editUrl,
                "EditDemo",
                "width=1000,height=800,resizable=yes,scrollbars=yes"
            );
    }
}
