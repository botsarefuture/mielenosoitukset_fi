#!/bin/bash

# Extract translatable strings
pybabel extract -F babel.cfg -o messages.pot .

# Update translation files
pybabel update -i messages.pot -d mielenosoitukset_fi/translations

# Compile translation files
pybabel compile -d mielenosoitukset_fi/translations

echo "Extraction, update, and compilation of translation files completed."

# Increment version number
VERSION_FILE="mielenosoitukset_fi/utils/data/VERSION"
if [ -f "$VERSION_FILE" ]; then
    VERSION=$(cat "$VERSION_FILE")
    IFS='.' read -r -a VERSION_PARTS <<< "${VERSION:1}"
    VERSION_PARTS[2]=$((VERSION_PARTS[2] + 1))
    NEW_VERSION="v${VERSION_PARTS[0]}.${VERSION_PARTS[1]}.${VERSION_PARTS[2]}"
    echo $NEW_VERSION > "$VERSION_FILE"
    echo "Version incremented to $NEW_VERSION."
else
    echo "Version file not found."
    exit 1
fi

git add mielenosoitukset_fi/translations "$VERSION_FILE"
git commit -m "Update translations and increment version to $NEW_VERSION"

git push
