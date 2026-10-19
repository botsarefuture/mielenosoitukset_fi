"""Keep responses from the restored app on the sandbox's local dependencies."""


def rewrite(value):
    if isinstance(value, dict):
        return {key: rewrite(item) for key, item in value.items()}
    if isinstance(value, list):
        return [rewrite(item) for item in value]
    if isinstance(value, str):
        return value.replace("https://cdn2.mielenosoitukset.fi/", "https://pentest.mielenosoitukset.fi/media/").replace(
            "https://mielenosoitukset.fi", "https://pentest.mielenosoitukset.fi")
    return value
