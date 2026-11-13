#!/usr/bin/env python3
"""Read-only gettext and UI copy inventory; Python standard library only."""
import argparse
import ast
from collections import defaultdict
from html import unescape
from html.parser import HTMLParser
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
START = '<!-- i18n-inventory:start -->'
END = '<!-- i18n-inventory:end -->'
FAMILIES = ('Home and listings', 'Detail', 'Cities and calendar', 'Submit',
            'Information pages', 'Campaign and fundraising', 'Contact', 'Status',
            'API docs', 'Suggestion forms', 'Organizations', 'Pride', 'Shared shell and other')
WORDS = set('''alkaen ajankohta ajankohdat anna alueella api-dokumentaatio apua arvo
avaa edellinen ehdota ei emme etusivu hae haku hallinta hanke heti ilmoita ilmoitukset
ilmoitus ja jatka joko järjestäjä kaikki kalenteri kartta katso kaupungissa kaupungit
kaupunki kellonaika kerro kirjaudu kirjoita kohti koko kuva kuvaus kutsu lataa ladataan
lisää logo luo luotu lue luokitus maa maksu me meille merkitse miten mukaan muuta
muokkaa muut muutokset nimi nopeus nouto nyt ohje ohjeet olet oma on organisaatio
organisaation organisaatiot osoite ota osallistujat osallistun otsikko paikka palaa
palvelu peru peruuta peruttu perusosoite pienennä poista profiili puuttuu reitti
rekisteröidy saaja salasana samana sarja seuraa seuraava sijainti sinulla sinut sivu
sivusto sulje suodata suodattimet suomi suomessa suomalainen tallenna tallennettu
tapahtuma tapahtuman tapahtumat tapahtumia tapahtumien tai takaisin tiedot tieto
tietoa tila toiminto toimii toimitus tulokset tunnista tunnus tuki tulevat uudelleen
uusi uusimmat vain vahvista vaihda valikko valitse valmis vastaanottaja verkkosivut
verkkosivusto virhe virheellinen voit vuosi yhteystiedot yhteys yritä ylläpito
mielenosoitus mielenosoituksen mielenosoitukset mielenosoituksia mielenosoitusten
ihmisluettava dokumentaatio julkiselle lahjoita lahjoitus tammikuu helmikuu maaliskuu
huhtikuu toukokuu kesäkuu heinäkuu elokuu syyskuu lokakuu marraskuu joulukuu
maanantai tiistai keskiviikko torstai perjantai lauantai sunnuntai seurataan tilaa
siirry osallistujaa kopioi kopioitu jaa facebook-tapahtuma aloitus perustiedot
facebook-tapahtumalinkki tuotu ilmastonmuutoksen tagit pilkuilla kuvausteksti
alkamisaika paikallaan marssi muu reitin paikkakunta katuosoite etsi yhteystietosi
roolisi tietosuojaselosteen kiitos mahdolliset osumat virhekoodi suosittelemme
osallistuu'''.split())
TOKEN = re.compile(r'''//[^\n]*|/\*[\s\S]*?\*/|"(?:\\[\s\S]|[^"\\])*"|'(?:\\[\s\S]|[^'\\])*'|`(?:\\[\s\S]|[^`\\])*`''')


def parse_po(text):
    entries = []
    entry = {'flags': [], 'obsolete': False, 'translations': {}}
    field = None

    def finish():
        nonlocal entry, field
        if 'msgid' in entry:
            entries.append(entry)
        entry = {'flags': [], 'obsolete': False, 'translations': {}}
        field = None

    for number, raw in enumerate(text.splitlines(), 1):
        if not raw.strip():
            finish()
            continue
        line = raw
        if line.startswith('#~'):
            entry['obsolete'] = True
            line = line[2:].lstrip()
        if line.startswith('#,'):
            entry['flags'].extend(part.strip() for part in line[2:].split(','))
        elif line.startswith('#'):
            continue
        else:
            match = re.match(r'(msgctxt|msgid_plural|msgid|msgstr(?:\[\d+\])?)\s+(".*")$', line)
            if match:
                name, quoted = match.groups()
                if name == 'msgid' and 'msgid' in entry:
                    finish()
                field = name
                value = ast.literal_eval(quoted)
                if name.startswith('msgstr'):
                    entry['translations'][name] = value
                else:
                    entry[name] = value
                    if name == 'msgid':
                        entry['line'] = number
            elif line.startswith('"') and field:
                value = ast.literal_eval(line)
                target = entry['translations'] if field.startswith('msgstr') else entry
                target[field] += value
            else:
                raise ValueError(f'Unsupported PO syntax at line {number}: {raw}')
    finish()
    return entries


def catalog_report(locale):
    path = f'mielenosoitukset_fi/translations/{locale}/LC_MESSAGES/messages.po'
    entries = parse_po((ROOT / path).read_text())
    active = [entry for entry in entries if entry['msgid'] and not entry['obsolete']]
    keys = defaultdict(list)
    for entry in active:
        keys[(entry.get('msgctxt', ''), entry['msgid'])].append(entry['line'])
    definitions = defaultdict(list)
    for entry in entries:
        if entry['msgid']:
            definitions[(entry.get('msgctxt', ''), entry['msgid'])].append(entry)
    return {
        'path': path, 'active': len(active), 'unique': len(keys),
        'empty': sum(not any(entry['translations'].values()) for entry in active),
        'partial_plural': sum(bool(entry.get('msgid_plural')) and any(entry['translations'].values())
                              and not all(entry['translations'].values()) for entry in active),
        'fuzzy': sum('fuzzy' in entry['flags'] for entry in active),
        'obsolete': sum(bool(entry['msgid']) and entry['obsolete'] for entry in entries),
        'duplicates': [{'context': context, 'msgid': msgid,
                        'lines': [entry['line'] for entry in copies],
                        'obsolete': [entry['obsolete'] for entry in copies]}
                       for (context, msgid), copies in sorted(definitions.items()) if len(copies) > 1],
        'entries': entries,
    }


def normalize(text):
    return re.sub(r'\s+', ' ', unescape(text)).strip()


def finnish(text):
    text = re.sub(r'\$\{[^}]*}', '', text)
    if not text or text.startswith(('/', '#', 'http:', 'https:')):
        return False
    if re.fullmatch(r'[^\s@]+@[^\s@]+|[\w.-]+\.(?:fi|com|org)', text):
        return False
    return bool(re.search('[äöÄÖ]', text) or set(re.findall(r'[\w-]+', text.lower())) & WORDS)


def template_copy(text):
    value = text.strip(' :|–—-.,;()')
    if not re.search(r'[A-Za-zÄÖäöÅå]{2}', value):
        return False
    if value in ('index, follow', 'noindex, follow', 'noindex, nofollow', 'OpenAPI', 'h min',
                 'Facebook', 'Twitter', 'Instagram', 'LinkedIn', 'YouTube', 'TikTok',
                 'logo', 'vvvv-kk-pp', 'pp.kk.vvvv'):
        return False
    if set(value.split()) <= {'Facebook', 'Twitter', 'Instagram', 'LinkedIn', 'YouTube', 'TikTok'}:
        return False
    if re.fullmatch(r'[^\s@]+@[^\s@]+|[\w.-]+\.(?:fi|com|org|yaml|html|png)', value):
        return False
    if value.startswith(('/', '#', 'http:', 'https:', 'width=')):
        return False
    if not finnish(value) and re.fullmatch(r'[\w-]*[-_][\w-]*', value):
        return False
    return True


def record(path, text, offset, value, kind):
    return {'path': path, 'line': text.count('\n', 0, offset) + 1,
            'text': normalize(value), 'kind': kind}


def react_strings(path, text):
    masked = list(text)
    records = []
    for start, end, value in javascript_literals(text):
        if value is not None and finnish(value):
            if re.search(r'<[a-zA-Z][\w-]*(?:\s|>)', value):
                for item in template_strings(path, re.sub(r'\$\{[^}]*}', ' ', value)):
                    if finnish(item['text']):
                        item['line'] += text.count('\n', 0, start)
                        item['kind'] = 'html-in-literal'
                        records.append(item)
            else:
                records.append(record(path, text, start, value, 'literal'))
        masked[start:end] = ['\n' if char == '\n' else ' ' for char in text[start:end]]
    if path.endswith('.tsx'):
        for match in re.finditer(r'(?:>|})([^<>{}]+)(?=[<{])', ''.join(masked)):
            value = match[1]
            if finnish(value) and not re.search(r'[;=]', value):
                records.append(record(path, text, match.start(1), value, 'jsx-text'))
    return sorted(records, key=lambda item: item['line'])


def javascript_literals(text):
    tokens = []

    def scan(position, expression=False):
        depth = 0
        while position < len(text):
            start = position
            if text.startswith('//', position) or text.startswith('/*', position):
                end = text.find('\n' if text[position + 1] == '/' else '*/', position + 2)
                position = len(text) if end < 0 else end + (0 if text[start + 1] == '/' else 2)
                tokens.append((start, position, None))
                continue
            char = text[position]
            if char in "\"'`":
                quote, chunks = char, []
                position += 1
                while position < len(text):
                    if text[position] == '\\':
                        chunks.append(text[position:position + 2])
                        position += 2
                    elif text[position] == quote:
                        position += 1
                        tokens.append((start, position, ''.join(chunks)))
                        break
                    elif quote == '`' and text.startswith('${', position):
                        expression_start = position
                        position = scan(position + 2, True)
                        chunks.append('${…}' + '\n' * text[expression_start:position].count('\n'))
                    elif quote != '`' and text[position] in '\r\n':
                        position = start + 1
                        break
                    else:
                        chunks.append(text[position])
                        position += 1
                continue
            if expression:
                if char == '{':
                    depth += 1
                elif char == '}':
                    if depth == 0:
                        return position + 1
                    depth -= 1
            position += 1
        return position

    scan(0)
    return sorted(tokens)


def object_copy(text, name):
    start = re.search(r'const ' + name + r'\s*:\s*\w+\s*=\s*{', text)
    if not start:
        raise ValueError(f'Missing typed copy object: {name}')
    stack, key, entries = [''], None, {}
    tokens = re.compile(TOKEN.pattern + r'|[{}]|\b\w+(?=\s*:)')
    for match in tokens.finditer(text, start.end()):
        token = match.group()
        if token.startswith(('//', '/*')):
            continue
        if token == '{':
            stack.append(key or '')
            key = None
        elif token == '}':
            stack.pop()
            if not stack:
                return entries
        elif token.startswith(("'", '"', '`')):
            if key:
                entries['.'.join([*filter(None, stack), key])] = {
                    'text': token[1:-1], 'offset': match.start()}
                key = None
        else:
            key = token
    raise ValueError(f'Unclosed copy object: {name}')


def translated_mask(text):
    text = re.sub(r'{%[-+]?\s*trans\b[\s\S]*?{%[-+]?\s*endtrans\s*[-+]?%}',
                  lambda match: re.sub(r'[^\n]', ' ', match.group()), text)
    chars = list(text)
    for match in re.finditer(r'\b(?:_|gettext|ngettext)\s*\(', text):
        depth = 1
        position = match.end()
        while position < len(text) and depth:
            if text[position] in "\"'":
                quote = text[position]
                position += 1
                while position < len(text) and text[position] != quote:
                    position += 2 if text[position] == '\\' else 1
            elif text[position] == '(':
                depth += 1
            elif text[position] == ')':
                depth -= 1
            position += 1
        chars[match.start():position] = ['\n' if char == '\n' else ' ' for char in text[match.start():position]]
    return ''.join(chars)


class TemplateText(HTMLParser):
    def __init__(self, path, text):
        super().__init__(convert_charrefs=True)
        self.path, self.text = path, text
        self.records = []
        self.hidden = None

    def add(self, value, kind):
        if template_copy(normalize(value)):
            self.records.append({'path': self.path, 'line': self.getpos()[0],
                                 'text': normalize(value), 'kind': kind})

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.hidden = tag
        if not self.hidden:
            for key, value in attrs:
                if key in ('title', 'alt', 'placeholder', 'aria-label', 'aria-description', 'content') or (
                    key == 'value' and tag == 'input' and dict(attrs).get('type') in ('submit', 'button')
                ):
                    self.add(value or '', f'attribute:{key}')

    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self.hidden = None

    def handle_data(self, data):
        if self.hidden == 'script':
            for item in react_strings(self.path, data):
                item['line'] += self.getpos()[0] - 1
                item['kind'] = 'inline-script:' + item['kind']
                self.records.append(item)
        elif not self.hidden:
            self.add(data, 'html-text')


def template_strings(path, text):
    masked = re.sub(r'{#[\s\S]*?#}|<!--[\s\S]*?-->',
                    lambda match: re.sub(r'[^\n]', ' ', match.group()), text)
    masked = translated_mask(masked)
    masked = re.sub(r'{%\s*block\s+(?:main_class|robots|og_url|og_image|twitter_image|canonical|body_font_styles)\s*%}[\s\S]*?{%\s*endblock\s*%}',
                    lambda match: re.sub(r'[^\n]', ' ', match.group()), masked)
    records = []
    for match in re.finditer(r'{{[\s\S]*?}}|{%[\s\S]*?%}', masked):
        for literal in TOKEN.finditer(match.group()):
            if literal.group().startswith(('"', "'")) and finnish(literal.group()[1:-1]) and template_copy(literal.group()[1:-1]):
                records.append(record(path, text, match.start() + literal.start(), literal.group()[1:-1], 'jinja-literal'))
    masked = re.sub(r'{{[\s\S]*?}}|{%[\s\S]*?%}',
                    lambda match: ('<!-- -->' if re.match(r'{%\s*(?:block|endblock)\b', match.group()) else ' ') + '\n' * match.group().count('\n'), masked)
    parser = TemplateText(path, text)
    parser.feed(masked)
    return sorted(records + parser.records, key=lambda item: item['line'])


def family(path):
    name = Path(path).stem.lower()
    if any(word in path.lower() for word in ('suggest', 'organization-fill', 'organizationfillscreen', 'fill_info')):
        return 'Suggestion forms'
    if any(word in path.lower() for word in ('campaign', 'fundrais', 'kampanja', 'volunteer', 'confirmation')):
        return 'Campaign and fundraising'
    if 'contact' in name:
        return 'Contact'
    if 'status' in name:
        return 'Status'
    if 'api' in name and 'doc' in name:
        return 'API docs'
    if any(word in path.lower() for word in ('information', '/ohjeet/', '/manuals/')) or name in ('info', 'privacy', 'terms', 'manual_base') or '/upcoming/' in path:
        return 'Information pages'
    if any(word in path.lower() for word in ('submit', '/submit/', 'cityselect', 'datefield', 'descriptioneditor', 'organizerlist')):
        return 'Submit'
    if any(word in path.lower() for word in ('calendar', '/cities/', 'citiesscreen', 'citiespage')) or name in ('cities', 'city', 'paikkakunta-dropdown', 'today_demos', 'todayscreen'):
        return 'Cities and calendar'
    if 'organization' in path.lower():
        return 'Organizations'
    if any(word in path.lower() for word in ('detail', 'demo_views', 'siblings', 'cancel_demonstration', 'preview')):
        return 'Detail'
    if 'pride' in path.lower():
        return 'Pride'
    if any(word in name for word in ('listing', 'list', 'home', 'index')) or name in ('tag_list',):
        return 'Home and listings'
    return 'Shared shell and other'


ROLLBACK_FILES = set('''api_docs cities city contact detail detail_react fundraising index info
list list_legacy privacy siblings status submit submit_react suggest_change tag_list terms today_demos'''.split())


def template_scope(path):
    relative = path.relative_to(ROOT / 'mielenosoitukset_fi/templates')
    if any(part in ('admin', 'admin_V2') for part in relative.parts) or path.name == 'admin_base.html':
        return 'Admin'
    if relative.parts[0] == 'emails':
        return 'Email'
    if (len(relative.parts) == 1 and path.stem in ROLLBACK_FILES) or relative.parts[0] in ('kampanja', 'pride-nakyvaksi', 'ohjeet', 'upcoming', 'organizations'):
        return 'Public rollback'
    return 'Other Flask/shared'


COPY_FILES = {'app/i18n.ts', 'app/detail.ts', 'app/submit-copy.ts', 'app/listing.ts',
              'app/information.ts', 'app/contact-route.ts', 'app/campaign-route.ts',
              'components/organization/copy.ts', 'data/campaign.ts'}


def inventory():
    catalogs = {locale: catalog_report(locale) for locale in ('en', 'sv')}
    react, templates = [], []
    main_copy = (ROOT / 'frontend/src/app/i18n.ts').read_text()
    fi_copy = object_copy(main_copy, 'fi')
    ts_catalogs = {}
    for locale in ('en', 'sv'):
        overrides = object_copy(main_copy, locale)
        ts_catalogs[locale] = {
            'keys': len(fi_copy), 'explicit': len(overrides),
            'missing': sorted(set(fi_copy) - set(overrides)),
            'same_as_fi': sorted(key for key in fi_copy if key in overrides and fi_copy[key]['text'] == overrides[key]['text']),
        }
    fi_only = {path: len(object_copy((ROOT / path).read_text(), 'fi')) for path in (
        'frontend/src/app/detail.ts', 'frontend/src/app/submit-copy.ts')}
    detail_source = (ROOT / 'frontend/src/app/detail.ts').read_text()
    submit_source = (ROOT / 'frontend/src/app/submit-copy.ts').read_text()
    if not all(re.search(r'\b' + locale + r':\s*fi\b', detail_source) for locale in ('en', 'sv')) or not re.search(
        r'const translations[^\n]*=\s*{};', submit_source
    ):
        raise ValueError('Detail/submit locale overrides changed; update their inventory extraction')
    for path in sorted((ROOT / 'frontend/src').rglob('*')):
        if path.suffix not in ('.ts', '.tsx') or re.search(r'\.(?:test|spec|d)\.tsx?$', path.name):
            continue
        relative = path.relative_to(ROOT).as_posix()
        text = path.read_text()
        if path.name == 'i18n.ts':
            text = text[:text.index('const en:')]
        for item in react_strings(relative, text):
            item['family'] = family(relative)
            if path.name == 'i18n.ts':
                home_start = text.index('  home: {', text.index('const fi:'))
                if item['line'] >= text.count('\n', 0, home_start) + 1:
                    item['family'] = 'Home and listings'
            item['placement'] = 'copy module' if path.relative_to(ROOT / 'frontend/src').as_posix() in COPY_FILES else 'inline'
            react.append(item)
    for path in sorted((ROOT / 'mielenosoitukset_fi/templates').rglob('*.html')):
        relative = path.relative_to(ROOT).as_posix()
        for item in template_strings(relative, path.read_text()):
            item['family'] = family(relative)
            item['scope'] = template_scope(path)
            templates.append(item)
    return {'catalogs': catalogs, 'ts_catalogs': ts_catalogs, 'fi_only': fi_only,
            'react': react, 'templates': templates}


def cell(value):
    return str(value).replace('|', '\\|').replace('\n', ' ')


def table(headers, rows):
    return '\n'.join('| ' + ' | '.join(cell(value) for value in row) + ' |'
                     for row in [headers, ['---'] * len(headers), *rows])


def report(data):
    catalogs = data['catalogs']
    parts = ['### Gettext totals', table(
        ['Locale', 'Total msgids', 'Active entries', 'Unique active keys', 'Empty', 'Fuzzy', 'Obsolete', 'Partial plurals', 'Duplicate keys'],
        [[locale, catalogs[locale]['active'] + catalogs[locale]['obsolete'],
          *[catalogs[locale][key] for key in ('active', 'unique', 'empty', 'fuzzy', 'obsolete', 'partial_plural')],
          len(catalogs[locale]['duplicates'])] for locale in catalogs])]
    parts += ['### Duplicate definitions', table(['Locale', 'msgid', 'PO lines'], [
        [locale, '`' + duplicate['msgid'] + '`', ', '.join(str(line) + (' (obsolete)' if obsolete else '')
          for line, obsolete in zip(duplicate['lines'], duplicate['obsolete']))]
        for locale, catalog in catalogs.items() for duplicate in catalog['duplicates']])]
    parts += ['### Main TypeScript catalog', table(
        ['Locale', 'Finnish keys', 'Explicit overrides', 'Missing overrides', 'Identical to Finnish'],
        [[locale, values['keys'], values['explicit'], len(values['missing']), ', '.join(values['same_as_fi'])]
         for locale, values in data['ts_catalogs'].items()])]
    parts += ['### Finnish-only typed message objects', table(
        ['File', 'Finnish keys', 'Missing en overrides', 'Missing sv overrides'],
        [[f'`{path}`', count, count, count] for path, count in data['fi_only'].items()])]
    parts += ['### React Finnish candidates', table(
        ['Family', 'Occurrences', 'Unique text', 'Copy module', 'Inline', 'Absent en PO', 'Absent sv PO'],
        [[group, len(items), len({item['text'] for item in items}),
          sum(item['placement'] == 'copy module' for item in items),
          sum(item['placement'] == 'inline' for item in items),
          *[len({item['text'] for item in items} - {entry['msgid'] for entry in catalogs[locale]['entries']
                if not entry['obsolete'] and not entry.get('msgctxt')}) for locale in catalogs]]
         for group, items in groups(data['react'])])]
    parts += ['### Template unwrapped copy candidates', table(
        ['Scope', 'Family', 'Occurrences', 'Unique text'],
        [[scope, group, len(items), len({item['text'] for item in items})]
         for scope in ('Public rollback', 'Other Flask/shared', 'Email', 'Admin')
         for group, items in groups([item for item in data['templates'] if item['scope'] == scope], scope == 'Public rollback')])]
    parts.append('React total: **%s occurrences / %s unique texts**. Templates: **%s occurrences / %s unique texts**.' % (
        len(data['react']), len({item['text'] for item in data['react']}),
        len(data['templates']), len({item['text'] for item in data['templates']})))
    return '\n\n'.join(parts)


def groups(records, include_empty=False):
    grouped = defaultdict(list)
    if include_empty:
        grouped.update({name: [] for name in FAMILIES})
    for item in records:
        grouped[item['family']].append(item)
    return sorted(grouped.items())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--json', action='store_true', help='Full file/line/text worklist and PO entries')
    parser.add_argument('--check', action='store_true', help='Check the generated section of docs/i18n-inventory.md')
    args = parser.parse_args()
    data = inventory()
    rendered = report(data)
    if args.check:
        document = (ROOT / 'docs/i18n-inventory.md').read_text()
        actual = document.split(START, 1)[1].split(END, 1)[0].strip()
        if actual != rendered:
            raise SystemExit('Inventory is stale: regenerate with python3 scripts/i18n_inventory.py')
        print('Inventory numbers match docs/i18n-inventory.md')
    else:
        print(json.dumps(data, ensure_ascii=False, indent=2) if args.json else rendered)


if __name__ == '__main__':
    main()
