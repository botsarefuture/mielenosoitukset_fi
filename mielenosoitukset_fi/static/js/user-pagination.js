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

    function setButtonState() {
      if (!button) return;
      button.textContent = initialLabel;
      button.disabled = false;
      button.classList.remove("loading");
      button.hidden = currentPage >= totalPages;
    }

    function setState(page, pageCount) {
      currentPage = Number(page) || 1;
      totalPages = Number(pageCount) || 1;
      setButtonState();
    }

    async function loadPageWithState(pageNumber, options = {}) {
      const result = await loadPage(pageNumber, options);
      if (result) setState(result.page, result.total_pages);
      return result;
    }

    async function loadNext() {
      if (loading || currentPage >= totalPages) return;
      loading = true;
      if (button) {
        button.disabled = true;
        button.classList.add("loading");
        button.textContent = loadingLabel;
      }

      try {
        await loadPageWithState(currentPage + 1, { append: true });
      } finally {
        loading = false;
        if (button && currentPage < totalPages) setButtonState();
      }
    }

    async function reload(options = {}) {
      loading = true;
      try {
        return await loadPageWithState(1, { ...options, reset: true });
      } finally {
        loading = false;
        if (button) setButtonState();
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
