document.addEventListener("DOMContentLoaded", function () {
  function updateApprovalStatus() {
    const checkbox = document.getElementById("approved");
    const statusText = document.getElementById("approval-status");
    const container = document.getElementById("approval-container");

    if (checkbox.checked) {
      statusText.textContent = "Kyllä";
      container.style.backgroundColor = "var(--green-lighter)"; // Light green for approved
      container.style.color = "var(--green-darker)"; // Dark green text
    } else {
      statusText.textContent = "Ei";
      container.style.backgroundColor = "var(--red)"; // Light red for not approved
      container.style.color = "var(--white)"; // Dark red text
    }
  }

  // Initialize status on page load
  updateApprovalStatus();

  // Add event listener to update status on checkbox change
  document
    .getElementById("approval-container")
    .addEventListener("change", updateApprovalStatus);
});
