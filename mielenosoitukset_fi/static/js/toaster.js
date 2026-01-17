function showToast(message, category = 'info') {
  const icons = {
    success: 'fa-circle-check',
    error: 'fa-circle-exclamation',
    danger: 'fa-circle-exclamation',
    warning: 'fa-triangle-exclamation',
    info: 'fa-circle-info',
    default: 'fa-bell',
  };

  const container = document.querySelector('.flash-messages') || (() => {
    const el = document.createElement('div');
    el.id = 'flash-messages';
    el.className = 'flash-messages';

    // we need this to be added after the header so that it appears below it
    // but before other content
    const firstChild = document.body.firstChild;
    if (firstChild) {
      document.body.insertBefore(el, firstChild.nextSibling);
    } else {
      document.body.appendChild(el);
    }
    
    return el;
  })();

  const toast = document.createElement('div');
  toast.className = `flash-message flash-${category}`;
  toast.innerHTML = `
    <div class="flash-icon"><i class="fa-solid ${icons[category] || icons.default}"></i></div>
    <div class="flash-content"><div class="flash-text">${message}</div></div>
    <button class="flash-close" aria-label="Close"><i class="fa-solid fa-xmark"></i></button>
    <div class="flash-progress"></div>
  `;

  const progress = toast.querySelector('.flash-progress');
  const remove = () => {
    if (toast.classList.contains('removing')) return;
    toast.classList.add('removing');
    setTimeout(() => toast.remove(), 400);
  };

  toast.querySelector('.flash-close').addEventListener('click', (e) => {
    e.preventDefault();
    remove();
  });

  let hovered = false;
  toast.addEventListener('mouseenter', () => {
    hovered = true;
    if (progress) progress.style.animationPlayState = 'paused';
  });
  toast.addEventListener('mouseleave', () => {
    hovered = false;
    if (progress) progress.style.animationPlayState = 'running';
    if (progress && progress.dataset.done) remove();
  });

  if (progress) {
    progress.style.animationPlayState = 'running';
    progress.addEventListener('animationend', () => {
      progress.dataset.done = '1';
      if (!hovered) remove();
    }, { once: true });
  } else {
    setTimeout(remove, 5000);
  }

  container.appendChild(toast);
}

// Example usage after a fetch:
/*
fetch('/api/something').then(r => r.json()).then(data => {
  if (data.success) showToast('Tallennettu!', 'success');
  else showToast(data.error || 'Virhe tallennuksessa', 'error');
}).catch(() => showToast('Verkkovirhe, yritä uudelleen', 'warning'));
*/