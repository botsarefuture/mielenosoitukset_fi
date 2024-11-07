// Data initialization
const data = {
    demo: {{ demo | tojson }}
};

// Map Initialization if location data is available
if (data.demo.latitude && data.demo.longitude) {
    const map = L.map("map").setView([data.demo.latitude, data.demo.longitude], 13);

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map);

    L.marker([data.demo.latitude, data.demo.longitude])
        .addTo(map)
        .bindPopup(data.demo.address)
        .openPopup();
} else {
    const mapElement = document.getElementById("map");
    if (mapElement) {
        mapElement.remove();
    }
}

// Converts Finnish date format (dd.mm.yyyy) to ISO (yyyy-mm-dd)
function formatFinnishDate(dateString) {
    const [day, month, year] = dateString.split(".").map(Number);
    return `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
}

// Updates the countdown to the event
function updateCountdown() {
    const demoDate = data.demo.date;
    const demoTime = data.demo.start_time;
    const eventDateStr = `${formatFinnishDate(demoDate)}T${demoTime}`;
    const eventDate = new Date(eventDateStr);
    const now = new Date();
    const timeRemaining = eventDate - now;

    const timerElement = document.getElementById("timer");

    if (timeRemaining <= 0) {
        timerElement.innerText = "{{ _('Mielenosoitus on käynnissä!') }}";
        return;
    }

    const days = Math.floor(timeRemaining / (1000 * 60 * 60 * 24));
    const hours = Math.floor((timeRemaining % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
    const minutes = Math.floor((timeRemaining % (1000 * 60 * 60)) / (1000 * 60));
    const seconds = Math.floor((timeRemaining % (1000 * 60)) / 1000);

    timerElement.innerText = `${days} {{ _('päivää') }} ${hours} {{ _('tuntia') }} ${minutes} {{ _('minuuttia') }} ${seconds} {{ _('sekuntia') }}`;
}

setInterval(updateCountdown, 1000);

// Populates the organizers' information in the HTML
function populateOrganizers(organizers) {
    const organizersListDiv = document.getElementById("organizers-list");
    const noOrganizersText = document.getElementById("no-organizers");

    if (organizers && organizers.length > 0) {
        organizers.forEach((org) => {
            const organizerDiv = document.createElement("div");
            organizerDiv.classList.add("organizer-info");

            const nameParagraph = document.createElement("p");
            nameParagraph.innerHTML = `<strong>{{ _('Nimi:') }}</strong><br />${org.name}`;
            organizerDiv.appendChild(nameParagraph);

            if (org.organization_id) {
                const profileLink = document.createElement("a");
                profileLink.href = org.url;
                profileLink.classList.add("org-profile-link");
                profileLink.innerText = "{{ _('Mielenosoitukset.fi -profiili') }}";
                organizerDiv.appendChild(profileLink);
            }

            if (org.website) {
                const websiteLink = document.createElement("a");
                websiteLink.href = org.website;
                websiteLink.target = "_blank";
                websiteLink.classList.add("org-website");
                websiteLink.innerText = org.website;
                const websiteParagraph = document.createElement("p");
                websiteParagraph.innerHTML = `<strong>{{ _('Verkkosivut:') }}</strong><br />`;
                websiteParagraph.appendChild(websiteLink);
                organizerDiv.appendChild(websiteParagraph);
            }

            if (org.email) {
                const emailLink = document.createElement("a");
                emailLink.href = `mailto:${org.email}`;
                emailLink.classList.add("org-email");
                emailLink.innerText = org.email;
                const emailParagraph = document.createElement("p");
                emailParagraph.innerHTML = `<strong>{{ _('Sähköpostiosoite:') }}</strong><br />`;
                emailParagraph.appendChild(emailLink);
                organizerDiv.appendChild(emailParagraph);
            }

            organizersListDiv.appendChild(organizerDiv);
        });
    } else {
        noOrganizersText.style.display = "block";
    }
}

// Populates the demo details in the HTML
function populateDemoDetails(demo) {
    const demoDetailsDiv = document.getElementById("demo-details");
    let detailsHTML = `
        <p><strong>{{ _('Päivämäärä:') }}</strong><br />${demo.date}</p>
        <p><strong>{{ _('Alkaa klo:') }}</strong><br />${demo.start_time}</p>
        <p><strong>{{ _('Päättyy klo:') }}</strong><br />${demo.end_time}</p>
        <p><strong>{{ _('Alkupaikka:') }}</strong><br />${demo.address}, ${demo.city}</p>
    `;

    if (demo.route && demo.route !== "None") {
        detailsHTML += `
            <div class="route">
                <p><strong>{{ _('Marssin reitti:' }}</strong></p>
                <p>${demo.route}</p>
            </div>`;
    }

    if (demo.facebook) {
        detailsHTML += `<a href="${demo.facebook}" target="_blank" class="facebook-button">{{ _('Facebook-tapahtuma') }}</a>`;
    }

    demoDetailsDiv.innerHTML = detailsHTML;
}

// Toggle display for toolbox buttons
function toggleToolbox() {
    const toolboxButtons = document.getElementById("toolbox-buttons");
    toolboxButtons.style.display = toolboxButtons.style.display === 'none' ? 'flex' : 'none';
}

// Initial population calls
populateOrganizers(data.demo.organizers);
populateDemoDetails(data.demo);
