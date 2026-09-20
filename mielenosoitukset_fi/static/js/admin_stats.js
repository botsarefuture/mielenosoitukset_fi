"use strict";

document.addEventListener("DOMContentLoaded", () => {
  const link = document.getElementById("matomo-link");
  const label = link?.querySelector("[data-matomo-label]");
  const endpoint = link?.dataset.liveUrl;
  if (!link || !label || !endpoint) return;

  fetch(endpoint, { headers: { Accept: "application/json" } })
    .then((response) => {
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return response.json();
    })
    .then((payload) => {
      if (!payload.enabled) {
        label.textContent = link.dataset.unavailableLabel;
        return;
      }
      label.textContent = `Matomo · ${payload.visits.length} ${link.dataset.visitorLabel}`;
    })
    .catch(() => {
      label.textContent = link.dataset.unavailableLabel;
    });
});
