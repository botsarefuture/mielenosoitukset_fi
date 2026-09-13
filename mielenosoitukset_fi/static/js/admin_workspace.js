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

document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("[data-admin-boolean]").forEach(updateAdminBooleanStatus);
});

document.addEventListener("change", (event) => {
  if (event.target.matches("[data-admin-boolean]")) {
    updateAdminBooleanStatus(event.target);
  }
});
