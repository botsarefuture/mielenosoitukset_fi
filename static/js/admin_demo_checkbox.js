document.addEventListener("DOMContentLoaded", function () {
  function updateApprovalStatus() {
    const checkbox = document.getElementById("approved");
    const statusText = document.getElementById("approval-status");
    const container = document.getElementById("approval-container");

    if (checkbox.checked) {
      statusText.textContent = "Kyllä";
      container.style.backgroundColor = "#d4edda"; // Light green for approved
      container.style.color = "#155724"; // Dark green text
    } else {
      statusText.textContent = "Ei";
      container.style.backgroundColor = "#f8d7da"; // Light red for not approved
      container.style.color = "#721c24"; // Dark red text
    }
  }

  // Initialize status on page load
  updateApprovalStatus();

  // Add event listener to update status on checkbox change
  document
    .getElementById("approval-wrapper")
    .addEventListener("change", updateApprovalStatus);
});
