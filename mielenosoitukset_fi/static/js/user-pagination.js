/*
 * Shared load-more contract for user-facing demonstration listings.
 * Pages provide the API-specific loader; this controller owns button state.
 */
(function (global) {
  "use strict";

  function createLoadMoreController({
    button = null,
    sentinel = null,
    loadPage,
    initialLabel = "Lataa lisää",
    loadingLabel = "Ladataan...",
    rootMargin = "1000px",
  }) {
    if ((!button && !sentinel) || typeof loadPage !== "function") {
      return null;
    }

    let currentPage = 1;
    let totalPages = 1;
    let loading = false;
    let observer = null;
    let generation = 0;

    function setButtonState() {
      if (!button) return;
      button.textContent = initialLabel;
      button.disabled = loading;
      button.classList.remove("loading");
      button.hidden = currentPage >= totalPages;
    }

    function setState(page, pageCount) {
      currentPage = Number(page) || 1;
      totalPages = Number(pageCount) || 1;
      setButtonState();
    }

    async function loadPageWithState(pageNumber, options = {}, requestGeneration = generation) {
      const result = await loadPage(pageNumber, options);
      if (requestGeneration !== generation) return null;
      if (result) {
        setState(result.page, result.total_pages);
      }
      return result;
    }

    async function loadNext() {
      if (loading || currentPage >= totalPages) return;
      const requestGeneration = generation;
      loading = true;
      if (button) {
        button.disabled = true;
        button.classList.add("loading");
        button.textContent = loadingLabel;
      }

      try {
        await loadPageWithState(currentPage + 1, { append: true }, requestGeneration);
      } finally {
        if (requestGeneration === generation) {
          loading = false;
          setButtonState();
        }
      }
    }

    async function reload(options = {}) {
      const requestGeneration = ++generation;
      const page = Math.max(Number(options.page) || 1, 1);
      currentPage = page;
      totalPages = 1;
      loading = true;
      if (button) button.disabled = true;
      try {
        return await loadPageWithState(page, { ...options, reset: true }, requestGeneration);
      } finally {
        if (requestGeneration === generation) {
          loading = false;
          setButtonState();
        }
      }
    }

    if (button) button.addEventListener("click", loadNext);
    if (sentinel && "IntersectionObserver" in window) {
      observer = new IntersectionObserver((entries) => {
        if (entries.some((entry) => entry.isIntersecting)) loadNext();
      }, { rootMargin });
      observer.observe(sentinel);
    }
    setState(currentPage, totalPages);

    return {
      button,
      setState,
      reload,
      loadNext,
      get currentPage() {
        return currentPage;
      },
      get totalPages() {
        return totalPages;
      },
      destroy() {
        observer?.disconnect();
        if (button) button.removeEventListener("click", loadNext);
      },
    };
  }

  function createFilterHistory({ form, fixed = {}, onChange, cityLabel = "", removeLabel = "" }) {
    const names = ["search", "city", "location", "date_start", "date_end"];
    let params = {};
    let page = 1;
    const field = name => form.elements.namedItem(name);
    const dateRange = global.PublicDateRange?.create(form);
    const positive = (value, fallback) => /^\d+$/.test(value || "") && Number.isSafeInteger(Number(value)) && Number(value) > 0 ? Number(value) : fallback;

    function renderCities() {
      const container = form.querySelector('#filters');
      if (!container || !form.querySelector('#city_input')) return;
      container.replaceChildren();
      (field('city')?.value || '').split(',').filter(Boolean).forEach(city => {
        const chip = document.createElement('div'); chip.className = 'public-filter-chip';
        const label = document.createElement('span'); label.textContent = `${cityLabel}: ${city}`;
        const remove = document.createElement('button'); remove.type = 'button';
        remove.className = 'public-filter-chip__remove'; remove.textContent = '×';
        remove.setAttribute('aria-label', `${removeLabel}: ${city}`);
        remove.addEventListener('click', event => {
          event.stopPropagation();
          field('city').value = field('city').value.split(',').filter(value => value !== city).join(',');
          submit();
        });
        chip.append(label, remove); container.append(chip);
      });
    }

    function hydrate() {
      const query = new URLSearchParams(global.location.search);
      params = {};
      names.forEach(name => {
        const value = (query.get(name) || '').trim();
        if (value) params[name] = value;
      });
      Object.assign(params, fixed);
      params.per_page = positive(query.get('per_page'), 12);
      page = positive(query.get('page'), 1);
      names.forEach(name => {
        if (field(name)) field(name).value = params[name] || '';
      });
      ['start', 'end'].forEach(edge => {
        const display = field(`display_date_${edge}`);
        const value = params[`date_${edge}`] || '';
        const formatted = /^\d{4}-\d{2}-\d{2}$/.test(value) ? value.split('-').reverse().join('.') : '';
        if (display) {
          display.value = formatted;
          display._flatpickr?.setDate?.(formatted, false);
        }
      });
      dateRange?.setValues(params.date_start, params.date_end);
      renderCities();
      return { ...params };
    }

    function write(push = false) {
      const url = new URL(global.location.href);
      [...names, ...Object.keys(fixed), 'page', 'per_page', 'display_date_start', 'display_date_end'].forEach(name => url.searchParams.delete(name));
      Object.entries(params).forEach(([name, value]) => { if (value) url.searchParams.set(name, value); });
      url.searchParams.set('page', page);
      if (push && url.href !== global.location.href) global.history.pushState({}, '', url);
      else global.history.replaceState(global.history.state, '', url);
    }

    function submit() {
      const next = { per_page: params.per_page || 12 };
      let valid = true;
      names.forEach(name => { const value = field(name)?.value.trim(); if (value) next[name] = value; });
      ['start', 'end'].forEach(edge => {
        const display = field(`display_date_${edge}`);
        if (!display) return;
        if (display.dataset.invalidDateEntry) display.value = display.dataset.invalidDateEntry;
        delete next[`date_${edge}`];
        if (field(`date_${edge}`)) field(`date_${edge}`).value = '';
        if (!display.value.trim()) return;
        const match = display.value.trim().match(/^(\d{1,2})\.(\d{1,2})\.(\d{4})$/);
        if (!match) { valid = false; return; }
        const [day, month, year] = match.slice(1).map(Number);
        const date = new Date(Date.UTC(year, month - 1, day));
        if (date.getUTCFullYear() === year && date.getUTCMonth() === month - 1 && date.getUTCDate() === day) {
          next[`date_${edge}`] = `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
        } else valid = false;
        if (field(`date_${edge}`)) field(`date_${edge}`).value = next[`date_${edge}`] || '';
      });
      if (next.date_start && next.date_end && next.date_start > next.date_end) valid = false;
      const error = form.querySelector('#date-error');
      if (error) error.style.display = valid ? 'none' : 'block';
      ['start', 'end'].forEach(edge => field(`display_date_${edge}`)?.setAttribute('aria-invalid', String(!valid)));
      if (!valid) return null;
      dateRange?.setValues(next.date_start, next.date_end);
      Object.assign(next, fixed);
      params = next; page = 1; renderCities(); write(true);
      return onChange({ ...params }, page);
    }

    const restore = () => { hydrate(); return onChange({ ...params }, page); };
    global.addEventListener('popstate', restore);
    hydrate(); write();
    return { get params() { return { ...params }; }, get page() { return page; }, submit, renderCities,
      pageLoaded(result) { page = result.page; write(); },
      destroy() { global.removeEventListener('popstate', restore); dateRange?.destroy(); } };
  }

  global.UserPagination = { createLoadMoreController, createFilterHistory };
})(window);
