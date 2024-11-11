## Translating

### Extracting Strings to Translate

To extract the translatable strings from your code, run the following command:

```bash
pybabel extract -F babel.cfg -o messages.pot .
```

### Initializing Language Translation Files

> **Warning**: Only do this the first time when initializing language! This will remove all previous translations!

After extracting the strings, initialize translation files for the supported languages: Finnish (fi), English (en), and Swedish (sv). Use the following commands:

#### Finnish (fi):
```bash
pybabel init -i messages.pot -d translations -l fi
```

#### English (en):
```bash
pybabel init -i messages.pot -d translations -l en
```

#### Swedish (sv):
```bash
pybabel init -i messages.pot -d translations -l sv
```

This will create `.po` files for each language (e.g., `translations/fi/LC_MESSAGES/messages.po`, `translations/en/LC_MESSAGES/messages.po`, `translations/sv/LC_MESSAGES/messages.po`).

### Updating Translation Files

If you add or change translatable strings in your code after the initial setup, you can update the translation files with the following command:

```bash
pybabel update -i messages.pot -d translations
```

This command will update the existing `.po` files with any new or modified strings from `messages.pot`.

### Translating the Strings

Open the `.po` files and add your translations. For example:

- **Finnish (fi):**
    ```po
    msgid "Hello, World!"
    msgstr "Hei, maailma!"
    ```

- **English (en):**
    ```po
    msgid "Hello, World!"
    msgstr "Hello, World!"
    ```

- **Swedish (sv):**
    ```po
    msgid "Hello, World!"
    msgstr "Hej, världen!"
    ```

### Compiling the `.mo` Files

After translating the `.po` files, compile them into `.mo` files:

```bash
pybabel compile -d translations
```

This will generate the compiled `.mo` files for Flask-Babel to use in `translations/fi/LC_MESSAGES/messages.mo`, `translations/en/LC_MESSAGES/messages.mo`, and `translations/sv/LC_MESSAGES/messages.mo`.