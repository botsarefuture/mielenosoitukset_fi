(() => {
  "use strict";

  const wrap = document.getElementById("notif-wrap");
  if (!wrap) return;

  const button = document.getElementById("notif-btn");
  const panel = document.getElementById("notif-panel");
  const list = document.getElementById("notif-list");
  const markReadButton = document.getElementById("mark-read-btn");
  if (!button || !panel || !list || !markReadButton) return;

  const labels = {
    empty: list.dataset.emptyLabel || "",
    loading: list.dataset.loadingLabel || "",
    loadError: list.dataset.loadErrorLabel || "",
    markError: list.dataset.markErrorLabel || "",
  };
  const locale = document.documentElement.lang || "fi-FI";
  const fallbackFormatter = new Intl.DateTimeFormat(locale, {
    dateStyle: "medium",
    timeStyle: "short",
  });
  const iconByType = {
    org_invite: "fa-building-circle-check",
    friend_request: "fa-user-plus",
    demo_invite: "fa-bullhorn",
    demo_cancelled: "fa-ban",
    recurring_demo_update: "fa-arrows-rotate",
  };

  const formatTimestamp = (value) => {
    if (window.timeago?.format) {
      try {
        return window.timeago.format(value);
      } catch (_) {
        // Fall through to the browser's locale-aware formatter.
      }
    }

    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return String(value || "");
    return fallbackFormatter.format(date);
  };

  const safeNotificationHref = (value) => {
    if (value === "#") return "#";
    if (typeof value !== "string" || !value.startsWith("/")) return "#";

    try {
      const url = new URL(value, window.location.origin);
      if (url.origin !== window.location.origin) return "#";
      return `${url.pathname}${url.search}${url.hash}`;
    } catch (_) {
      return "#";
    }
  };

  const createIcon = (classes) => {
    const icon = document.createElement("i");
    icon.className = classes;
    icon.setAttribute("aria-hidden", "true");
    return icon;
  };

  const renderState = (message, state = "empty") => {
    const status = document.createElement("div");
    status.className = `notif-state notif-state--${state}`;
    status.setAttribute("role", state === "error" ? "alert" : "status");

    if (state === "loading") {
      status.appendChild(createIcon("fa-solid fa-spinner fa-spin"));
    } else if (state === "error") {
      status.appendChild(createIcon("fa-solid fa-circle-exclamation"));
    }

    const text = document.createElement("span");
    text.textContent = message;
    status.appendChild(text);
    list.replaceChildren(status);
    list.setAttribute("aria-busy", state === "loading" ? "true" : "false");
  };

  const updateBadge = (count) => {
    button.querySelector(".notif-badge")?.remove();
    if (!count) return;

    const badge = document.createElement("span");
    badge.className = "notif-badge position-absolute top-0 start-100 translate-middle";
    badge.textContent = count > 99 ? "99+" : String(count);
    button.appendChild(badge);
  };

  const createNotificationItem = (notification) => {
    const item = document.createElement("div");
    item.className = `notif-item${notification.read ? "" : " is-unread"}`;

    const link = document.createElement("a");
    link.className = "notif-item__link";
    link.href = safeNotificationHref(notification.link);

    const iconWrap = document.createElement("span");
    iconWrap.className = "notif-item__icon";
    iconWrap.appendChild(
      createIcon(`fa-solid ${iconByType[notification.type] || "fa-circle-info"}`),
    );

    const content = document.createElement("span");
    content.className = "notif-item__content";

    const message = document.createElement("span");
    message.className = "notif-item__message";
    message.textContent = String(notification.message || "");

    const timestamp = document.createElement("time");
    timestamp.className = "notif-item__time";
    timestamp.dateTime = String(notification.time || "");
    timestamp.textContent = formatTimestamp(notification.time);

    content.append(message, timestamp);
    link.append(iconWrap, content);
    item.appendChild(link);
    return item;
  };

  const render = (notifications) => {
    const unreadCount = notifications.filter((notification) => !notification.read).length;
    updateBadge(unreadCount);
    markReadButton.classList.toggle("d-none", unreadCount === 0);

    if (notifications.length === 0) {
      renderState(labels.empty);
      return;
    }

    const fragment = document.createDocumentFragment();
    notifications.forEach((notification) => {
      fragment.appendChild(createNotificationItem(notification));
    });
    list.replaceChildren(fragment);
    list.setAttribute("aria-busy", "false");
  };

  const loadNotifications = async ({ showLoading = false } = {}) => {
    if (showLoading) renderState(labels.loading, "loading");

    try {
      const response = await fetch("/api/notifications/", {
        headers: { Accept: "application/json" },
        credentials: "same-origin",
      });
      if (!response.ok) throw new Error(`Notification request failed: ${response.status}`);

      const notifications = await response.json();
      if (!Array.isArray(notifications)) throw new TypeError("Notification response must be an array");
      render(notifications);
    } catch (error) {
      console.error(error);
      if (button.getAttribute("aria-expanded") === "true") {
        renderState(labels.loadError, "error");
      }
    }
  };

  const open = () => {
    button.setAttribute("aria-expanded", "true");
    wrap.setAttribute("aria-expanded", "true");
    panel.setAttribute("aria-hidden", "false");
    loadNotifications({ showLoading: true });
  };

  const close = ({ restoreFocus = false } = {}) => {
    button.setAttribute("aria-expanded", "false");
    wrap.setAttribute("aria-expanded", "false");
    panel.setAttribute("aria-hidden", "true");
    if (restoreFocus) button.focus();
  };

  button.addEventListener("click", (event) => {
    event.stopPropagation();
    if (button.getAttribute("aria-expanded") === "true") close();
    else open();
  });

  document.addEventListener("click", (event) => {
    if (!wrap.contains(event.target)) close();
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && button.getAttribute("aria-expanded") === "true") {
      close({ restoreFocus: true });
    }
  });

  markReadButton.addEventListener("click", async (event) => {
    event.preventDefault();
    markReadButton.disabled = true;

    try {
      const response = await fetch("/api/notifications/mark-read", {
        method: "POST",
        headers: { Accept: "application/json" },
        credentials: "same-origin",
      });
      if (!response.ok) throw new Error(`Mark-read request failed: ${response.status}`);
      await loadNotifications();
    } catch (error) {
      console.error(error);
      if (typeof window.displayFlashMessage === "function") {
        window.displayFlashMessage("error", labels.markError);
      } else {
        renderState(labels.markError, "error");
      }
    } finally {
      markReadButton.disabled = false;
    }
  });

  window.setInterval(() => loadNotifications(), 60_000);
})();
