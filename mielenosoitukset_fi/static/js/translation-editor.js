(function () {
  "use strict";

  const textarea = document.getElementById("translated_description");
  const preview = document.getElementById("translation-description-preview");
  const guideSteps = Array.from(document.querySelectorAll("[data-guide-step]"));
  const replayButton = document.getElementById("replay-markdown-guide");
  const guideStatus = document.getElementById("markdown-guide-status");
  const guide = document.getElementById("markdown-guide");
  const editor = document.getElementById("translation-editor");
  const accessibilityToggle = document.getElementById("translation-accessibility-mode");
  const accessibilityStatus = document.getElementById("accessibility-mode-status");
  const accessibilityStorageKey = "translation-editor-accessibility-mode";
  let guideTimers = [];

  function appendInlineMarkdown(container, text) {
    const tokenPattern = /(\*\*[^*]+\*\*|\*[^*]+\*|\[[^\]]+\]\([^)]+\))/g;
    let cursor = 0;

    for (const match of text.matchAll(tokenPattern)) {
      container.append(document.createTextNode(text.slice(cursor, match.index)));
      const token = match[0];

      if (token.startsWith("**")) {
        const strong = document.createElement("strong");
        strong.textContent = token.slice(2, -2);
        container.append(strong);
      } else if (token.startsWith("*")) {
        const emphasis = document.createElement("em");
        emphasis.textContent = token.slice(1, -1);
        container.append(emphasis);
      } else {
        const parts = token.match(/^\[([^\]]+)\]\(([^)]+)\)$/);
        const link = document.createElement("a");
        const target = parts[2].trim();
        link.textContent = parts[1];
        if (/^https?:\/\//i.test(target) || /^mailto:/i.test(target)) {
          link.href = target;
        }
        container.append(link);
      }
      cursor = match.index + token.length;
    }

    container.append(document.createTextNode(text.slice(cursor)));
  }

  function renderMarkdown() {
    if (!textarea || !preview) return;

    preview.replaceChildren();
    const lines = textarea.value.split(/\r?\n/);
    let list = null;

    lines.forEach(function (line) {
      const trimmed = line.trim();
      if (!trimmed) {
        list = null;
        return;
      }

      if (trimmed.startsWith("- ")) {
        if (!list) {
          list = document.createElement("ul");
          preview.append(list);
        }
        const item = document.createElement("li");
        appendInlineMarkdown(item, trimmed.slice(2));
        list.append(item);
        return;
      }

      list = null;
      const headingMatch = trimmed.match(/^(#{1,6})\s+(.+)$/);
      const element = document.createElement(headingMatch ? `h${headingMatch[1].length}` : "p");
      appendInlineMarkdown(element, headingMatch ? headingMatch[2] : trimmed);
      preview.append(element);
    });

    if (!preview.hasChildNodes()) {
      const hint = document.createElement("p");
      hint.className = "text-muted";
      hint.textContent = preview.dataset.emptyMessage || "";
      preview.append(hint);
    }
  }

  function applyMarkdown(button) {
    if (!textarea) return;
    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const selected = textarea.value.slice(start, end) || button.dataset.markdownPlaceholder || "";
    const before = button.dataset.markdownBefore || "";
    const after = button.dataset.markdownAfter || "";
    const linePrefix = button.dataset.markdownLine || "";
    const replacement = linePrefix
      ? selected.split(/\r?\n/).map((line) => `${linePrefix}${line}`).join("\n")
      : `${before}${selected}${after}`;

    textarea.setRangeText(replacement, start, end, "select");
    textarea.focus();
    renderMarkdown();
  }

  function replayGuide() {
    guideTimers.forEach(window.clearTimeout);
    guideTimers = [];
    if (guide) guide.classList.add("is-replaying");
    guideSteps.forEach((step) => step.classList.remove("is-active", "is-complete"));

    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    guideSteps.forEach(function (step, index) {
      const showStep = function () {
        guideSteps.forEach((other, otherIndex) => {
          other.classList.toggle("is-active", otherIndex === index);
          other.classList.toggle("is-complete", otherIndex < index);
        });
        if (guideStatus) guideStatus.textContent = `${index + 1} / ${guideSteps.length}`;
        if (index === guideSteps.length - 1 && guide) {
          guideTimers.push(window.setTimeout(() => guide.classList.remove("is-replaying"), 1200));
        }
      };
      if (reducedMotion) {
        step.classList.add("is-complete");
      } else {
        guideTimers.push(window.setTimeout(showStep, index * 900));
      }
    });

    if (reducedMotion && guideStatus) {
      guideStatus.textContent = `${guideSteps.length} / ${guideSteps.length}`;
    }
  }

  function storedAccessibilityMode() {
    try {
      return window.localStorage.getItem(accessibilityStorageKey) !== "false";
    } catch (error) {
      return true;
    }
  }

  function setAccessibilityMode(enabled, announce) {
    if (!editor || !accessibilityToggle) return;
    editor.classList.toggle("accessibility-mode", enabled);
    accessibilityToggle.checked = enabled;
    if (!enabled) {
      guideTimers.forEach(window.clearTimeout);
      guideTimers = [];
      if (guide) guide.classList.remove("is-replaying");
    }
    if (announce && accessibilityStatus) {
      accessibilityStatus.textContent = enabled
        ? accessibilityToggle.dataset.enabledMessage
        : accessibilityToggle.dataset.disabledMessage;
    }
    try {
      window.localStorage.setItem(accessibilityStorageKey, String(enabled));
    } catch (error) {
      // The mode still works when browser storage is unavailable.
    }
  }

  document.querySelectorAll("[data-markdown-before], [data-markdown-line]").forEach(function (button) {
    button.addEventListener("click", function () {
      applyMarkdown(button);
    });
  });
  if (textarea) textarea.addEventListener("input", renderMarkdown);
  if (replayButton) replayButton.addEventListener("click", replayGuide);
  if (accessibilityToggle) {
    accessibilityToggle.addEventListener("change", function () {
      setAccessibilityMode(accessibilityToggle.checked, true);
      if (accessibilityToggle.checked) replayGuide();
    });
  }

  const accessibilityModeEnabled = storedAccessibilityMode();
  setAccessibilityMode(accessibilityModeEnabled, false);
  renderMarkdown();
  if (accessibilityModeEnabled) replayGuide();
})();
