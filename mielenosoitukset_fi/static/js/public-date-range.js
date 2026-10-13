/* Shared Flatpickr adapter for public collection date ranges. */
(function (global) {
  "use strict";

  function parseDate(value, iso = false) {
    const match = String(value || "").match(iso ? /^(\d{4})-(\d{2})-(\d{2})$/ : /^(\d{1,2})\.(\d{1,2})\.(\d{4})$/);
    if (!match) return undefined;
    const parts = match.slice(1).map(Number);
    const [year, month, day] = iso ? parts : parts.reverse();
    const date = new Date(year, month - 1, day);
    return date.getFullYear() === year && date.getMonth() === month - 1 && date.getDate() === day ? date : undefined;
  }

  function create(form) {
    if (typeof global.flatpickr !== "function") return null; // manual entry still works
    const inputs = ['start', 'end'].map(edge => form.elements.namedItem(`display_date_${edge}`));
    if (inputs.some(input => !input)) return null;
    const activeLocale = global.currentLocale || document.documentElement.lang || 'fi';
    const formatCalendarPart = (date, options) => new Intl.DateTimeFormat(activeLocale, { ...options, timeZone: 'UTC' }).format(date);
    const weekdays = Array.from({length: 7}, (_, index) => new Date(Date.UTC(2024, 0, 7 + index, 12)));
    const months = Array.from({length: 12}, (_, index) => new Date(Date.UTC(2024, index, 1, 12)));
    const locale = {
      firstDayOfWeek: 1,
      yearAriaLabel: form.dataset.dateYearLabel, monthAriaLabel: form.dataset.dateMonthLabel,
      weekdays: { shorthand: weekdays.map(date => formatCalendarPart(date, {weekday: 'short'})), longhand: weekdays.map(date => formatCalendarPart(date, {weekday: 'long'})) },
      months: { shorthand: months.map(date => formatCalendarPart(date, {month: 'short'})), longhand: months.map(date => formatCalendarPart(date, {month: 'long'})) },
    };
    let pickers = [];
    function bounds(start, end) {
      const today = new Date(); today.setHours(0, 0, 0, 0);
      // Historical endpoints enable historical browsing, not a new lower
      // bound at the restored value. Clearing both returns to today's floor.
      const historical = (start && start < today) || (end && end < today);
      const floor = historical ? undefined : today;
      pickers[0].set('minDate', floor);
      pickers[0].set('maxDate', end);
      pickers[1].set('minDate', start || floor);
      pickers[1].set('maxDate', undefined);
    }
    function changed(_, __, instance) {
      if (instance) delete instance.input.dataset.invalidDateEntry;
      bounds(parseDate(inputs[0].value), parseDate(inputs[1].value));
    }
    pickers = inputs.map(input => global.flatpickr(input, {
      dateFormat: 'd.m.Y', allowInput: true, disableMobile: true,
      locale, parseDate: value => parseDate(value),
      onChange: changed,
      onReady: (_, __, instance) => {
        const calendar = instance.calendarContainer;
        calendar.classList.add('public-date-calendar');
        calendar.id = `${input.id}-calendar`;
        calendar.setAttribute('role', 'dialog');
        calendar.setAttribute('aria-label', input.labels?.[0]?.textContent || '');
        input.setAttribute('role', 'combobox'); input.setAttribute('aria-haspopup', 'dialog');
        input.setAttribute('aria-controls', calendar.id); input.setAttribute('aria-expanded', 'false');
      },
      onOpen: (_, __, instance) => instance.input.setAttribute('aria-expanded', 'true'),
      onClose: (_, __, instance) => instance.input.setAttribute('aria-expanded', 'false'),
    }));
    // Prevent Flatpickr's blur parser from normalizing invalid calendar days
    // before the shared form validator can report them to the visitor.
    const listeners = inputs.map(input => {
      const onInput = () => {
        const date = parseDate(input.value), picker = input._flatpickr;
        const outsideBounds = date && ((picker.config.minDate && date < picker.config.minDate) || (picker.config.maxDate && date > picker.config.maxDate));
        if (input.value && (!date || outsideBounds)) input.dataset.invalidDateEntry = input.value;
        else delete input.dataset.invalidDateEntry;
      };
      const onBlur = event => {
        if (input.dataset.invalidDateEntry || (input.value && !parseDate(input.value))) event.stopImmediatePropagation();
      };
      const onKeydown = event => {
        const picker = input._flatpickr;
        if (event.key === 'ArrowDown' && picker) {
          event.preventDefault(); event.stopImmediatePropagation();
          picker.open();
          const day = picker.selectedDateElem || picker.todayDateElem || picker.calendarContainer.querySelector('.flatpickr-day:not(.flatpickr-disabled):not(.prevMonthDay):not(.nextMonthDay)');
          day?.focus();
        } else if (event.key === 'Escape' && picker?.isOpen) {
          event.preventDefault(); event.stopImmediatePropagation(); picker.close();
        }
      };
      input.addEventListener('input', onInput);
      input.addEventListener('blur', onBlur, true);
      input.addEventListener('keydown', onKeydown, true);
      return {input, onInput, onBlur, onKeydown};
    });
    return {
      setValues(startValue, endValue) {
        inputs.forEach(input => delete input.dataset.invalidDateEntry);
        const start = parseDate(startValue, true), end = parseDate(endValue, true);
        pickers.forEach(picker => picker.clear(false));
        bounds(start, end);
        pickers[0].setDate(start || [], false);
        pickers[1].setDate(end || [], false);
      },
      destroy() {
        listeners.forEach(({input, onInput, onBlur, onKeydown}) => {
          input.removeEventListener('input', onInput);
          input.removeEventListener('blur', onBlur, true);
          input.removeEventListener('keydown', onKeydown, true);
          ['role', 'aria-haspopup', 'aria-controls', 'aria-expanded'].forEach(name => input.removeAttribute(name));
        });
        pickers.forEach(picker => picker.destroy());
      },
    };
  }

  global.PublicDateRange = { create };
})(window);
