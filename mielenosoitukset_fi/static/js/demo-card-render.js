function format_time(time) {
    if (!time) return ""; // handle empty or undefined
    const [hh, mm] = time.split(":"); // split "hh:mm:ss"
    return `${hh}:${mm}`;
}


// 1️⃣ Render all demo cards
function renderDemoCards(demoData) {
  const container = document.getElementById('demos-grid');
  const template = document.getElementById('demo-card-template');

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
  try {
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

    // Render demo cards
    const newCards = renderDemoCards(data.results);

    // Fetch friends attending in one batch
    getFriendsAttending(newCards);

    setup_grid_navigation(newCards);

    // update pagination state
    currentPage = data.page;
    totalPages = data.total_pages;

    // handle "Load more" button
    const loadMoreBtn = document.getElementById("load-more-btn");
    if (currentPage < totalPages) {
      loadMoreBtn.style.display = "block";
      loadMoreBtn.onclick = () => loadDemos(currentPage + 1, true, extraParams);
    } else {
      loadMoreBtn.style.display = "none";
    }

  } catch (err) {
    console.error("Failed to load demos:", err);
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

