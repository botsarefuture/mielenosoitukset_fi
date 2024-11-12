from transifex.api import TransifexApi
from transifex.native import init
import os

# Initialize Transifex API with your credentials
token = '1/1/14dfa66d710e78c928222add8fdb602934ba530c'  # Your Token
secret = '1/19a5791f91615afb61088e6e2ca4a53d559b825b'  # Your Secret
project_slug = 'mielenosoitukset_fi'  # Your Transifex project slug
resource_slug = 'messages'  # Your Transifex resource slug (e.g., messages.po)

# Initialize Transifex SDK
init(token, ['fi', 'en', 'sv'])  # Initialize with the source languages (fi, en, sv)

# File paths for the PO files in different languages
po_files = {
    'fi': '../translations/fi/LC_MESSAGES/messages.po',
    'en': '../translations/en/LC_MESSAGES/messages.po',
    'sv': '../translations/sv/LC_MESSAGES/messages.po'
}

# Function to upload PO file to Transifex
def upload_po_to_transifex(language_code, file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        po_content = f.read()

    # Upload the PO file content to the Transifex resource
    try:
        # Use the Transifex API to upload content
        api = TransifexApi(token, secret)
        api.resources.upload_content(project_slug, resource_slug, po_content, language_code)
        print(f"Successfully uploaded {language_code} translation.")
    except Exception as e:
        print(f"Error uploading {language_code} translation: {e}")

# Step: Upload the PO files for each language
for lang, file_path in po_files.items():
    if os.path.exists(file_path):
        upload_po_to_transifex(lang, file_path)
    else:
        print(f"File not found: {file_path}")

