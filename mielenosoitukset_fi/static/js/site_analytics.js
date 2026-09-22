/**
 * Built-in analytics: tiny beacon for browser-only signals.
 *
 * Basic pageviews are recorded server-side; this script only reports the few
 * interactions that cannot be seen from requests at all, and it is strictly
 * allowlisted server-side:
 *   - map_interaction: visitor touched the map on a page that embeds one
 *     (recorded once per page load, with the page path)
 *   - external_link: visitor clicked a link to another site (recorded with
 *     the target *hostname* only, so counters stay small and useful)
 *
 * No identifiers, no cookies, no storage — each event is a single fire-and-
 * forget beacon. Admin and account areas are skipped entirely.
 */
(function () {
  "use strict";
  if (typeof navigator === "undefined" || !navigator.sendBeacon) return;

  var path = window.location.pathname || "/";
  if (path.indexOf("/admin") === 0 || path.indexOf("/users") === 0) return;

  function send(event, resourceId) {
    try {
      navigator.sendBeacon(
        "/api/analytics/event",
        new Blob([JSON.stringify({ event: event, resource_id: resourceId || "" })], {
          type: "application/json",
        })
      );
    } catch (err) {
      /* analytics must never break the page */
    }
  }

  // Map interaction — at most one event per page load.
  function bindMap() {
    var mapEl = document.querySelector(".leaflet-container");
    if (!mapEl || mapEl.dataset.analyticsMapBound) return;
    mapEl.dataset.analyticsMapBound = "1";
    mapEl.addEventListener(
      "pointerdown",
      function () {
        send("map_interaction", path.slice(0, 200));
      },
      { once: true, passive: true }
    );
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bindMap, { once: true });
  } else {
    bindMap();
  }

  // External link clicks — target hostname only.
  document.addEventListener(
    "click",
    function (event) {
      var target = event.target;
      while (target && target !== document) {
        if (target.tagName === "A") break;
        target = target.parentNode;
      }
      if (!target || target === document) return;
      var href = target.getAttribute("href") || "";
      if (href.indexOf("http://") !== 0 && href.indexOf("https://") !== 0) return;
      try {
        var url = new URL(href, window.location.href);
        if (url.hostname === window.location.hostname) return;
        send("external_link", url.hostname.slice(0, 200));
      } catch (err) {
        /* ignore malformed hrefs */
      }
    },
    true
  );
})();
