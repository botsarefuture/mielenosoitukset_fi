import json
import re
from pathlib import Path

import markdown


source = Path(__file__).resolve().parent.parent / "docs" / "api.md"
document = markdown.Markdown(
    extensions=["fenced_code", "tables", "toc"],
    extension_configs={"toc": {"permalink": True}},
)
html = document.convert(source.read_text(encoding="utf-8"))
html = re.sub(
    r"<pre(?=[\s>])(?![^>]*\btabindex=)", '<pre tabindex="0"', html
)
html = html.replace(
    "<table>",
    '<div class="api-docs-table" tabindex="0" role="region" '
    'aria-label="API-dokumentaatio"><table>',
).replace("</table>", "</table></div>")
print(json.dumps({"html": html, "toc": document.toc}))
