function updateAdminBooleanStatus(control) {
  const statusId = control.getAttribute("aria-describedby")
    ?.split(/\s+/)
    .find((id) => document.getElementById(id)?.classList.contains("admin-check-row__status"));
  const status = statusId ? document.getElementById(statusId) : null;
  if (!status) return;

  status.textContent = control.checked
    ? status.dataset.trueLabel
    : status.dataset.falseLabel;
}

const adminModalTriggers = new WeakMap();

function restoreAdminModalFocus(modal) {
  const trigger = adminModalTriggers.get(modal);
  if (trigger?.isConnected) trigger.focus();
}

function rememberAdminModalTrigger(trigger) {
  const targetSelector = trigger.getAttribute("data-bs-target");
  const modal = targetSelector ? document.querySelector(targetSelector) : null;
  if (!modal) return;

  adminModalTriggers.set(modal, trigger);
  modal.addEventListener(
    "hidden.bs.modal",
    () => restoreAdminModalFocus(modal),
    { once: true },
  );
}

document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("[data-admin-boolean]").forEach(updateAdminBooleanStatus);
});

// Table viewports scroll horizontally, which would clip their action menus.
// Configure each toggle when it is first used, before Bootstrap creates its
// dropdown, so tables replaced later, such as by the user list's
// search and paging, get the same fixed positioning.
const TABLE_DROPDOWN = '.admin-data-view__viewport [data-bs-toggle="dropdown"]';
function useFixedTableDropdown(event) {
  const toggle = event.target instanceof Element ? event.target.closest(TABLE_DROPDOWN) : null;
  if (!toggle || toggle.hasAttribute("data-bs-popper-config")) return;
  // Bootstrap reads these data attributes when it creates the dropdown.
  toggle.setAttribute("data-bs-boundary", "viewport");
  toggle.setAttribute("data-bs-popper-config", '{"strategy":"fixed"}');
}
// Bootstrap's own delegated handlers listen on document in the capture phase,
// so listen on window to run before them.
window.addEventListener("click", useFixedTableDropdown, true);
window.addEventListener("keydown", useFixedTableDropdown, true);

document.addEventListener("change", (event) => {
  if (event.target.matches("[data-admin-boolean]")) {
    updateAdminBooleanStatus(event.target);
  }

  if (event.target.matches(".admin-page-size select")) {
    const url = new URL(window.location.href);
    url.searchParams.set("per_page", event.target.value);
    url.searchParams.set("page", "1");
    window.location.assign(url.toString());
  }
});

document.addEventListener("click", (event) => {
  const modalTrigger = event.target.closest('[data-bs-toggle="modal"][data-bs-target]');
  if (modalTrigger) rememberAdminModalTrigger(modalTrigger);

  const dismissButton = event.target.closest('[data-bs-dismiss="modal"]');
  const dismissedModal = dismissButton?.closest(".modal");
  if (dismissedModal) {
    // Also restore after the dismiss click. This is a resilient fallback for
    // reduced-motion/test environments where a transition-end event is absent.
    setTimeout(() => restoreAdminModalFocus(dismissedModal), 0);
  }
});
