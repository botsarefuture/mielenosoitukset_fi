/**
 * Toggles between dark and light mode.
 */
function toggleDarkMode() {
    const isDarkMode = $("html").toggleClass("dark").hasClass("dark");

    if (!isDarkMode) {
        $("html").toggleClass("light");
    } else {
        $("html").toggleClass("light");
    }

    // Select all theme icons
    const themeIcons = $(".theme-icon");

    console.log(isDarkMode);

    // Update the icons based on the theme
    themeIcons.each(function () {
        $(this).toggleClass("fa-moon", isDarkMode);
        $(this).toggleClass("fa-sun", !isDarkMode);
    });

    // Store the theme in localStorage
    localStorage.setItem("theme", isDarkMode ? "dark" : "light");
}

/**
 * Applies the preferred theme based on saved preference or system settings.
 */
function applyPreferredTheme() {
    const savedTheme = localStorage.getItem("theme");
    const prefersDarkMode = window.matchMedia("(prefers-color-scheme: dark)").matches;

    // Determine the active theme
    let theme = savedTheme || (prefersDarkMode ? "dark" : "light");

    // Apply the theme to the document
    $("html").toggleClass("dark", theme === "dark");
    $("html").toggleClass("light", theme !== "dark");

    // Select all theme icons and update based on the applied theme
    const themeIcons = $(".theme-icon");

    themeIcons.each(function () {
        $(this).toggleClass("fa-moon", theme === "dark");
        $(this).toggleClass("fa-sun", theme !== "dark");
    });
}
