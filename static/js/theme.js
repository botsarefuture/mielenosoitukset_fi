function toggleDarkMode() {
    document.documentElement.classList.toggle("dark");
    document.documentElement.classList.toggle("light");

    const themeIcon = document.getElementById("theme-icon");

    if (document.documentElement.classList.contains("dark")) {
        themeIcon.classList.remove("fa-moon");
        themeIcon.classList.add("fa-sun");
        localStorage.setItem("theme", "dark");
    } else {
        themeIcon.classList.remove("fa-sun");
        themeIcon.classList.add("fa-moon");
        localStorage.setItem("theme", "light");
    }
}

function applyPreferredTheme() {
    const savedTheme = localStorage.getItem("theme");
    const prefersDarkMode = window.matchMedia("(prefers-color-scheme: dark)").matches;
    const themeIcon = document.getElementById("theme-icon");

    if (savedTheme) {
        if (savedTheme === "dark") {
            document.documentElement.classList.add("dark");
            document.documentElement.classList.remove("light");
            themeIcon.classList.remove("fa-moon");
            themeIcon.classList.add("fa-sun");
        } else {
            document.documentElement.classList.add("light");
            document.documentElement.classList.remove("dark");
            themeIcon.classList.remove("fa-sun");
            themeIcon.classList.add("fa-moon");
        }
    } else if (prefersDarkMode) {
        document.documentElement.classList.add("dark");
        document.documentElement.classList.remove("light");
        themeIcon.classList.remove("fa-moon");
        themeIcon.classList.add("fa-sun");
    } else {
        document.documentElement.classList.add("light");
        document.documentElement.classList.remove("dark");
        themeIcon.classList.remove("fa-sun");
        themeIcon.classList.add("fa-moon");
    }
}