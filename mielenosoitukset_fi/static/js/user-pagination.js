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
      if (result) setState(result.page, result.total_pages);
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
      currentPage = 1;
      totalPages = 1;
      loading = true;
      if (button) button.disabled = true;
      try {
        return await loadPageWithState(1, { ...options, reset: true }, requestGeneration);
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

  global.UserPagination = { createLoadMoreController };
})(window);
