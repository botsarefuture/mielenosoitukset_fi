"""Actual pinned engine, native modal lifecycle and transactional file updates."""
import hashlib
import base64
from pathlib import Path
import pytest
from flask import render_template_string


def test_cropper_uses_shared_dialog_and_pinned_existing_engine():
    source = Path('mielenosoitukset_fi/templates/cropper-modal.html').read_text()
    assert '<dialog id="cropperModal"' in source
    assert 'aria-labelledby="cropperTitle"' in source
    assert 'aria-describedby="cropperHelp"' in source
    assert 'keyboard active tabindex="0"' in source
    assert '<style' not in source and 'style=' not in source
    controller = Path('mielenosoitukset_fi/static/js/user-cropper.js').read_text()
    assert 'container.innerHTML' not in controller
    assert 'getOriginalFile' in controller and 'getCropper' in controller
    vendor = Path('mielenosoitukset_fi/static/vendor/cropperjs/2.1.0/cropper.esm.min.js')
    assert hashlib.sha256(vendor.read_bytes()).hexdigest() == '1873abfe6048bea0867c18116fd7705789ff6abb4dd6281ef5767307dcfd4d64'


def _open_harness(app, live_server, page, theme='light', width=1440, locale='fi', source_width=800):
    app.config.update(BABEL_SUPPORTED_LOCALES=['fi', 'en', 'sv'], BABEL_PUBLIC_LOCALES=['fi', 'en', 'sv'])
    def view():
        return render_template_string("""<!doctype html><html><head>
          <link rel="stylesheet" href="{{ url_for('static', filename='css/product-tokens.css') }}">
          <link rel="stylesheet" href="{{ url_for('static', filename='css/user-workspace.css') }}">
          </head><body><button id="outside" type="button">Outside</button>
          <label for="image">Image</label><input id="image" name="image" type="file" accept="image/*">
          <img id="image-preview" hidden alt="Preview">
          {% include 'cropper-modal.html' %}</body></html>""")
    app.add_url_rule('/cropper-test/', view_func=view)
    page.set_viewport_size({'width': width, 'height': 900})
    page.goto(f'{live_server}/set_language/{locale}')
    page.goto(f'{live_server}/cropper-test/')
    page.evaluate('(scheme) => document.documentElement.style.colorScheme = scheme', theme)
    return base64.b64decode(page.evaluate("""(sourceWidth) => {
      const canvas = document.createElement('canvas');
      canvas.width = sourceWidth; canvas.height = sourceWidth * 9 / 16;
      const context = canvas.getContext('2d');
      context.fillStyle = '#2463b7'; context.fillRect(0, 0, canvas.width, canvas.height);
      return canvas.toDataURL('image/png').split(',')[1];
    }""", source_width))


def _select(page, image, name='test-image.png'):
    page.locator('#image').set_input_files({'name': name, 'mimeType': 'image/png', 'buffer': image})
    page.wait_for_function("window.cropperModal?.getCropper() && !document.getElementById('applyCrop').disabled")


def _track_crop_apply_settlement(page):
    page.add_init_script("""(() => {
      const original = EventTarget.prototype.addEventListener;
      EventTarget.prototype.addEventListener = function(type, listener, options) {
        if (this.id === 'applyCrop' && type === 'click' && typeof listener === 'function') {
          const handler = listener;
          listener = async function(event) {
            window.cropApplySettled = false;
            try { return await handler.call(this, event); }
            finally { window.cropApplySettled = true; }
          };
        }
        return original.call(this, type, listener, options);
      };
    })();""")


@pytest.mark.e2e
@pytest.mark.integration
@pytest.mark.parametrize('capability', ['no-transfer', 'no-file', 'setter-throws', 'setter-ignores'])
def test_cropper_preserves_native_upload_without_file_transfer_support(
    app, live_server, browser_page, capability
):
    patches = {
        'no-transfer': 'window.DataTransfer = undefined;',
        'no-file': 'window.File = undefined;',
        'setter-throws': "Object.defineProperty(HTMLInputElement.prototype, 'files', {get: descriptor.get, set() { throw new Error('Unsupported'); }});",
        'setter-ignores': "Object.defineProperty(HTMLInputElement.prototype, 'files', {get: descriptor.get, set() {}});",
    }
    browser_page.add_init_script("const descriptor = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'files');" + patches[capability])
    errors = []
    browser_page.on('pageerror', lambda error: errors.append(error.stack))
    image = _open_harness(app, live_server, browser_page)
    assert browser_page.evaluate('typeof window.cropperModal?.getCropper') == 'undefined'
    browser_page.locator('#image').set_input_files({
        'name': 'native-upload.png', 'mimeType': 'image/png', 'buffer': image,
    })
    result = browser_page.evaluate("""async () => {
      const input = document.getElementById('image');
      const form = document.createElement('form');
      input.before(form); form.append(input);
      const file = new FormData(form).get('image');
      const hash = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', await file.arrayBuffer())))
        .map(byte => byte.toString(16).padStart(2, '0')).join('');
      return {name: file.name, size: file.size, type: file.type, hash};
    }""")
    assert result == {'name': 'native-upload.png', 'size': len(image),
                      'type': 'image/png', 'hash': hashlib.sha256(image).hexdigest()}
    assert not browser_page.locator('#cropperModal').evaluate('element => element.open')
    assert browser_page.locator('#image-preview').is_hidden()
    assert not errors


@pytest.mark.e2e
@pytest.mark.integration
@pytest.mark.parametrize('theme,width', [('light', 1440), ('dark', 1440), ('light', 390), ('dark', 390)])
def test_actual_cropper_has_modal_focus_keyboard_geometry_and_real_upload(app, live_server, browser_page, theme, width):
    image = _open_harness(app, live_server, browser_page, theme, width)
    errors = []
    browser_page.on('pageerror', lambda error: errors.append(error.stack))
    _select(browser_page, image)
    modal = browser_page.locator('#cropperModal')
    assert modal.get_attribute('aria-labelledby') == 'cropperTitle'
    assert modal.evaluate('element => element.matches(":modal")')
    rect = modal.bounding_box()
    assert rect['x'] >= 0 and rect['x'] + rect['width'] <= width + 1
    assert modal.evaluate('element => getComputedStyle(element).backgroundColor') == ('rgb(255, 255, 255)' if theme == 'light' else 'rgb(32, 37, 45)')
    assert browser_page.locator('#applyCrop').evaluate('element => getComputedStyle(element).backgroundColor') == ('rgb(0, 51, 160)' if theme == 'light' else 'rgb(49, 94, 168)')
    assert browser_page.locator('#applyCrop').evaluate('element => getComputedStyle(element).color') == 'rgb(255, 255, 255)'
    browser_page.locator('#outside').evaluate('element => element.focus()')
    assert modal.evaluate('element => element.contains(document.activeElement)')
    for _ in range(6):
        browser_page.keyboard.press('Tab')
        assert modal.evaluate('element => element.contains(document.activeElement)')
    selection = modal.locator('cropper-selection')
    selection.focus()
    before = selection.evaluate('element => element.x')
    browser_page.keyboard.press('ArrowRight')
    assert selection.evaluate('element => element.x') > before
    modal.screenshot(path=f'/tmp/moso-cropper-{theme}-{width}.png')
    browser_page.locator('#applyCrop').click()
    browser_page.wait_for_function("!document.getElementById('cropperModal').open")
    result = browser_page.evaluate("""async () => {
      const input = document.getElementById('image'), file = input.files[0];
      const image = await createImageBitmap(file);
      return {name: file.name, type: file.type, width: image.width, height: image.height,
        visible: !document.getElementById('image-preview').hidden, focus: document.activeElement.id};
    }""")
    assert result['name'] == 'test-image.png' and result['type'] == 'image/png'
    assert result['width'] > 0 and abs(result['width'] / result['height'] - 16 / 9) < 0.02
    assert result['visible'] and result['focus'] == 'image'
    assert not errors


@pytest.mark.e2e
@pytest.mark.integration
@pytest.mark.parametrize('width', [1440, 390])
@pytest.mark.parametrize('zoom,minimum,maximum', [(1, 1200, 1600), (2, 600, 800), (0.1, 1200, 1600)])
def test_cropper_export_uses_source_resolution_and_bounded_zoom(app, live_server, browser_page, width, zoom, minimum, maximum):
    image = _open_harness(app, live_server, browser_page, width=width, source_width=1600)
    _select(browser_page, image)
    if zoom != 1:
        browser_page.evaluate('(zoom) => window.cropperModal.getCropper().getCropperImage().$scale(zoom)', zoom)
    browser_page.locator('#applyCrop').click()
    browser_page.wait_for_function("!document.getElementById('cropperModal').open")
    dimensions = browser_page.evaluate("""async () => {
      const file = document.getElementById('image').files[0];
      const bitmap = await createImageBitmap(file);
      return {width: bitmap.width, height: bitmap.height};
    }""")
    assert minimum <= dimensions['width'] <= maximum
    assert 0 < dimensions['height'] <= 900
    assert abs(dimensions['width'] / dimensions['height'] - 16 / 9) < 0.02


@pytest.mark.e2e
@pytest.mark.integration
@pytest.mark.parametrize('locale,title,apply', [('fi', 'Rajaa kuva', 'Käytä rajausta'), ('en', 'Crop image', 'Use crop'), ('sv', 'Beskär bilden', 'Använd beskärningen')])
def test_cropper_locales_reopen_and_cancel_are_consistent(app, live_server, browser_page, locale, title, apply):
    image = _open_harness(app, live_server, browser_page, locale=locale)
    for index in range(3):
        _select(browser_page, image)
        assert browser_page.locator('#cropperTitle').inner_text() == title
        assert browser_page.locator('#applyCrop').inner_text() == apply
        if index == 0:
            browser_page.keyboard.press('Escape')
        elif index == 1:
            browser_page.locator('#cancelCrop').click()
        else:
            browser_page.mouse.click(2, 2)
        assert not browser_page.locator('#cropperModal').evaluate('element => element.open')
        assert browser_page.locator('#image').input_value() == ''
        assert browser_page.evaluate('document.activeElement.id') == 'image'
        assert browser_page.evaluate('window.cropperModal.getCropper()') is None
        assert browser_page.locator('#cropperContainer').inner_html() == ''


@pytest.mark.e2e
@pytest.mark.integration
def test_cropper_cancel_during_async_apply_cannot_commit_stale_file(app, live_server, browser_page):
    _track_crop_apply_settlement(browser_page)
    image = _open_harness(app, live_server, browser_page)
    _select(browser_page, image)
    browser_page.evaluate("""() => {
      window.cropperModal.getCropper().getCropperSelection().$toCanvas = () =>
        new Promise(resolve => window.finishCrop = () => resolve(document.createElement('canvas')));
    }""")
    browser_page.locator('#applyCrop').click()
    browser_page.wait_for_function('typeof window.finishCrop === "function"')
    browser_page.keyboard.press('Escape')
    browser_page.evaluate('window.finishCrop()')
    browser_page.wait_for_function('window.cropApplySettled === true')
    assert browser_page.locator('#image').input_value() == ''
    assert browser_page.locator('#image-preview').is_hidden()
    _select(browser_page, image)
    assert browser_page.locator('#applyCrop').is_enabled()


@pytest.mark.e2e
@pytest.mark.integration
def test_cropper_decode_and_apply_failures_are_visible_and_recoverable(app, live_server, browser_page):
    image = _open_harness(app, live_server, browser_page)
    browser_page.locator('#image').set_input_files({'name': 'broken.png', 'mimeType': 'image/png', 'buffer': b'not an image'})
    browser_page.locator('#cropperError').wait_for(state='visible')
    assert browser_page.locator('#applyCrop').is_disabled()
    browser_page.locator('#cancelCrop').click()
    _select(browser_page, image)
    browser_page.evaluate("() => { window.cropperModal.getCropper().getCropperSelection().$toCanvas = async () => { throw new Error('Synthetic crop failure'); }; }")
    browser_page.locator('#applyCrop').click()
    browser_page.locator('#cropperError').wait_for(state='visible')
    assert browser_page.locator('#applyCrop').is_enabled()
    assert browser_page.locator('#image').evaluate('element => element.files.length') == 0
    assert browser_page.locator('#image-preview').is_hidden()


async_state = """async () => {
  const input = document.getElementById('image');
  const preview = document.getElementById('image-preview');
  const digest = async bytes => Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', bytes)))
    .map(byte => byte.toString(16).padStart(2, '0')).join('');
  const file = input.files[0];
  const src = preview.getAttribute('src');
  return {
    file: file ? {name: file.name, type: file.type, size: file.size,
      hash: await digest(await file.arrayBuffer())} : null,
    preview: {hash: src ? await digest(new TextEncoder().encode(src)) : null,
      hidden: preview.hidden, visible: preview.getClientRects().length > 0 && getComputedStyle(preview).display !== 'none'}
  };
}"""


@pytest.mark.e2e
@pytest.mark.integration
@pytest.mark.parametrize('width', [1440, 390])
@pytest.mark.parametrize('committed', [False, True])
@pytest.mark.parametrize('exit_path', ['button', 'escape', 'backdrop', 'decode', 'canvas', 'pending-cancel'])
def test_cropper_restores_committed_file_and_preview_together(
    app, live_server, browser_page, width, committed, exit_path
):
    _track_crop_apply_settlement(browser_page)
    image = _open_harness(app, live_server, browser_page, width=width)
    if committed:
        _select(browser_page, image, name='committed.png')
        browser_page.locator('#applyCrop').click()
        browser_page.wait_for_function("!document.getElementById('cropperModal').open")
    expected = browser_page.evaluate(async_state)
    if exit_path == 'decode':
        browser_page.locator('#image').set_input_files({
            'name': 'broken.png', 'mimeType': 'image/png', 'buffer': b'not an image',
        })
        browser_page.locator('#cropperError').wait_for(state='visible')
    else:
        _select(browser_page, image, name='replacement.png')
        if exit_path == 'canvas':
            browser_page.evaluate("() => { window.cropperModal.getCropper().getCropperSelection().$toCanvas = async () => { throw new Error('Synthetic crop failure'); }; }")
            browser_page.locator('#applyCrop').click()
            browser_page.locator('#cropperError').wait_for(state='visible')
        elif exit_path == 'pending-cancel':
            browser_page.evaluate("""() => {
              window.cropperModal.getCropper().getCropperSelection().$toCanvas = () =>
                new Promise(resolve => window.finishCrop = () => resolve(document.createElement('canvas')));
            }""")
            browser_page.locator('#applyCrop').click()
            browser_page.wait_for_function('typeof window.finishCrop === "function"')
            browser_page.keyboard.press('Escape')
            browser_page.evaluate('window.finishCrop()')
            browser_page.wait_for_function('window.cropApplySettled === true')
        elif exit_path == 'button':
            browser_page.locator('#cancelCrop').click()
        elif exit_path == 'escape':
            browser_page.keyboard.press('Escape')
        else:
            browser_page.mouse.click(2, 2)
    assert browser_page.evaluate(async_state) == expected
    if exit_path in ['decode', 'canvas']:
        browser_page.locator('#cancelCrop').click()
        assert browser_page.evaluate(async_state) == expected
    assert browser_page.evaluate('document.activeElement.id') == 'image'
