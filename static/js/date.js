
document.addEventListener("DOMContentLoaded", function() {
    flatpickr("#date", {
    dateFormat: "d.m.Y", // Date format
    altInput: true,
    altFormat: "d.m.Y",
    allowInput: true,
    locale: {
        firstDayOfWeek: 1, // Start week on Monday
        weekdays: {
            shorthand: ['Su', 'Ma', 'Ti', 'Ke', 'To', 'Pe', 'La'],
            longhand: ['Sunnuntai', 'Maanantai', 'Tiistai', 'Keskiviikko', 'Torstai', 'Perjantai', 'Lauantai']
        },
        months: {
            shorthand: ['Tam', 'Hel', 'Mar', 'Huht', 'Tou', 'Kes', 'Hele', 'Elok', 'Syys', 'Lok', 'Marr', 'Jou'],
            longhand: ['Tammikuu', 'Helmikuu', 'Maaliskuu', 'Huhtikuu', 'Toukokuu', 'Kesäkuu', 'Heinäkuu', 'Elokuu', 'Syyskuu', 'Lokakuu', 'Marraskuu', 'Joulukuu']
        }
    }
});

    flatpickr("#start_time", {
        enableTime: true, // Enable time selection
        noCalendar: true, // Disable calendar
        dateFormat: "H:i", // 24-hour format
        altInput: true,
        altFormat: "H:i", // Alternate input format for display
        allowInput: true,
        time_24hr: true, // Ensure 24-hour format
    });

    flatpickr("#end_time", {
        enableTime: true,
        noCalendar: true,
        dateFormat: "H:i",
        altInput: true,
        altFormat: "H:i",
        allowInput: true,
        time_24hr: true, // Ensure 24-hour format
    });
});