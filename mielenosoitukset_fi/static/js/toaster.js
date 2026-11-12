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
  toast.setAttribute('role', 'status');
  toast.setAttribute('aria-live', 'polite');

  const icon = document.createElement('div');
  icon.className = 'flash-icon';
  const iconEl = document.createElement('i');
  iconEl.className = `fa-solid ${icons[category] || icons.default}`;
  iconEl.setAttribute('aria-hidden', 'true');
  icon.appendChild(iconEl);

  const content = document.createElement('div');
  content.className = 'flash-content';
  const text = document.createElement('div');
  text.className = 'flash-text';
  // Messages can contain user-controlled data, so never interpret them as HTML.
  text.textContent = String(message ?? '');
  content.appendChild(text);

  const close = document.createElement('button');
  close.className = 'flash-close';
  close.type = 'button';
  close.setAttribute('aria-label', 'Close');
  const closeIcon = document.createElement('i');
  closeIcon.className = 'fa-solid fa-xmark';
  closeIcon.setAttribute('aria-hidden', 'true');
  close.appendChild(closeIcon);

  const progress = document.createElement('div');
  progress.className = 'flash-progress';
  toast.append(icon, content, close, progress);

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