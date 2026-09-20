document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("[data-demo-edit-link-modal]").forEach((modalElement) => {
    const modal = bootstrap.Modal.getOrCreateInstance(modalElement);
    const duration = modalElement.querySelector("[data-demo-edit-link-duration]");
    const result = modalElement.querySelector("[data-demo-edit-link-result]");
    const rawLink = modalElement.querySelector("[data-demo-edit-link-value]");
    const expiry = modalElement.querySelector("[data-demo-edit-link-expiry]");
    const feedback = modalElement.querySelector("[data-demo-edit-link-feedback]");
    const title = modalElement.querySelector("[data-demo-edit-link-title]");
    const generateButton = modalElement.querySelector("[data-demo-edit-link-generate]");
    const copyButton = modalElement.querySelector("[data-demo-edit-link-copy]");
    const email = modalElement.querySelector("[data-demo-edit-link-email]");
    const sendButton = modalElement.querySelector("[data-demo-edit-link-send]");
    let demoId = modalElement.dataset.demoId || "";

    const endpointFor = (template) =>
      template.replace("__DEMO_ID__", encodeURIComponent(demoId));

    const copyCurrentLink = async () => {
      if (!rawLink.value) return false;
      try {
        await navigator.clipboard.writeText(rawLink.value);
        feedback.textContent = modalElement.dataset.copySuccess;
        return true;
      } catch (_error) {
        rawLink.focus();
        rawLink.select();
        feedback.textContent = modalElement.dataset.copyFallback;
        return false;
      }
    };

    modalElement.addEventListener("show.bs.modal", (event) => {
      const trigger = event.relatedTarget;
      if (trigger?.matches("[data-demo-edit-link-trigger]")) {
        demoId = trigger.dataset.demoId || "";
        title.textContent = trigger.dataset.demoTitle || "";
      }
    });

    generateButton?.addEventListener("click", async () => {
      if (!demoId) return;
      feedback.textContent = "";
      generateButton.disabled = true;
      try {
        const response = await fetch(endpointFor(modalElement.dataset.generateUrlTemplate), {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRF-Token": modalElement.dataset.csrfToken,
          },
          body: JSON.stringify({ duration: duration.value }),
        });
        const data = await response.json();
        if (!response.ok || data.status !== "OK") {
          feedback.textContent = data.message || modalElement.dataset.generateError;
          return;
        }
        rawLink.value = data.edit_link;
        expiry.textContent = `${modalElement.dataset.expiresLabel}: ${new Date(data.expires_at).toLocaleString()}`;
        result.classList.remove("d-none");
        await copyCurrentLink();
      } catch (_error) {
        feedback.textContent = modalElement.dataset.connectionError;
      } finally {
        generateButton.disabled = false;
      }
    });

    copyButton?.addEventListener("click", copyCurrentLink);

    sendButton?.addEventListener("click", async () => {
      if (!demoId || !email) return;
      feedback.textContent = "";
      sendButton.disabled = true;
      try {
        const response = await fetch(endpointFor(modalElement.dataset.emailUrlTemplate), {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRF-Token": modalElement.dataset.csrfToken,
          },
          body: JSON.stringify({ email: email.value, duration: duration.value }),
        });
        const data = await response.json();
        feedback.textContent = response.ok
          ? `${data.message} ${modalElement.dataset.expiresLabel}: ${new Date(data.expires_at).toLocaleString()}`
          : data.message || modalElement.dataset.emailError;
      } catch (_error) {
        feedback.textContent = modalElement.dataset.connectionError;
      } finally {
        sendButton.disabled = false;
      }
    });

    modalElement.addEventListener("hidden.bs.modal", () => {
      rawLink.value = "";
      expiry.textContent = "";
      feedback.textContent = "";
      title.textContent = "";
      if (email) email.value = "";
      result.classList.add("d-none");
    });

    // Static editor pages can initialize the modal without a trigger.
    if (demoId) modal.handleUpdate();
  });
});
