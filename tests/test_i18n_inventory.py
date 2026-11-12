"""Focused standard-library checks for the read-only inventory scanner."""
import unittest
from pathlib import Path
import tempfile
from unittest.mock import patch

from scripts.i18n_inventory import (
    ROOT, catalog_report, javascript_literals, object_copy, parse_po,
    react_strings, template_scope, template_strings,
)


class I18nInventoryTests(unittest.TestCase):
    def test_po_multiline_context_plural_flags_and_obsolete(self):
        entries = parse_po('''msgid ""
msgstr "Language: en\\n"

#, fuzzy, python-format
msgctxt "button"
msgid "Tallenna "
"tiedot"
msgid_plural "Tallenna tiedot monikossa"
msgstr[0] ""
msgstr[1] "Saved"

#~ msgid "Vanha"
#~ msgstr "Old"
''')
        self.assertEqual(len(entries), 3)
        self.assertEqual(entries[1]['msgid'], 'Tallenna tiedot')
        self.assertEqual(entries[1]['msgctxt'], 'button')
        self.assertEqual(entries[1]['translations'], {'msgstr[0]': '', 'msgstr[1]': 'Saved'})
        self.assertIn('fuzzy', entries[1]['flags'])
        self.assertTrue(entries[2]['obsolete'])

    def test_duplicate_definitions_include_obsolete(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / 'mielenosoitukset_fi/translations/en/LC_MESSAGES/messages.po'
            path.parent.mkdir(parents=True)
            path.write_text('''#, fuzzy
msgid "Takaisin"
msgstr ""

#~ msgid "Takaisin"
#~ msgstr "Old"

msgid "tapahtuma"
msgstr ""

msgid "tapahtuma"
msgstr "Event"
''')
            with patch('scripts.i18n_inventory.ROOT', root):
                catalog = catalog_report('en')
        self.assertEqual((catalog['active'], catalog['unique'], catalog['empty'],
                          catalog['obsolete'], catalog['fuzzy']), (3, 2, 2, 1, 1))
        self.assertEqual(catalog['duplicates'][0]['obsolete'], [False, True])
        self.assertEqual(catalog['duplicates'][1]['obsolete'], [False, False])

    def test_javascript_nested_templates_and_comments(self):
        text = '''// 'Älä laske kommenttia'
const title = `Tallenna ${flag ? `tiedot ${count}` : 'nyt'}`;
/* "Ei kommenttia" */'''
        values = [value for _, _, value in javascript_literals(text) if value is not None]
        self.assertEqual(values, ['Tallenna ${…}', 'tiedot ${…}', 'nyt'])

    def test_react_literals_jsx_attributes_and_html_templates(self):
        text = '''const label = 'Tallenna';
const html = `<h1>Ota yhteyttä</h1><a href="/info">Tietoa</a>`;
const node = <p title="Ohjeet">Kuvaus</p>;'''
        records = react_strings('sample.tsx', text)
        self.assertEqual([entry['text'] for entry in records],
                         ['Tallenna', 'Ota yhteyttä', 'Tietoa', 'Ohjeet', 'Kuvaus'])
        self.assertEqual(records[-1]['line'], 3)

    def test_template_translation_boundaries_and_attributes(self):
        text = '''<!-- Ei kommenttia -->
<p>{{ _('Käännetty', name='Matti') }}</p>
{% trans %}Myös käännetty{% endtrans %}
<p title="Ohjeet">Ota yhteyttä {{ person }}</p>
{% set title = 'Tallenna' %}
<input type="submit" value="Jatka">
<script>const label = 'Virhe'; const translated = _('Käännetty skripti');</script>
<style>.x::after {content: 'Ei tyyliä'}</style>'''
        records = template_strings('sample.html', text)
        self.assertEqual([entry['text'] for entry in records],
                         ['Ohjeet', 'Ota yhteyttä', 'Tallenna', 'Jatka', 'Virhe'])
        self.assertEqual(records[0]['line'], 4)

    def test_typed_catalog_counts_explicit_overrides_only(self):
        text = "const fi: Catalog = { nav: { home: 'Etusivu' }, close: 'Sulje' };"
        self.assertEqual(set(object_copy(text, 'fi')), {'nav.home', 'close'})
        translated = 'const en: Catalog = { ...fi, nav: { home: "Home" } };'
        self.assertEqual(object_copy(translated, 'en'),
                         {'nav.home': {'text': 'Home', 'offset': translated.index('"Home"')}})

    def test_template_ownership(self):
        root = ROOT / 'mielenosoitukset_fi/templates'
        self.assertEqual(template_scope(root / 'contact.html'), 'Public rollback')
        self.assertEqual(template_scope(root / 'admin_V2/status.html'), 'Admin')
        self.assertEqual(template_scope(root / 'users/auth/login.html'), 'Other Flask/shared')
        self.assertEqual(template_scope(root / 'emails/submit.html'), 'Email')


if __name__ == '__main__':
    unittest.main()
