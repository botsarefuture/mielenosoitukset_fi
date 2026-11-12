/**
 * Built-in analytics: tiny beacons for browser-only signals.
 *
 * Basic pageviews are recorded server-side; this script only reports the few
 * interactions that cannot be seen from requests at all, and it is strictly
 * allowlisted server-side:
 *   - map_interaction: visitor touched the map on a page that embeds one
 *     (recorded once per page load, with the page path)
 *   - external_link: visitor clicked a link to another site (recorded with
 *     the target *hostname* only, so counters stay small and useful)
 *
 * Web Vitals are also submitted as metric name + numeric value only. The
 * server derives a coarse route family and device bucket, then updates a
 * bounded daily histogram. No metric id, URL, DOM target, visitor, cookie or
 * browser storage is sent. Admin and account areas are skipped entirely.
 */
(function () {
  "use strict";
  if (typeof navigator === "undefined" || !navigator.sendBeacon) return;

  var path = window.location.pathname || "/";
  if (
    path.indexOf("/admin") === 0 ||
    path.indexOf("/users") === 0 ||
    path.indexOf("/board") === 0 ||
    path.indexOf("/developer") === 0
  ) return;
  var sentVitals = Object.create(null);
  var pendingVitals = Object.create(null);

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

  function sendVital(metric) {
    if (!metric || ["CLS", "INP", "LCP", "TTFB"].indexOf(metric.name) === -1) return;
    if (typeof metric.value !== "number" || !isFinite(metric.value) || metric.value < 0) return;
    if (sentVitals[metric.name]) return;
    pendingVitals[metric.name] = metric.value;
  }

  function flushVitals() {
    ["CLS", "INP", "LCP", "TTFB"].forEach(function (name) {
      if (!Object.prototype.hasOwnProperty.call(pendingVitals, name) || sentVitals[name]) return;
      try {
        var queued = navigator.sendBeacon(
          "/api/analytics/vitals",
          new Blob([JSON.stringify({ metric: name, value: pendingVitals[name] })], {
            type: "application/json",
          })
        );
        if (queued) sentVitals[name] = true;
      } catch (err) {
        /* analytics must never break the page */
      }
    });
  }

  // The pinned, self-hosted web-vitals library is deferred before this file.
  // Unsupported browsers or a failed optional library download simply omit
  // these metrics without affecting the page or the other analytics beacons.
  if (window.webVitals) {
    window.webVitals.onCLS(sendVital, { reportAllChanges: true });
    window.webVitals.onINP(sendVital, { reportAllChanges: true });
    window.webVitals.onLCP(sendVital, { reportAllChanges: true });
    window.webVitals.onTTFB(sendVital);
  }

  window.addEventListener("pagehide", flushVitals);

  document.addEventListener("visibilitychange", function () {
    if (document.visibilityState === "hidden") flushVitals();
  });

  window.addEventListener("pageshow", function (event) {
    if (!event.persisted) return;
    // web-vitals starts fresh metric instances for a restored bfcache visit.
    // Clear the previous visit only after it has been flushed while hidden.
    sentVitals = Object.create(null);
    pendingVitals = Object.create(null);
  });

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
