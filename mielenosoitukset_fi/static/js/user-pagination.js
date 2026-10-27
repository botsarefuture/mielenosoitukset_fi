/*
 * Shared load-more contract for user-facing demonstration listings.
 * Pages provide the API-specific loader; this controller owns button state.
 */
(function (global) {
  "use strict";

  // Keep only a small contiguous DOM window. Removed pages are re-fetched when
  // scrolling back, not retained as hidden nodes or an unbounded data cache.
  function createPageWindow(grid, maxPages = 5) {
    grid.classList.add('public-list-window');
    let scrollHost = global;
    for (let node = grid.parentElement; node; node = node.parentElement) {
      if (node !== document.scrollingElement && /auto|scroll/.test(getComputedStyle(node).overflowY)) {
        scrollHost = node;
        break;
      }
    }
    const viewport = () => scrollHost === global ? { top: 0, bottom: innerHeight }
      : scrollHost.getBoundingClientRect();
    let pages = [];
    const pinned = node => node.contains(document.activeElement);
    const anchorFor = node => node && getComputedStyle(node).display === 'contents'
      ? node.firstElementChild : node;
    function pageBounds(node) {
      if (getComputedStyle(node).display !== 'contents') return node.getBoundingClientRect();
      // Layout-free React roots retain ownership/focus, but have no box of
      // their own. Evict only when all of the page's cards are off screen.
      const boxes = Array.from(node.children, child => child.getBoundingClientRect());
      return boxes.length ? {
        top: Math.min(...boxes.map(box => box.top)),
        bottom: Math.max(...boxes.map(box => box.bottom)),
      } : node.getBoundingClientRect();
    }
    function canExtend(previous = false, manual = false) {
      if (pages.length < maxPages) return true;
      const edge = previous ? pages[pages.length - 1] : pages[0];
      const rect = pageBounds(edge.node);
      const bounds = viewport();
      return !pinned(edge.node) && (manual || (previous ? rect.top > bounds.bottom : rect.bottom < bounds.top));
    }
    function refreshLayout() {
      if (getComputedStyle(grid).display !== 'grid') return;
      // An old column start could create implicit tracks after narrowing.
      grid.style.removeProperty('--public-list-first-column');
      const columns = getComputedStyle(grid).gridTemplateColumns.split(/\s+/).filter(Boolean).length || 1;
      // Keep surviving cards in their global columns when a page is evicted.
      const column = ((pages[0]?.start || 1) - 1) % columns + 1;
      grid.style.setProperty('--public-list-first-column', column);
    }
    return {
      reset() { pages = []; grid.replaceChildren(); grid.style.removeProperty('--public-list-first-column'); },
      refreshLayout,
      preservePosition(change) {
        const anchor = anchorFor(pages[0]?.node);
        const oldTop = anchor?.getBoundingClientRect().top;
        change();
        if (anchor?.isConnected && oldTop !== undefined) {
          scrollHost.scrollBy({ top: anchor.getBoundingClientRect().top - oldTop, behavior: 'instant' });
        }
      },
      canExtend,
      scrollHost,
      viewport,
      get first() { return pages[0]?.page; },
      get last() { return pages[pages.length - 1]?.page; },
      get range() {
        return { start: pages[0]?.start || 0, end: pages[pages.length - 1]?.end || 0,
          count: pages.reduce((sum, entry) => sum + entry.count, 0) };
      },
      mount(data, render) {
        if (!data.results.length || pages.some(entry => entry.page === data.page)) return [];
        const previous = pages.length && data.page < pages[0].page;
        // Use a surviving card as the scroll anchor. CSS scroll anchoring is
        // disabled for this grid so the correction is applied exactly once.
        const anchor = anchorFor(previous ? pages[0]?.node : pages[pages.length - 1]?.node);
        const oldTop = anchor?.getBoundingClientRect().top;
        const node = document.createElement('div');
        node.className = 'demos-grid public-list-page';
        node.dataset.listPage = data.page;
        const cards = render(node);
        const entry = { page: data.page, node, count: data.results.length,
          start: data.result_start || ((data.page - 1) * data.per_page + 1),
          end: data.result_end || (data.page * data.per_page) };
        if (previous) { pages.unshift(entry); grid.prepend(node); }
        else { pages.push(entry); grid.append(node); }
        if (pages.length > maxPages) {
          const removed = previous ? pages.pop() : pages.shift();
          removed.node.remove();
        }
        refreshLayout();
        if (anchor?.isConnected && oldTop !== undefined) {
          scrollHost.scrollBy({ top: anchor.getBoundingClientRect().top - oldTop, behavior: 'instant' });
        }
        return cards;
      },
    };
  }

  function createLoadMoreController({
    button = null,
    sentinel = null,
    loadPage,
    initialLabel = "Lataa lisää",
    loadingLabel = "Ladataan...",
    rootMargin = "1000px",
    windowed = false,
  }) {
    if ((!button && !sentinel) || typeof loadPage !== "function") {
      return null;
    }

    let currentPage = 1;
    let totalPages = 1;
    let loading = false;
    let observer = null;
    let generation = 0;
    let destroyed = false;
    let autoFailed = false;
    let autoFrame = null;
    let lastScroll = 0;
    let direction = 1;
    const automatic = !global.navigator.connection?.saveData;
    const pageWindow = windowed ? createPageWindow(document.getElementById('demos-grid')) : null;
    const scrollHost = pageWindow?.scrollHost || global;
    const scrollPosition = () => scrollHost === global ? global.scrollY : scrollHost.scrollTop;
    lastScroll = scrollPosition();
    const previousButton = windowed ? document.getElementById('load-previous-btn') : null;
    if (pageWindow) global.publicListWindow = pageWindow;
    if (previousButton) document.getElementById('demos-grid').before(previousButton);

    function setButtonState() {
      if (!button) return;
      button.textContent = initialLabel;
      button.disabled = loading;
      button.classList.remove("loading");
      button.hidden = currentPage >= totalPages;
      if (previousButton) {
        const hidden = !pageWindow.first || pageWindow.first <= 1;
        if (previousButton.hidden !== hidden) {
          // Showing/hiding Previous also changes the grid's top position.
          pageWindow.preservePosition(() => { previousButton.hidden = hidden; });
        }
        previousButton.disabled = loading;
      }
    }

    function setState(page, pageCount) {
      currentPage = pageWindow?.last || Number(page) || 1;
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

    async function loadNext(previous = false, manual = false) {
      // A DOM event is not the previous-page boolean.
      manual = manual || previous?.type === 'click';
      previous = previous === true;
      const target = previous ? pageWindow?.first - 1 : currentPage + 1;
      if (destroyed || loading || target < 1 || target > totalPages || !Number.isFinite(target)) return;
      if (pageWindow && !pageWindow.canExtend(previous, manual)) return;
      const requestGeneration = generation;
      loading = true;
      if (previousButton) previousButton.disabled = true;
      if (button) {
        button.disabled = true;
        button.classList.add("loading");
        button.textContent = loadingLabel;
      }

      try {
        const result = await loadPageWithState(target, { append: true, previous, manual }, requestGeneration);
        if (requestGeneration === generation) autoFailed = !result;
      } catch (error) {
        if (requestGeneration === generation) autoFailed = true;
        console.error('Public list load failed:', error);
        return null;
      } finally {
        if (requestGeneration === generation) {
          loading = false;
          setButtonState();
          lastScroll = scrollPosition();
          if (!autoFailed) scheduleAuto();
        }
      }
    }

    async function reload(options = {}) {
      const requestGeneration = ++generation;
      autoFailed = false;
      const page = Math.max(Number(options.page) || 1, 1);
      currentPage = page;
      totalPages = 1;
      loading = true;
      if (previousButton) previousButton.disabled = true;
      if (button) button.disabled = true;
      try {
        const result = await loadPageWithState(page, { ...options, reset: true }, requestGeneration);
        if (requestGeneration === generation) autoFailed = !result;
        return result;
      } finally {
        if (requestGeneration === generation) {
          loading = false;
          setButtonState();
          lastScroll = scrollPosition();
          direction = 1;
          if (!autoFailed) scheduleAuto();
        }
      }
    }

    function checkAuto() {
      autoFrame = null;
      if (!pageWindow || !automatic || destroyed || loading || autoFailed) return;
      // Never remove the control being activated with a keyboard or steal
      // focused cards. Failed requests require an explicit retry, not a loop.
      const control = direction < 0 ? previousButton : button;
      if (!control || control.hidden || control === document.activeElement) return;
      const rect = control.getBoundingClientRect();
      const bounds = pageWindow.viewport();
      if (rect.top <= bounds.bottom + 400 && rect.bottom >= bounds.top - 400) loadNext(direction < 0);
    }
    function scheduleAuto() {
      if (pageWindow && autoFrame === null) autoFrame = global.requestAnimationFrame(checkAuto);
    }
    function onScroll() {
      const delta = scrollPosition() - lastScroll;
      lastScroll = scrollPosition();
      if (!delta) return;
      direction = delta < 0 ? -1 : 1;
      scheduleAuto();
    }
    function onResize() { pageWindow.refreshLayout(); scheduleAuto(); }
    const loadPrevious = () => loadNext(true, true);

    if (button) button.addEventListener("click", loadNext);
    previousButton?.addEventListener('click', loadPrevious);
    if (pageWindow) scrollHost.addEventListener('scroll', onScroll, { passive: true });
    if (pageWindow) global.addEventListener('resize', onResize);
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
      resumeAuto() { autoFailed = false; lastScroll = scrollPosition(); scheduleAuto(); },
      get currentPage() {
        return currentPage;
      },
      get totalPages() {
        return totalPages;
      },
      destroy() {
        destroyed = true;
        generation += 1;
        if (autoFrame !== null) global.cancelAnimationFrame(autoFrame);
        observer?.disconnect();
        if (button) button.removeEventListener("click", loadNext);
        previousButton?.removeEventListener('click', loadPrevious);
        scrollHost.removeEventListener('scroll', onScroll);
        if (pageWindow) global.removeEventListener('resize', onResize);
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
      params.per_page = Math.min(positive(query.get('per_page'), 12), 100);
      page = positive(query.get('page'), 1);
      names.forEach(name => {
        if (field(name)) field(name).value = params[name] || '';
      });
      // Clear stale cross-field limits before setDate validates restored dates.
      const pickers = ['start', 'end'].map(edge => field(`display_date_${edge}`)?._flatpickr);
      pickers.forEach(picker => {
        picker?.set?.('minDate', undefined); picker?.set?.('maxDate', undefined);
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

    const restore = () => { hydrate(); return onChange({ ...params, history_restore: '1' }, page); };
    global.addEventListener('popstate', restore);
    hydrate(); write();
    return { get params() { return { ...params }; }, get page() { return page; }, submit, renderCities,
      pageLoaded(result) { page = result.page; write(); },
      destroy() { global.removeEventListener('popstate', restore); dateRange?.destroy(); } };
  }

  global.UserPagination = { createLoadMoreController, createFilterHistory, createPageWindow };
})(window);
