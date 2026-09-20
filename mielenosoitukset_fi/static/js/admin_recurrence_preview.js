"use strict";

document.addEventListener("DOMContentLoaded", () => {
  const preview = document.querySelector("[data-recurrence-preview]");
  const form = document.getElementById("recu-demo-form");
  if (!preview || !form) return;

  const status = preview.querySelector("[data-preview-status]");
  const dates = preview.querySelector("[data-preview-dates]");
  const note = preview.querySelector("[data-preview-note]");
  const watchedNames = new Set([
    "date",
    "frequency_type",
    "frequency_interval",
    "weekday",
    "monthly_option",
    "day_of_month",
    "nth_weekday",
    "weekday_of_month",
    "end_date",
    "break_dates",
  ]);
  let debounceTimer;
  let requestController;

  const label = (name, fallback) => preview.dataset[name] || fallback;
  const withCount = (template, count) => template.replace("__COUNT__", String(count));

  function buildQuery() {
    const query = new URLSearchParams();
    for (const name of watchedNames) {
      const fields = form.querySelectorAll(`[name="${name}"]`);
      fields.forEach((field) => {
        if ((field.type === "radio" || field.type === "checkbox") && !field.checked) return;
        if (field.value) query.append(name, field.value);
      });
    }
    return query;
  }

  function clearPreview() {
    dates.replaceChildren();
    note.hidden = true;
    note.textContent = "";
  }

  function renderDates(payload) {
    clearPreview();
    if (!payload.dates.length) {
      status.textContent = label("emptyLabel", "Nykyisillä asetuksilla ei synny tulevia päivämääriä.");
      return;
    }

    status.textContent = withCount(
      label("countLabel", "Seuraavat __COUNT__ päivämäärää"),
      payload.dates.length,
    );
    const locale = document.documentElement.lang || "fi";
    payload.dates.forEach((isoDate) => {
      const item = document.createElement("li");
      const time = document.createElement("time");
      time.dateTime = isoDate;
      time.textContent = new Date(`${isoDate}T12:00:00`).toLocaleDateString(locale, {
        weekday: "short",
        day: "numeric",
        month: "long",
        year: "numeric",
      });
      item.append(time);
      dates.append(item);
    });

    const notes = [];
    if (payload.has_more) notes.push(label("moreLabel", "Lisää päivämääriä syntyy esikatselun jälkeen."));
    if (payload.excluded_break_dates) {
      notes.push(withCount(label("breakLabel", "__COUNT__ taukopäivää on jätetty pois."), payload.excluded_break_dates));
    }
    if (notes.length) {
      note.textContent = notes.join(" ");
      note.hidden = false;
    }
  }

  async function refreshPreview() {
    const query = buildQuery();
    if (!query.get("date")) {
      clearPreview();
      status.textContent = label("startLabel", "Täytä alkupäivä nähdäksesi tulevat päivämäärät.");
      return;
    }

    requestController?.abort();
    requestController = new AbortController();
    status.textContent = label("loadingLabel", "Lasketaan tulevia päivämääriä…");
    try {
      const response = await fetch(`${preview.dataset.previewEndpoint}?${query}`, {
        headers: { Accept: "application/json" },
        signal: requestController.signal,
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.message || "Preview failed");
      renderDates(payload);
    } catch (error) {
      if (error.name === "AbortError") return;
      clearPreview();
      status.textContent = error.message || label("errorLabel", "Päivämäärien esikatselua ei voitu laskea.");
    }
  }

  function scheduleRefresh(event) {
    if (event && !watchedNames.has(event.target.name)) return;
    window.clearTimeout(debounceTimer);
    debounceTimer = window.setTimeout(refreshPreview, 180);
  }

  form.addEventListener("input", scheduleRefresh);
  form.addEventListener("change", scheduleRefresh);
  const breakDateList = document.getElementById("break-date-list");
  if (breakDateList) {
    new MutationObserver(() => scheduleRefresh()).observe(breakDateList, {
      childList: true,
    });
  }
  refreshPreview();
});
