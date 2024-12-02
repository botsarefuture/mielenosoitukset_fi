#!/bin/bash

# Extract translatable strings
pybabel extract -F babel.cfg -o messages.pot .

# Update translation files
pybabel update -i messages.pot -d mielenosoitukset_fi/translations

# Compile translation files
pybabel compile -d mielenosoitukset_fi/translations

echo "Extraction, update, and compilation of translation files completed."

git add mielenosoitukset_fi/translations
git commit -m "Update translations"

git push
