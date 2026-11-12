(function () {
    "use strict";

    const BLOCK_ELEMENTS = new Set([
        "ADDRESS", "ARTICLE", "ASIDE", "BLOCKQUOTE", "DIV", "DL", "FIELDSET",
        "FIGCAPTION", "FIGURE", "FOOTER", "FORM", "H1", "H2", "H3", "H4",
        "H5", "H6", "HEADER", "HR", "LI", "MAIN", "NAV", "OL", "P", "PRE",
        "SECTION", "TABLE", "TR", "UL"
    ]);
    const OMITTED_ELEMENTS = new Set(["SCRIPT", "STYLE", "TEMPLATE", "NOSCRIPT"]);

    function toPlainText(value) {
        if (!value) return "";

        const documentFragment = new DOMParser().parseFromString(String(value), "text/html");
        const parts = [];

        function appendText(node) {
            if (node.nodeType === Node.TEXT_NODE) {
                parts.push(node.nodeValue || "");
                return;
            }
            if (node.nodeType !== Node.ELEMENT_NODE || OMITTED_ELEMENTS.has(node.tagName)) return;
            if (node.tagName === "BR" || BLOCK_ELEMENTS.has(node.tagName)) parts.push(" ");
            node.childNodes.forEach(appendText);
            if (BLOCK_ELEMENTS.has(node.tagName)) parts.push(" ");
        }

        documentFragment.body.childNodes.forEach(appendText);
        return parts.join("").replace(/\s+/g, " ").trim();
    }

    function render(container, { title, description, imageUrl }) {
        const content = [];

        if (imageUrl) {
            const image = document.createElement("img");
            image.src = imageUrl;
            image.alt = title || "";
            content.push(image);
        }

        const heading = document.createElement("strong");
        heading.textContent = title || "";
        content.push(heading);

        const plainDescription = toPlainText(description);
        if (plainDescription) {
            const paragraph = document.createElement("p");
            paragraph.textContent = plainDescription;
            content.push(paragraph);
        }

        container.replaceChildren(...content);
    }

    window.CalendarPreview = Object.freeze({ render, toPlainText });
})();
