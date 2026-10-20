"""Keep responses from the restored app on the sandbox's local dependencies."""
import re


LOCAL_ASSETS = {
    "https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js":
        "/static/dr-vendor/bootstrap-5.3.3.bundle.min.js",
    "https://code.jquery.com/jquery-3.7.0.min.js": "/static/dr-vendor/jquery-3.7.0.min.js",
    'https://code.jquery.com/jquery-3.6.0.min.js': '/static/dr-vendor/jquery-3.6.0.min.js',
    'https://cdn.quilljs.com/1.3.6/quill.min.js': '/static/dr-vendor/quill-1.3.6.min.js',
    'https://cdn.quilljs.com/1.3.6/quill.snow.css': '/static/dr-vendor/quill-1.3.6.snow.css',
    'https://cdn.quilljs.com/1.3.6/quill.bubble.css': '/static/dr-vendor/quill-1.3.6.bubble.css',
    'https://cdn.quilljs.com/1.3.6/quill.core.css': '/static/dr-vendor/quill-1.3.6.core.css',
    'https://cdn.jsdelivr.net/npm/flatpickr@4.6.13/dist/flatpickr.min.js': '/static/dr-vendor/flatpickr-4.6.13.min.js',
    'https://cdn.jsdelivr.net/npm/flatpickr@4.6.13/dist/flatpickr.min.css': '/static/dr-vendor/flatpickr-4.6.13.min.css',
    'https://cdn.socket.io/4.7.2/socket.io.min.js': '/static/dr-vendor/socket.io-4.7.2.min.js',
    'https://cdn.ckeditor.com/ckeditor5/43.2.0/ckeditor5.css': '/static/dr-vendor/ckeditor5-43.2.0.css',
    "https://cdn.jsdelivr.net/npm/flatpickr/dist/flatpickr.min.css": "/static/dr-vendor/flatpickr-4.6.13.min.css",
    "https://cdn.jsdelivr.net/npm/flatpickr": "/static/dr-vendor/flatpickr-4.6.13.min.js",

}

def rewrite(value):
    if isinstance(value, dict):
        return {key: rewrite(item) for key, item in value.items()}
    if isinstance(value, list):
        return [rewrite(item) for item in value]
    if isinstance(value, str):
        for source, local in sorted(LOCAL_ASSETS.items(), key=lambda item: len(item[0]), reverse=True):
            pattern = re.escape(source) + r'(?=$|[?#\s\x22\x27<>),])'
            value = re.sub(pattern, lambda match: local, value)
        return value.replace("https://cdn2.mielenosoitukset.fi/", "https://pentest.mielenosoitukset.fi/media/").replace(
            "https://mielenosoitukset.fi", "https://pentest.mielenosoitukset.fi")
    return value
