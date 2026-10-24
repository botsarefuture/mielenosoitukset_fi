/* Display-only shared deadline clock: no polling, writes or escalation. */
(() => {
  document.querySelectorAll('[data-admin-deadlines]').forEach(root => {
    const serverTime = Date.parse(root.dataset.serverNow);
    if (!Number.isFinite(serverTime)) return;
    const reference = performance.now();
    const update = () => {
      const now = serverTime + performance.now() - reference;
      root.querySelectorAll('[data-deadline]').forEach(label => {
        const deadline = Date.parse(label.dataset.deadline);
        if (!Number.isFinite(deadline)) return;
        const minutes = Math.max(0, Math.ceil((deadline - now) / 60000));
        label.textContent = minutes === 0 ? root.dataset.expiredLabel :
          `${root.dataset.remainingLabel}: ${Math.floor(minutes / 60)} h ${minutes % 60} min`;
      });
    };
    update();
    window.setInterval(update, 60000);
    document.addEventListener('visibilitychange', () => { if (!document.hidden) update(); });
  });
})();
