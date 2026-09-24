(() => {
  function replacePlaceholders(fragment, replacements) {
    fragment.querySelectorAll('*').forEach((element) => {
      for (const attribute of ['id', 'name', 'for', 'value', 'data-organization-id']) {
        if (!element.hasAttribute(attribute)) continue;
        let value = element.getAttribute(attribute);
        Object.entries(replacements).forEach(([placeholder, replacement]) => {
          value = value.replaceAll(placeholder, replacement);
        });
        element.setAttribute(attribute, value);
      }
      if (element.matches('[data-organizer-linked-name]')) {
        element.textContent = replacements.__ORGANIZATION_NAME__ || '';
      }
      if (element.matches('[data-organizer-linked-email]')) {
        element.textContent = replacements.__ORGANIZATION_EMAIL__ || '';
        element.parentElement.hidden = !replacements.__ORGANIZATION_EMAIL__;
      }
      if (element.matches('[data-organizer-linked-website]')) {
        element.textContent = replacements.__ORGANIZATION_WEBSITE__ || '';
        element.parentElement.hidden = !replacements.__ORGANIZATION_WEBSITE__;
      }
    });
  }

  function initializeOrganizerEditor(editor) {
    const list = editor.querySelector('[data-organizer-list]');
    const emptyState = editor.querySelector('[data-organizer-empty]');
    const error = editor.querySelector('[data-organizer-error]');
    const organizationSelect = editor.querySelector('[data-organization-select]');

    function updateEmptyState() {
      emptyState.hidden = Boolean(list.querySelector('[data-organizer-row]'));
    }

    function nextIndex() {
      const index = Number.parseInt(editor.dataset.nextIndex || '1', 10);
      editor.dataset.nextIndex = String(index + 1);
      return String(index);
    }

    function appendFromTemplate(kind, replacements = {}) {
      const template = editor.querySelector(`[data-organizer-template="${kind}"]`);
      const fragment = template.content.cloneNode(true);
      replacePlaceholders(fragment, { __INDEX__: nextIndex(), ...replacements });
      const row = fragment.querySelector('[data-organizer-row]');
      list.append(fragment);
      error.hidden = true;
      error.textContent = '';
      updateEmptyState();
      const focusTarget = row.querySelector('input:not([type="hidden"])')
        || row.querySelector('button');
      window.setTimeout(() => focusTarget?.focus(), 0);
    }

    editor.querySelector('[data-add-linked-organizer]').addEventListener('click', () => {
      const option = organizationSelect.selectedOptions[0];
      const organizationId = option?.value || '';
      if (!organizationId) {
        error.textContent = editor.dataset.selectOrganization;
        error.hidden = false;
        organizationSelect.focus();
        return;
      }
      if (list.querySelector(`[data-organization-id="${CSS.escape(organizationId)}"]`)) {
        error.textContent = editor.dataset.duplicateOrganization;
        error.hidden = false;
        organizationSelect.focus();
        return;
      }
      appendFromTemplate('linked', {
        __ORGANIZATION_ID__: organizationId,
        __ORGANIZATION_NAME__: option.dataset.name || option.textContent.trim(),
        __ORGANIZATION_EMAIL__: option.dataset.email || '',
        __ORGANIZATION_WEBSITE__: option.dataset.website || ''
      });
      organizationSelect.value = '';
    });

    editor.querySelector('[data-add-freeform-organizer]').addEventListener('click', () => {
      appendFromTemplate('freeform');
    });

    list.addEventListener('click', (event) => {
      const removeButton = event.target.closest('[data-remove-organizer]');
      if (!removeButton) return;
      const row = removeButton.closest('[data-organizer-row]');
      const nextFocus = row.nextElementSibling || row.previousElementSibling;
      row.remove();
      updateEmptyState();
      (nextFocus?.querySelector('input:not([type="hidden"])')
        || nextFocus?.querySelector('button')
        || editor.querySelector('[data-add-freeform-organizer]')).focus();
    });

    list.addEventListener('change', (event) => {
      if (!event.target.matches('input[name^="organizer_is_private_"]')) return;
      const row = event.target.closest('[data-organizer-row]');
      const emailToggle = row.querySelector('input[name^="organizer_show_email_"]');
      if (event.target.checked && emailToggle) emailToggle.checked = false;
    });

    updateEmptyState();
  }

  document.querySelectorAll('[data-organizer-editor]').forEach(initializeOrganizerEditor);
})();
