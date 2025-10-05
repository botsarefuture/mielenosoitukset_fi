# 📖 Mielenosoitukset.fi — Demo Card Specification

## 1. Purpose

Demo cards represent **individual demonstrations / protests** in a **grid or list layout**. They provide quick access to key information and link to the full event page.

## 2. Required Elements

Each demo card must include the following fields:

* **Unique Identifier**

  * `data-demo-id` attribute: unique `_id`, `running_number`, or `slug`.
* **Title**

  * `demo.title`
  * Displayed in `.demo-card-title`.
* **Date**

  * `demo.date_display` (localized, e.g. `5.10.2025`).
  * Displayed in `.demo-card-date-time` with calendar icon.
* **Time**

  * `demo.start_time_display` and `demo.end_time_display` (if provided).
  * Displayed with clock icon.
* **City**

  * `demo.city` (string, optional).
  * Displayed with city icon.
* **Address / Location**

  * `demo.address` (string, optional).
  * Displayed with location-dot icon.
* **Tags**

  * `demo.tags[]` (array of hashtags).
  * If missing, fallback to `demo.topic`.
  * Rendered as links (`/tag/{tag}`) inside `.demo-card-tags`.

## 3. Optional Elements

* **Badges**

  * `Tänään` badge if `demo.date_display` = today.
  * `Nousussa` badge if `demo.is_trending` = true.
  * `Suositeltu` badge if `demo.is_recommended` = true.
* **Image**

  * Chosen from: `demo.img`, `demo.cover_image`, `demo.preview_image`.
  * Fallback: `/download_material/{demo._id}`.
  * Rendered inside `.demo-card-image` with `alt` attribute: `{title} – {city} – {date}`.
* **Actions**

  * **Open button** → navigates to `/demonstration/{slug|running_number|_id}`.
  * **Copy link button** → copies full URL to clipboard, provides feedback (`"Kopioitu!"`).

## 4. Accessibility & Interactions

* **Keyboard support**

  * Entire card (`.demo-card`) is focusable (`tabindex="0"`) and clickable with `Enter`.
* **Alt text**

  * All images must have descriptive `alt`.
* **ARIA**

  * Buttons have proper labels (`aria-label` when needed).
* **Visual consistency**

  * Badges use `.demo-card-badge` with role-like styles (e.g. today = accent, trending = highlight).

## 5. Layout Variants

* **Grid view**

  * Cards displayed inside `.container-grid`.
  * Optimized for browsing many events.
* **List view**

  * Alternative rendering as `<tr>` rows in `.demo-table`.
  * Must contain the same information fields but in table form.

## 6. Behavior

* **Navigation**

  * Clicking anywhere on the card or pressing Enter opens the event detail page.
* **Clipboard copy**

  * Clicking “Kopioi linkki” copies the event URL to clipboard.
  * Button text changes temporarily to `"Kopioitu!"`.
* **Lazy loading**

  * Images use `loading="lazy"`.
* **Infinite scroll**

  * Additional demo cards load automatically when scroll sentinel enters viewport.

## 7. Example Markup (grid card)

```html
<div class="grid-item demo-card" 
     data-demo-id="12345"
     tabindex="0"
     onclick="window.location='/demonstration/12345'"
     onkeypress="if(event.key==='Enter'){window.location='/demonstration/12345'}">

  <span class="demo-card-badge demo-card-badge-today">Tänään</span>

  <div class="demo-card-image">
    <img src="/download_material/12345" 
         alt="Elokapina – Helsinki – 5.10.2025" 
         loading="lazy">
  </div>

  <div class="demo-card-title"><span>Elokapina: Ilmastomarssi</span></div>

  <div class="demo-card-date-time">
    <span><i class="fa-regular fa-calendar"></i> 5.10.2025</span>
    <span><i class="fa-regular fa-clock"></i> 13:00 – 16:00</span>
  </div>

  <div class="demo-card-location-row">
    <span><i class="fa-solid fa-city"></i> Helsinki</span>
    <span><i class="fa-solid fa-location-dot"></i> Kansalaistori</span>
  </div>

  <div class="demo-card-tags">
    <a href="/tag/ilmasto" class="demo-card-tag">#ilmasto</a>
    <a href="/tag/ympäristö" class="demo-card-tag">#ympäristö</a>
  </div>

  <div class="demo-card-actions">
    <button class="demo-card-action-btn"><i class="fa-solid fa-arrow-right"></i> Avaa</button>
    <button class="demo-card-action-btn"><i class="fa-solid fa-link"></i> Kopioi linkki</button>
  </div>
</div>
```