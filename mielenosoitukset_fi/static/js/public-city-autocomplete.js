/* Shared local city suggestions; selection keeps the existing hidden field contract. */
window.publicCityAutocomplete = function ({cities, onSelect}) {
  const input = document.getElementById('city_input');
  const results = document.getElementById('city_suggestions');
  const selected = document.getElementById('city');
  if (!input || !results || !selected) return;
  let matches = [];
  let active = -1;

  function close() {
    matches = [];
    active = -1;
    results.replaceChildren();
    results.classList.remove('show');
    input.setAttribute('aria-expanded', 'false');
    input.removeAttribute('aria-activedescendant');
  }
  function activate(index) {
    active = index;
    Array.from(results.children).forEach((option, position) => {
      option.setAttribute('aria-selected', String(position === active));
    });
    const option = results.children[active];
    input.setAttribute('aria-activedescendant', option.id);
    option.scrollIntoView({block: 'nearest'});
  }
  function select(index) {
    const city = matches[index];
    if (!city) return;
    const current = selected.value ? selected.value.split(',') : [];
    if (!current.includes(city)) current.push(city);
    selected.value = current.join(',');
    input.value = '';
    close();
    window.publicListHistory.renderCities();
    if (onSelect) onSelect();
  }
  function render() {
    close();
    const query = input.value.trim().toLocaleLowerCase();
    if (query.length < 2) return;
    const current = new Set(selected.value.split(','));
    matches = cities.filter(city => typeof city === 'string' && !current.has(city) &&
      city.toLocaleLowerCase().includes(query))
      .sort((a, b) => a.localeCompare(b)).slice(0, 20);
    matches.forEach((city, index) => {
      const option = document.createElement('div');
      option.className = 'suggestion-item';
      option.id = `city-suggestion-${index}`;
      option.setAttribute('role', 'option');
      option.setAttribute('aria-selected', 'false');
      option.textContent = city;
      // Keep DOM focus on the combobox while pointer users select an option.
      option.addEventListener('pointerdown', event => event.preventDefault());
      option.addEventListener('click', () => select(index));
      results.append(option);
    });
    if (matches.length) {
      results.classList.add('show');
      input.setAttribute('aria-expanded', 'true');
    }
  }
  input.addEventListener('input', render);
  input.addEventListener('keydown', event => {
    if (event.key === 'Escape') {
      if (matches.length) { event.preventDefault(); event.stopPropagation(); }
      close();
      return;
    }
    if (event.key === 'Tab') { close(); return; }
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      if (!matches.length) render();
      if (!matches.length) return;
      event.preventDefault();
      const step = event.key === 'ArrowDown' ? 1 : -1;
      activate(active < 0 ? (step > 0 ? 0 : matches.length - 1) :
        (active + step + matches.length) % matches.length);
    } else if (matches.length && (event.key === 'Home' || event.key === 'End')) {
      event.preventDefault();
      activate(event.key === 'Home' ? 0 : matches.length - 1);
    } else if (event.key === 'Enter' && active >= 0) {
      event.preventDefault();
      select(active);
    }
  });
  input.addEventListener('blur', close);
};
