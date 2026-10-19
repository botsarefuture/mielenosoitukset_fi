"""Keep responses from the restored app on the sandbox's local dependencies."""


LOCAL_ASSETS = {
    "https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js":
        "/static/dr-vendor/bootstrap-5.3.3.bundle.min.js",
    "https://code.jquery.com/jquery-3.7.0.min.js": "/static/dr-vendor/jquery-3.7.0.min.js",
}

def rewrite(value):
    if isinstance(value, dict):
        return {key: rewrite(item) for key, item in value.items()}
    if isinstance(value, list):
        return [rewrite(item) for item in value]
    if isinstance(value, str):
        for source, local in LOCAL_ASSETS.items():
            value = value.replace(source, local)
        return value.replace("https://cdn2.mielenosoitukset.fi/", "https://pentest.mielenosoitukset.fi/media/").replace(
            "https://mielenosoitukset.fi", "https://pentest.mielenosoitukset.fi")
    return value
