#!/bin/bash

# Extract translatable strings
pybabel extract -F babel.cfg -o messages.pot .

# Update translation files
pybabel update -i messages.pot -d translations

# Compile translation files
pybabel compile -d translations

echo "Extraction, update, and compilation of translation files completed."

git add translations
git commit -m "Update translations"

git push
