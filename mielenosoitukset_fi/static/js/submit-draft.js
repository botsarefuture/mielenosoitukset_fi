(() => {
  "use strict";

  const form = document.getElementById("myForm");
  if (!form) return;

  const DRAFT_KEY = "mielenosoitukset.submit-draft.v2";
  const DRAFT_VERSION = 2;
  const DRAFT_TTL_MS = 24 * 60 * 60 * 1000;
  const MAX_DRAFT_BYTES = 150000;
  const MAX_ORGANIZERS = 20;
  const MAX_DESCRIPTION_CHARACTERS = 50000;
  const FIELD_NAMES = [
    "facebook",
    "facebook_imported",
    "facebook_image_url",
    "title",
    "tags",
    "default_language",
    "date",
    "start_time",
    "end_time",
    "type",
    "route",
    "city",
    "address",
    "submitter_role",
    "submitter_name",
    "submitter_email",
  ];
  const ALLOWED_DELTA_ATTRIBUTES = new Set([
    "bold",
    "italic",
    "link",
    "blockquote",
    "list",
  ]);

  let ready = false;
  let saveTimer = null;

  function storageGet(key) {
    try {
      return window.localStorage.getItem(key);
    } catch (error) {
      console.warn("Draft storage is unavailable", error);
      return null;
    }
  }

  function storageSet(key, value) {
    try {
      window.localStorage.setItem(key, value);
      return true;
    } catch (error) {
      console.warn("Draft could not be saved", error);
      return false;
    }
  }

  function storageRemove(key) {
    try {
      window.localStorage.removeItem(key);
    } catch (error) {
      console.warn("Draft could not be removed", error);
    }
  }

  function legacyKeys() {
    try {
      return Object.keys(window.localStorage).filter(
        (key) => key === "form_step" || key.startsWith("form_")
      );
    } catch (error) {
      return [];
    }
  }

  function clearLegacyDraft() {
    legacyKeys().forEach(storageRemove);
  }

  function clampStep(value) {
    const step = Number.parseInt(value, 10);
    return Number.isInteger(step) && step >= 1 && step <= 5 ? step : 1;
  }

  function boundedString(value, maxLength = 20000) {
    return typeof value === "string" ? value.slice(0, maxLength) : "";
  }

  function normalizeDelta(delta) {
    if (!delta || !Array.isArray(delta.ops) || delta.ops.length > 2000) {
      return null;
    }

    let characterCount = 0;
    const ops = [];
    for (const rawOperation of delta.ops) {
      if (!rawOperation || typeof rawOperation.insert !== "string") {
        return null;
      }

      characterCount += rawOperation.insert.length;
      if (characterCount > MAX_DESCRIPTION_CHARACTERS) {
        return null;
      }

      const operation = { insert: rawOperation.insert };
      if (rawOperation.attributes && typeof rawOperation.attributes === "object") {
        const attributes = {};
        Object.entries(rawOperation.attributes).forEach(([name, value]) => {
          if (!ALLOWED_DELTA_ATTRIBUTES.has(name)) return;
          if (name === "link") {
            if (typeof value === "string") attributes.link = value.slice(0, 2048);
          } else if (name === "list") {
            if (value === "ordered" || value === "bullet") attributes.list = value;
          } else if (value === true) {
            attributes[name] = true;
          }
        });
        if (Object.keys(attributes).length) operation.attributes = attributes;
      }
      ops.push(operation);
    }
    return { ops };
  }

  function normalizeOrganizer(raw) {
    if (!raw || typeof raw !== "object") return null;
    return {
      name: boundedString(raw.name, 200),
      email: boundedString(raw.email, 254),
      website: boundedString(raw.website, 2048),
      isPrivate: raw.isPrivate === true,
      showName: raw.showName !== false,
      showEmail: raw.showEmail !== false,
    };
  }

  function normalizeDraft(raw) {
    if (!raw || raw.version !== DRAFT_VERSION || typeof raw.savedAt !== "number") {
      return null;
    }
    if (Date.now() - raw.savedAt > DRAFT_TTL_MS || raw.savedAt > Date.now() + 60000) {
      return null;
    }

    const fields = {};
    if (raw.fields && typeof raw.fields === "object") {
      FIELD_NAMES.forEach((name) => {
        if (typeof raw.fields[name] === "string") {
          fields[name] = boundedString(raw.fields[name]);
        }
      });
    }

    const organizers = Array.isArray(raw.organizers)
      ? raw.organizers.slice(0, MAX_ORGANIZERS).map(normalizeOrganizer).filter(Boolean)
      : [];

    return {
      version: DRAFT_VERSION,
      savedAt: raw.savedAt,
      step: clampStep(raw.step),
      fields,
      organizers,
      descriptionDelta: normalizeDelta(raw.descriptionDelta),
    };
  }

  function readDraft() {
    const serialized = storageGet(DRAFT_KEY);
    if (!serialized) return null;
    if (serialized.length > MAX_DRAFT_BYTES) {
      storageRemove(DRAFT_KEY);
      return null;
    }
    try {
      const draft = normalizeDraft(JSON.parse(serialized));
      if (!draft) storageRemove(DRAFT_KEY);
      return draft;
    } catch (error) {
      storageRemove(DRAFT_KEY);
      return null;
    }
  }

  function readLegacyDraft() {
    const fields = {};
    FIELD_NAMES.forEach((name) => {
      const value = storageGet(`form_${name}`);
      if (value !== null) fields[name] = boundedString(value);
    });

    const organizers = [];
    for (let index = 1; index <= MAX_ORGANIZERS; index += 1) {
      const name = storageGet(`form_organizer_name_${index}`);
      const email = storageGet(`form_organizer_email_${index}`);
      const website = storageGet(`form_organizer_website_${index}`);
      if (name === null && email === null && website === null) continue;
      organizers.push({
        name: boundedString(name, 200),
        email: boundedString(email, 254),
        website: boundedString(website, 2048),
        isPrivate: false,
        showName: true,
        showEmail: true,
      });
    }

    const hasContent = Object.values(fields).some(Boolean) || organizers.length > 0;
    const draft = hasContent
      ? {
          version: DRAFT_VERSION,
          savedAt: Date.now(),
          step: clampStep(storageGet("form_step")),
          fields,
          organizers,
          descriptionDelta: null,
        }
      : null;
    clearLegacyDraft();
    if (draft) storageSet(DRAFT_KEY, JSON.stringify(draft));
    return draft;
  }

  function fieldValue(name) {
    const field = form.elements.namedItem(name);
    if (!field || typeof field.value !== "string") return "";
    const maxLength = field.maxLength > 0 ? field.maxLength : 20000;
    return boundedString(field.value, maxLength);
  }

  function collectOrganizers() {
    return Array.from(form.querySelectorAll(".organizer-card"))
      .slice(0, MAX_ORGANIZERS)
      .map((card) => {
        const index = card.id.replace("organizer-", "");
        return {
          name: fieldValue(`organizer_name_${index}`),
          email: fieldValue(`organizer_email_${index}`),
          website: fieldValue(`organizer_website_${index}`),
          isPrivate: Boolean(document.getElementById(`organizer_is_private_${index}`)?.checked),
          showName: Boolean(document.getElementById(`organizer_show_name_${index}`)?.checked),
          showEmail: Boolean(document.getElementById(`organizer_show_email_${index}`)?.checked),
        };
      });
  }

  function descriptionDelta() {
    try {
      return typeof quill !== "undefined" && quill?.getContents
        ? normalizeDelta(quill.getContents())
        : null;
    } catch (error) {
      return null;
    }
  }

  function draftHasContent(draft) {
    const fieldContent = Object.values(draft.fields).some(Boolean);
    const organizerContent = draft.organizers.some(
      (organizer) =>
        organizer.name ||
        organizer.email ||
        organizer.website ||
        organizer.isPrivate ||
        !organizer.showName ||
        !organizer.showEmail
    );
    const descriptionContent = draft.descriptionDelta?.ops.some(
      (operation) => operation.insert.trim() !== ""
    );
    return fieldContent || organizerContent || descriptionContent || draft.step > 1;
  }

  function persistDraft() {
    if (!ready) return;
    const fields = {};
    FIELD_NAMES.forEach((name) => {
      fields[name] = fieldValue(name);
    });
    const activePage = form.querySelector(".form-page.active");
    const activeStep = activePage?.id?.match(/^page-(\d+)$/)?.[1];
    const draft = {
      version: DRAFT_VERSION,
      savedAt: Date.now(),
      step: clampStep(activeStep),
      fields,
      organizers: collectOrganizers(),
      descriptionDelta: descriptionDelta(),
    };
    if (!draftHasContent(draft)) {
      storageRemove(DRAFT_KEY);
      return;
    }
    const serialized = JSON.stringify(draft);
    if (serialized.length <= MAX_DRAFT_BYTES) storageSet(DRAFT_KEY, serialized);
  }

  function scheduleSave() {
    if (!ready) return;
    window.clearTimeout(saveTimer);
    saveTimer = window.setTimeout(persistDraft, 200);
  }

  function flushDraft() {
    if (!ready) return;
    window.clearTimeout(saveTimer);
    saveTimer = null;
    persistDraft();
  }

  function restoreFields(fields) {
    Object.entries(fields).forEach(([name, value]) => {
      if (name === "city") return;
      const field = form.elements.namedItem(name);
      if (!field || field.type === "file" || field.type === "checkbox") return;
      if (field instanceof HTMLSelectElement) {
        if (Array.from(field.options).some((option) => option.value === value)) {
          field.value = value;
        }
        return;
      }
      field.value = value;
    });

    const city = fields.city;
    if (city) {
      const cityOption = Array.from(document.querySelectorAll("#dropdown-content [role='option']"))
        .find((option) => option.textContent.trim() === city);
      if (cityOption && typeof window.selectCity === "function") window.selectCity(city);
    }

    if (fields.facebook_image_url) {
      const preview = document.getElementById("image-preview");
      if (preview) {
        preview.src = fields.facebook_image_url;
        preview.style.display = "block";
      }
    }

    form.elements.namedItem("type")?.dispatchEvent(new Event("change", { bubbles: true }));
    form.elements.namedItem("route")?.dispatchEvent(new Event("input", { bubbles: true }));
  }

  function restoreOrganizers(organizers) {
    if (!organizers.length) return;
    while (form.querySelectorAll(".organizer-card").length < organizers.length) {
      window.addOrganizer?.(false);
    }

    const cards = Array.from(form.querySelectorAll(".organizer-card"));
    organizers.forEach((organizer, position) => {
      const card = cards[position];
      if (!card) return;
      const index = card.id.replace("organizer-", "");
      const setValue = (prefix, value) => {
        const field = document.getElementById(`${prefix}_${index}`);
        if (field) field.value = value;
      };
      const setChecked = (prefix, checked) => {
        const field = document.getElementById(`${prefix}_${index}`);
        if (field) field.checked = checked;
      };
      setValue("organizer_name", organizer.name);
      setValue("organizer_email", organizer.email);
      setValue("organizer_website", organizer.website);
      setChecked("organizer_is_private", organizer.isPrivate);
      setChecked("organizer_show_name", organizer.showName);
      setChecked("organizer_show_email", organizer.showEmail);
      window.handlePrivateToggle?.(index);
    });
  }

  function restoreDescription(delta) {
    if (!delta) return;
    try {
      if (typeof quill !== "undefined" && quill?.setContents) {
        quill.setContents(delta, "silent");
        const description = document.getElementById("description");
        if (description) description.value = quill.root.innerHTML;
      }
    } catch (error) {
      console.warn("Draft description could not be restored", error);
    }
  }

  function clearDraft() {
    ready = false;
    window.clearTimeout(saveTimer);
    storageRemove(DRAFT_KEY);
    clearLegacyDraft();
    document.getElementById("cacheNotice")?.classList.add("hidden");
  }

  window.saveSubmitDraft = scheduleSave;
  window.clearSubmitDraft = clearDraft;

  function initializeDraft() {
    let draft = readDraft();
    if (!draft) draft = readLegacyDraft();

    if (draft) {
      restoreFields(draft.fields);
      restoreOrganizers(draft.organizers);
      restoreDescription(draft.descriptionDelta);
    }

    ready = true;
    if (draft) {
      window.showPage?.(draft.step);
      document.getElementById("cacheNotice")?.classList.remove("hidden");
    }

    form.addEventListener("input", scheduleSave);
    form.addEventListener("change", scheduleSave);
    window.addEventListener("pagehide", flushDraft);
    try {
      if (typeof quill !== "undefined" && quill?.on) quill.on("text-change", scheduleSave);
    } catch (error) {
      console.warn("Draft editor synchronization is unavailable", error);
    }

    document.getElementById("resetCacheBtn")?.addEventListener("click", () => {
      clearDraft();
      window.location.reload();
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    // Let the form's own DOM-ready initializers establish their default state
    // before a saved draft deliberately overrides it.
    window.setTimeout(initializeDraft, 0);
  });
})();
