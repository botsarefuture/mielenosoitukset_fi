// Configuration objects for date and time pickers
const date_picker_config = {
    dateFormat: "Y-m-d",
    altInput: true,
    altFormat: "d.m.Y",
    allowInput: true,
    locale: {
        firstDayOfWeek: 1, // Fixed typo from firstDayOfTheWee
        weekdays: {
            shorthand: ['Su', 'Ma', 'Ti', 'Ke', 'To', 'Pe', 'La'],
            longhand: ['Sunnuntai', 'Maanantai', 'Tiistai', 'Keskiviikko', 'Torstai', 'Perjantai', 'Lauantai']
        },
        months: {
            shorthand: ['Tam', 'Hel', 'Mar', 'Huht', 'Tou', 'Kes', 'Hele', 'Elok', 'Syys', 'Lok', 'Marr', 'Jou'],
            longhand: ['Tammikuu', 'Helmikuu', 'Maaliskuu', 'Huhtikuu', 'Toukokuu', 'Kesäkuu', 'Heinäkuu', 'Elokuu', 'Syyskuu', 'Lokakuu', 'Marraskuu', 'Joulukuu']
        }
    }
};

const time_picker_config = {
    enableTime: true,
    noCalendar: true,
    dateFormat: "H:i",
    altInput: true,
    altFormat: "H:i",
    allowInput: true,
    time_24hr: true
};

/**
 * Initialize date and time pickers with given configurations
 *
 * Parameters
 * ----------
 * None
 *
 * Returns
 * -------
 * void
 */
function initializeDatePickers() {
    
    if (window.today == true) {
        date_picker_config.minDate = 'today';
    }
    
    flatpickr("#date", date_picker_config);
    flatpickr("#start_time", time_picker_config);
    flatpickr("#end_time", time_picker_config);
}

document.addEventListener("DOMContentLoaded", initializeDatePickers);