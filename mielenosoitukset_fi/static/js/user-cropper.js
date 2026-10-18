/* One progressively enhanced image field; upload names and Cropper 2.x hooks stay stable. */
(() => {
  'use strict';
  function initialize() {
    const fileInput = document.getElementById('image');
    const modal = document.getElementById('cropperModal');
    const container = document.getElementById('cropperContainer');
    const preview = document.getElementById('image-preview');
    if (!fileInput || !modal || !container || !preview || !modal.showModal) return;
    // Leave native uploads untouched unless cropped files can be committed.
    try {
      if (typeof DataTransfer !== 'function' || typeof File !== 'function') return;
      const probe = document.createElement('input');
      probe.type = 'file';
      const transfer = new DataTransfer();
      transfer.items.add(new File([''], 'cropper-capability-test'));
      probe.files = transfer.files;
      if (probe.files.length !== 1 || probe.files[0].name !== 'cropper-capability-test') return;
    } catch (_unsupported) {
      return;
    }
    const apply = document.getElementById('applyCrop');
    const cancel = document.getElementById('cancelCrop');
    const status = document.getElementById('cropperStatus');
    const error = document.getElementById('cropperError');
    const template = document.getElementById('cropperTemplate');
    let cropper = null;
    let originalFile = null;
    let generation = 0;
    let imageURL = null;
    let engine = null;
    let backdropStart = false;
    let committedImage = null;

    function restoreCommittedImage() {
      if (committedImage) {
        const transfer = new DataTransfer();
        transfer.items.add(committedImage.file);
        fileInput.files = transfer.files;
        preview.src = committedImage.preview;
        preview.hidden = false;
        preview.style.display = 'block';
      } else {
        fileInput.value = '';
        preview.removeAttribute('src');
        preview.hidden = true;
        preview.style.display = 'none';
      }
    }

    function cleanup() {
      generation += 1;
      if (cropper) cropper.destroy();
      cropper = null;
      container.replaceChildren();
      if (imageURL) URL.revokeObjectURL(imageURL);
      imageURL = null;
      modal.removeAttribute('aria-busy');
      apply.disabled = true;
    }
    function close(cancelled) {
      cleanup();
      if (cancelled) restoreCommittedImage();
      if (modal.open) modal.close();
      fileInput.focus();
    }
    function showError() {
      restoreCommittedImage();
      status.textContent = '';
      error.textContent = modal.dataset.error;
      error.hidden = false;
      modal.removeAttribute('aria-busy');
    }
    function isCurrent(ticket) {
      return ticket === generation && modal.open;
    }

    fileInput.addEventListener('change', async () => {
      const file = fileInput.files?.[0];
      if (!file) return;
      cleanup();
      originalFile = file;
      const ticket = generation;
      error.hidden = true;
      error.textContent = '';
      status.textContent = modal.dataset.loading;
      modal.setAttribute('aria-busy', 'true');
      if (!modal.open) modal.showModal();
      cancel.focus();
      imageURL = URL.createObjectURL(file);
      const image = document.createElement('img');
      image.id = 'cropperImage';
      image.alt = '';
      image.src = imageURL;
      container.append(image);
      try {
        // Import only when an image is selected. Failed imports may be retried.
        engine ||= import(modal.dataset.moduleUrl).catch(failure => {
          engine = null;
          throw failure;
        });
        const [{default: Cropper}] = await Promise.all([engine, image.decode()]);
        if (!isCurrent(ticket)) return;
        cropper = new Cropper(image, {template: template.innerHTML});
        await cropper.getCropperImage().$ready();
        if (!isCurrent(ticket)) return;
        status.textContent = '';
        modal.removeAttribute('aria-busy');
        apply.disabled = false;
      } catch (_failure) {
        if (isCurrent(ticket)) showError();
      }
    });

    apply.addEventListener('click', async () => {
      if (!cropper || apply.disabled) return;
      const ticket = generation;
      const file = originalFile;
      const selection = cropper.getCropperSelection();
      if (!selection) return;
      apply.disabled = true;
      error.hidden = true;
      modal.setAttribute('aria-busy', 'true');
      try {
        const image = cropper.getCropperImage();
        const source = await image.$ready();
        if (!isCurrent(ticket)) return;
        const [a, b] = image.$getTransform();
        const scale = Math.hypot(a, b);
        const aspect = selection.width / selection.height;
        if (![scale, aspect].every(value => Number.isFinite(value) && value > 0)) {
          throw new Error('Invalid crop transform');
        }
        // Export source pixels, not responsive dialog pixels. Zooming out must
        // not allocate a canvas larger than the original image's dimensions.
        const width = Math.round(Math.min(
          selection.width / scale, source.naturalWidth, source.naturalHeight * aspect
        ));
        const height = Math.round(width / aspect);
        if (width < 1 || height < 1) throw new Error('Empty crop');
        const canvas = await selection.$toCanvas({width, height});
        if (!isCurrent(ticket)) return;
        const blob = await new Promise((resolve, reject) => canvas.toBlob(
          result => result ? resolve(result) : reject(new Error('Empty crop')),
          file.type || 'image/jpeg'
        ));
        if (!isCurrent(ticket)) return;
        const dataURL = canvas.toDataURL(blob.type);
        const cropped = new File([blob], file.name, {type: blob.type});
        const transfer = new DataTransfer();
        transfer.items.add(cropped);
        // Commit the preview and upload only after every async stage succeeded.
        fileInput.files = transfer.files;
        preview.src = dataURL;
        preview.hidden = false;
        preview.style.display = 'block';
        committedImage = {file: cropped, preview: dataURL};
        close(false);
      } catch (_failure) {
        if (isCurrent(ticket)) {
          showError();
          apply.disabled = false;
        }
      }
    });
    cancel.addEventListener('click', () => close(true));
    modal.addEventListener('cancel', event => {
      event.preventDefault();
      close(true);
    });
    modal.addEventListener('keydown', event => {
      if (event.key !== 'Tab') return;
      const stops = Array.from(modal.querySelectorAll('button:not([disabled]), [tabindex="0"]'))
        .filter(element => element.getClientRects().length);
      const first = stops[0], last = stops[stops.length - 1];
      if (!first) return;
      if ((event.shiftKey && document.activeElement === first) ||
          (!event.shiftKey && document.activeElement === last)) {
        event.preventDefault();
        (event.shiftKey ? last : first).focus();
      }
    });
    const outside = event => {
      const rect = modal.getBoundingClientRect();
      return event.clientX < rect.left || event.clientX > rect.right ||
        event.clientY < rect.top || event.clientY > rect.bottom;
    };
    modal.addEventListener('pointerdown', event => {
      backdropStart = event.target === modal && outside(event);
    });
    modal.addEventListener('click', event => {
      if (backdropStart && event.target === modal && outside(event)) close(true);
      backdropStart = false;
    });
    window.cropperModal = {
      getCropper: () => cropper,
      getOriginalFile: () => originalFile,
    };
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initialize, {once: true});
  else initialize();
})();
