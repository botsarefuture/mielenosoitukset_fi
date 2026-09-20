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

  if (event.target.matches(".admin-page-size select")) {
    const url = new URL(window.location.href);
    url.searchParams.set("per_page", event.target.value);
    url.searchParams.set("page", "1");
    window.location.assign(url.toString());
  }
});
