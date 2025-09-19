/**
 * Toggles between dark and light mode.
 */
function toggleDarkMode() {
    const isDarkMode = $("html").toggleClass("dark").hasClass("dark");
    $("html").toggleClass("light", !isDarkMode);

    // Update theme icons
    $(".theme-icon").each(function () {
        $(this).toggleClass("fa-moon", isDarkMode);
        $(this).toggleClass("fa-sun", !isDarkMode);
    });

    // Store the theme in localStorage
    localStorage.setItem("theme", isDarkMode ? "dark" : "light");
}

/**
 * Applies the preferred theme based on saved preference, user settings, or system settings.
 */
function applyPreferredTheme() {
    let theme = localStorage.getItem("theme"); // user-chosen theme

    // If no user-chosen theme, check current_user preference
    if (!theme) {
        try {
            const userData = localStorage.getItem("current_user");
            if (userData) {
                const user = JSON.parse(userData);
                if (typeof user.dark_mode === "boolean") {
                    theme = user.dark_mode ? "dark" : "light";
                }
            }
        } catch(e) {
            console.warn("Could not read current_user from localStorage:", e);
        }
    }

    // Fallback to system preference
    if (!theme) {
        theme = window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
    }

    // Apply the theme
    $("html").toggleClass("dark", theme === "dark");
    $("html").toggleClass("light", theme !== "dark");

    // Update icons
    $(".theme-icon").each(function () {
        $(this).toggleClass("fa-moon", theme === "dark");
        $(this).toggleClass("fa-sun", theme !== "dark");
    });
}

// Call this on page load
$(document).ready(() => applyPreferredTheme());
