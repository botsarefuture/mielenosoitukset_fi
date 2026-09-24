/*
 * Shared load-more contract for user-facing demonstration listings.
 * Pages provide the API-specific loader; this controller owns button state.
 */
(function (global) {
  "use strict";

  function createLoadMoreController({
    button,
    loadPage,
    initialLabel = "Lataa lisää",
    loadingLabel = "Ladataan...",
  }) {
    if (!button || typeof loadPage !== "function") {
      return null;
    }

    let currentPage = 1;
    let totalPages = 1;
    let loading = false;

    function setState(page, pageCount) {
      currentPage = Number(page) || 1;
      totalPages = Number(pageCount) || 1;
      button.textContent = initialLabel;
      button.disabled = false;
      button.classList.remove("loading");
      button.style.display = currentPage < totalPages ? "" : "none";
    }

    async function loadNext() {
      if (loading || currentPage >= totalPages) return;
      loading = true;
      button.disabled = true;
      button.classList.add("loading");
      button.textContent = loadingLabel;

      try {
        await loadPage(currentPage + 1);
      } finally {
        loading = false;
        if (currentPage < totalPages) {
          button.disabled = false;
          button.classList.remove("loading");
          button.textContent = initialLabel;
        }
      }
    }

    button.addEventListener("click", loadNext);
    setState(currentPage, totalPages);

    return {
      button,
      setState,
      get currentPage() {
        return currentPage;
      },
      get totalPages() {
        return totalPages;
      },
    };
  }

  global.UserPagination = { createLoadMoreController };
})(window);
