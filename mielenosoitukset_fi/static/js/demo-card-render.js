function format_time(time) {
  if (!time) return ""; // handle empty or undefined
  const [hh, mm] = time.split(":"); // split "hh:mm:ss"
  return `${hh}:${mm}`;
}


// 1️⃣ Render all demo cards
function renderDemoCards(demoData) {
  const container = document.getElementById('demos-grid');
  const template = document.getElementById('demo-card-template');

  const todayDate = new Date();
  todayDate.setHours(0,0,0,0); // strip time

  demoData.forEach(demo => {
    const clone = template.content.cloneNode(true);
    const card = clone.querySelector('.demo-card');

    card.dataset.demoId = demo._id;
    card.querySelector('.demo-card-title span').textContent = demo.title;
    card.querySelector('.demo-card-image img').src = demo.preview_image;
    card.querySelector('.demo-card-date').append(demo.formatted_date);

    // Compute start & end display
    const demoStartTime = format_time(demo.start_time);
    const demoEndTime = demo.end_time ? format_time(demo.end_time) : null;

    // Combine for display
    const timeText = demoEndTime ? `${demoStartTime} – ${demoEndTime}` : demoStartTime;

    // Set in card
    card.querySelector('.demo-card-time').textContent = timeText;

    card.querySelector('.demo-card-city').append(demo.city);
    card.querySelector('.demo-card-address').append(demo.address);
  // Add badges container
    const badgeContainer = card.querySelector('.demo-card-badges');
    badgeContainer.innerHTML = ''; // clear existing

    // 🌟 "Tänään" badge if demo is today
    const demoDateObj = new Date(demo.date);
    demoDateObj.setHours(0,0,0,0); // strip time
    if (demoDateObj.getTime() === todayDate.getTime()) {
      const todayBadge = document.createElement('span');
      todayBadge.className = 'demo-badge today-badge';
      todayBadge.textContent = 'Tänään';
      badgeContainer.appendChild(todayBadge);
    }

    // 🌈 Tags-based badges (e.g., Pride)
    if (demo.tags && demo.tags.length > 0) {
      demo.tags.forEach(tag => {
        if (tag.toLowerCase() === 'pride') {
          const prideBadge = document.createElement('span');
          prideBadge.className = 'demo-badge pride-badge';
          prideBadge.textContent = 'Pride';
          badgeContainer.appendChild(prideBadge);
        }
        // Add more tag-to-badge rules here
        // e.g., if (tag.toLowerCase() === 'climate') ...
      });
    }
    // Optional: tags
    const tagsContainer = card.querySelector('.demo-card-tags');
    if (demo.tags && demo.tags.length > 0) {
      demo.tags.forEach(tag => {
        const a = document.createElement('a');
        a.href = `/tag/${tag}`;
        a.textContent = `#${tag}`;
        a.className = 'demo-card-tag';
        tagsContainer.appendChild(a);
      });
    }

    container.appendChild(clone);

  });

  // Return all card elements
  return Array.from(container.querySelectorAll('.demo-card'));
}

// Attach click events (both existing and new cards)
function setup_grid_navigation(cards) {
  cards.forEach(item => {
    const demoId = item.dataset.demoId;

    // Main card click
    item.addEventListener('click', e => {
      if (e.target.closest('a') || e.target.closest('.demo-card-invite-btn') || e.target.closest('.demo-card-no-friends')) return;
      if (demoId) window.location.href = `/demonstration/${demoId}`;
    });

    // Invite button
    const inviteBtn = item.querySelector('.demo-card-invite-btn');
    if (inviteBtn) {
      inviteBtn.addEventListener('click', e => {
        e.stopPropagation();
        if (demoId) window.location.href = `/demonstration/${demoId}?action=inviteFriends`;
      });
    }

    // "No friends" section click
    const noFriendsDiv = item.querySelector('.demo-card-no-friends');
    if (noFriendsDiv) {
      noFriendsDiv.addEventListener('click', e => {
        e.stopPropagation();
        if (demoId) window.location.href = `/demonstration/${demoId}?action=inviteFriends`;
      });
    }
  });
}


// pagination state
let currentPage = 1;
let totalPages = 1;
const perPage = 12; // default per-page

async function loadDemos(page = 1, append = false, extraParams = {}) {
  const loadMoreBtn = document.getElementById("load-more-btn");
  const demosGrid = document.getElementById("demos-grid");
  try {
     // Show loading state
    if (loadMoreBtn) {
      loadMoreBtn.disabled = true;
      loadMoreBtn.textContent = 'Ladataan…'; // temporary text
      loadMoreBtn.classList.add('loading');   // optional CSS spinner class
    }
    // Build query params
    const params = new URLSearchParams({
      page,
      per_page: perPage,
      ...extraParams // merge in any page-specific params
    });

    const res = await fetch(`/api/demonstrations?${params.toString()}`);
    const data = await res.json();

    const grid = document.getElementById("demos-grid");
    if (!append) grid.innerHTML = ""; // clear on first load

    if (data.results.length === 0) {
      const noResultsDiv = document.getElementById("no-results");
      noResultsDiv.style.display = ""; // ✅ just set the property
      demosGrid.style.display = "none";

    } else {
      // hide if there are results
      const noResultsDiv = document.getElementById("no-results");
      noResultsDiv.style.display = "none";
      demosGrid.style.display = "";
    }


    // Render demo cards
    const newCards = renderDemoCards(data.results);

    // Fetch friends attending in one batch
    getFriendsAttending(newCards);

    setup_grid_navigation(newCards);

    // update pagination state
    currentPage = data.page;
    totalPages = data.total_pages;

    // handle "Load more" button
    if (currentPage < totalPages) {
      if (loadMoreBtn) {
        loadMoreBtn.style.display = "block";
        loadMoreBtn.disabled = false;
        loadMoreBtn.textContent = 'Lataa lisää';
        loadMoreBtn.onclick = () => loadDemos(currentPage + 1, true, extraParams);
      }
    } else {
      if (loadMoreBtn) loadMoreBtn.style.display = "none";
    }

  } catch (err) {
    console.error("Failed to load demos:", err);
    if (loadMoreBtn) {
      loadMoreBtn.disabled = false;
      loadMoreBtn.textContent = 'Lataa lisää';
    }
  }

  finally {
    loadMoreBtn.classList.remove("loading");
  }
}


// load first page on startup
//document.addEventListener("DOMContentLoaded", () => {
//  loadDemos();

//  document.getElementById("load-more-btn").addEventListener("click", () => {
//    if (currentPage < totalPages) {
//      loadDemos(currentPage + 1, true);
//    }
//  });
//});


// 2️⃣ Update attending section per card
function updateDemoCardAttending(cardElement, friends) {
  const loadingDiv = cardElement.querySelector('.attending-loading');
  const friendsDiv = cardElement.querySelector('.demo-card-friends');
  const noFriendsDiv = cardElement.querySelector('.demo-card-no-friends');

  loadingDiv.style.display = 'none';

  if (friends && friends.length > 0) {
    friendsDiv.style.display = 'flex';
    friendsDiv.innerHTML = friends.slice(0, 3).map(f => `
      <img class="friend-avatar animate-fade-in-up" src="${f.avatar}" alt="${f.name}" title="${f.name}">
    `).join('') + `<span class="friends-text">${friends[0].name} osallistuu</span>`;
    noFriendsDiv.style.display = 'none';
  } else {
    friendsDiv.style.display = 'none';
    noFriendsDiv.style.display = 'flex';
  }
}

// Example usage:
// Suppose `card` is your rendered demo-card element
// fetch('/api/demo-attending?id=123')
//   .then(res => res.json())
//   .then(data => updateDemoCardAttending(card, data.friends));
// 3️⃣ Fetch friends attending in one batch
function getFriendsAttending(demoCards) {
  const demoIds = demoCards.map(card => card.dataset.demoId);
  if (demoIds.length === 0) return; // Don't query API if empty :3

  // 🛑 If user isn’t logged in, show login prompt in each card
  if (document.logged_in !== true) {
    demoCards.forEach(card => {
      const loadingDiv = card.querySelector('.attending-loading');
      const friendsDiv = card.querySelector('.demo-card-friends');
      const noFriendsDiv = card.querySelector('.demo-card-no-friends');

      if (loadingDiv) loadingDiv.style.display = 'none';
      if (friendsDiv) friendsDiv.style.display = 'none';
      if (noFriendsDiv) {
        noFriendsDiv.style.display = 'flex';
        noFriendsDiv.innerHTML = `<span class="login-prompt">Kirjaudu sisään käyttääksesi sosiaalisia toimintoja</span>`;
      }
    });
    return;
  }

  fetch('/api/friends-attending', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ demo_ids: demoIds }),

  })
    .then(res => res.json())
    .then(data => {
      demoCards.forEach(card => {
        const id = card.dataset.demoId;
        const friends = data[id] || [];
        updateDemoCardAttending(card, friends);
      });
    })
    .catch(err => console.error('Failed to fetch friends attending:', err));
}

