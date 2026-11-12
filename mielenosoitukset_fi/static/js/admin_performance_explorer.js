/* Existing anonymous page-family aggregates; links also work without JavaScript. */
(() => {
  const canvas = document.getElementById('sitePerformanceChart');
  const config = document.getElementById('site-performance-data');
  if (!canvas || !config || typeof Chart === 'undefined') return;
  const { report, page } = JSON.parse(config.textContent);
  let selected = page;
  const rows = new Map(report.rows.map(row => [row.page_type, row]));
  const names = new Map(Array.from(document.querySelectorAll('[data-vitals-name]'), link => [link.dataset.vitalsPage, link.dataset.vitalsName]));
  const title = document.getElementById('vitals-chart-title');
  const empty = document.getElementById('vitals-chart-empty');
  const colors = () => {
    const styles = getComputedStyle(document.documentElement);
    return Object.fromEntries(['text', 'grid', 'primary', 'surface'].map(key => [key, styles.getPropertyValue(`--admin-chart-${key}`).trim()]));
  };
  const initial = colors();
  const chart = new Chart(canvas.getContext('2d'), {
    type: 'line',
    data: { labels: report.labels, datasets: [{ label: report.metric, data: report.series[selected].values, borderColor: initial.primary, backgroundColor: initial.primary, pointRadius: 3, spanGaps: false, tension: 0 }] },
    options: {
      responsive: true, maintainAspectRatio: false,
      scales: { x: { ticks: { color: initial.text, maxTicksLimit: 12 }, grid: { display: false } }, y: { beginAtZero: true, ticks: { color: initial.text }, grid: { color: initial.grid }, title: { display: report.metric !== 'CLS', text: 'ms', color: initial.text } } },
      plugins: { legend: { display: false }, tooltip: { backgroundColor: initial.surface, titleColor: initial.text, bodyColor: initial.text } },
    },
  });
  document.querySelectorAll('[data-vitals-page]').forEach(link => {
    link.addEventListener('click', event => {
      if (event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
      const key = link.dataset.vitalsPage;
      if (!rows.has(key)) return;
      event.preventDefault();
      selected = key;
      title.textContent = `${names.get(key)}: ${report.metric}`;
      chart.data.datasets[0].data = report.series[key].values;
      chart.update('none');
      empty.hidden = report.series[key].values.some(value => value !== null);
      document.querySelectorAll('[data-vitals-page-input]').forEach(input => { input.value = key; });
      document.querySelectorAll('[data-vitals-name]').forEach(rowLink => {
        if (rowLink.dataset.vitalsPage === key) rowLink.setAttribute('aria-current', 'true');
        else rowLink.removeAttribute('aria-current');
      });
      const url = new URL(link.href);
      history.replaceState(null, '', url.pathname + url.search + url.hash);
    });
  });
  document.addEventListener('admin:themechange', () => {
    const next = colors();
    chart.data.datasets[0].borderColor = next.primary;
    chart.data.datasets[0].backgroundColor = next.primary;
    chart.options.scales.x.ticks.color = next.text;
    chart.options.scales.y.ticks.color = next.text;
    chart.options.scales.y.title.color = next.text;
    chart.options.scales.y.grid.color = next.grid;
    chart.options.plugins.tooltip.backgroundColor = next.surface;
    chart.options.plugins.tooltip.titleColor = next.text;
    chart.options.plugins.tooltip.bodyColor = next.text;
    chart.update('none');
  });
})();
