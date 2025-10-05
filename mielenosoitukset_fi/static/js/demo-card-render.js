function format_time(time) {
    if (!time) return ""; // handle empty or undefined
    const [hh, mm] = time.split(":"); // split "hh:mm:ss"
    return `${hh}:${mm}`;
}


function renderDemoCard(demo) {
  const tpl = document.getElementById("demo-card-template");
  const clone = tpl.content.cloneNode(true);
  const card = clone.querySelector(".demo-card");

  // id + navigation
  card.dataset.demoId = demo._id;
  card.onclick = () => window.location.href = `/demonstration/${demo.slug || demo.running_number || demo._id}`;
  card.onkeypress = (e) => { if (e.key === "Enter") card.onclick(); };

  // badges
  const badges = clone.querySelector(".demo-card-badges");
  if (demo.is_today) badges.innerHTML += `<span class="demo-card-badge demo-card-badge-today">Tänään</span>`;
  if (demo.is_trending) badges.innerHTML += `<span class="demo-card-badge demo-card-badge-trending">Nousussa</span>`;
  if (demo.is_recommended) badges.innerHTML += `<span class="demo-card-badge demo-card-badge-recommended">Suositeltu</span>`;

  // image
  const img = clone.querySelector(".demo-card-image img");
  img.src = demo.img || demo.cover_image || demo.preview_image || `/download_material/${demo._id}`;
  img.alt = `${demo.title} – ${demo.city || ""} – ${demo.date_display}`;

  // title
  clone.querySelector(".demo-card-title span").textContent = demo.title;

  // date + time

  _formatted_start_time = format_time(demo.start_time);
  _formatted_end_time = format_time(demo.end_time)
  clone.querySelector(".demo-card-date").innerHTML = `<i class="fa-regular fa-calendar"></i> ${demo.formatted_date}`;
  clone.querySelector(".demo-card-time").innerHTML = _formatted_start_time 
      ? `<i class="fa-regular fa-clock"></i> ${_formatted_start_time}${_formatted_end_time ? " – " + _formatted_end_time : ""}` 
      : "";

  // city + address
  if (demo.city) clone.querySelector(".demo-card-city").innerHTML = `<i class="fa-solid fa-city"></i> ${demo.city}`;
  if (demo.address) clone.querySelector(".demo-card-address").innerHTML = `<i class="fa-solid fa-location-dot"></i> ${demo.address}`;

  // tags
  const tagsEl = clone.querySelector(".demo-card-tags");
  (demo.tags?.length ? demo.tags : [demo.topic]).forEach(tag => {
    const a = document.createElement("a");
    a.href = `/tag/${tag}`;
    a.className = "demo-card-tag";
    a.textContent = `#${tag}`;
    tagsEl.appendChild(a);
  });

  // actions
  clone.querySelector(".open-btn").onclick = () => window.location.href = `/demonstration/${demo.slug || demo.running_number || demo._id}`;
  clone.querySelector(".copy-btn").onclick = async (e) => {
    e.stopPropagation();
    await navigator.clipboard.writeText(`${window.location.origin}/demonstration/${demo.slug || demo.running_number || demo._id}`);
    e.target.textContent = "Kopioitu!";
    setTimeout(() => e.target.innerHTML = `<i class="fa-solid fa-link"></i> Kopioi linkki`, 1500);
  };

  return clone;
}

// pagination state
let currentPage = 1;
let totalPages = 1;
const perPage = 12; // can match your backend default

async function loadDemos(page = 1, append = false) {
  const res = await fetch(`/api/demonstrations?page=${page}&per_page=${perPage}`);
  const data = await res.json();

  const grid = document.getElementById("demo-grid");
  if (!append) grid.innerHTML = ""; // clear on first load

  data.results.forEach(demo => grid.appendChild(renderDemoCard(demo)));

  // update state
  currentPage = data.page;
  totalPages = data.total_pages;

  // handle "Load more" button
  const loadMoreBtn = document.getElementById("load-more-btn");
  if (currentPage < totalPages) {
    loadMoreBtn.style.display = "block";
  } else {
    loadMoreBtn.style.display = "none";
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
