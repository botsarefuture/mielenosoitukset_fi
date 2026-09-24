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
