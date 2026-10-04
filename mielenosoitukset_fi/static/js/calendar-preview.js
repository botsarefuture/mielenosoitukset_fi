(function () {
    "use strict";

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

        if (description) {
            const paragraph = document.createElement("p");
            paragraph.textContent = description;
            content.push(paragraph);
        }

        container.replaceChildren(...content);
    }

    window.CalendarPreview = Object.freeze({ render });
})();
