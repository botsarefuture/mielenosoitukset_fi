/**
 * Toggles between dark and light mode.
 */
function applyThemeState(isDarkMode) {
    const root = document.documentElement;
    root.classList.toggle("dark", isDarkMode);
    root.classList.toggle("light", !isDarkMode);

    document.querySelectorAll(".theme-icon").forEach(icon => {
        icon.classList.toggle("fa-moon", isDarkMode);
        icon.classList.toggle("fa-sun", !isDarkMode);
    });
}

function toggleDarkMode() {
    const isDarkMode = !document.documentElement.classList.contains("dark");
    applyThemeState(isDarkMode);

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

    applyThemeState(theme === "dark");
}
