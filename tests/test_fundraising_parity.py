"""The React host ports fundraising_details; both read the same fixture.

scripts/verify_public_host.mjs checks the TypeScript port against these cases.
"""

import json
from datetime import date
from pathlib import Path

import pytest

from mielenosoitukset_fi.utils.fundraising import fundraising_details

CASES = json.loads((Path(__file__).parent / "fixtures/fundraising_parity.json").read_text(encoding="utf-8"))


def _plain(details):
    return {key: value.isoformat() if isinstance(value, date) else value for key, value in sorted(details.items())}


@pytest.mark.parametrize("case", CASES, ids=[case["name"] for case in CASES])
def test_python_fundraising_matches_shared_fixture(case):
    assert _plain(fundraising_details(case["input"], today=date.fromisoformat(case["today"]))) == case["expected"]


def test_fixture_covers_open_closed_and_unsafe_urls():
    assert any(case["expected"]["can_donate"] for case in CASES)
    assert any(not case["expected"]["can_donate"] and case["expected"]["confirmed"] for case in CASES)
    assert sum(case["name"].startswith("url ") for case in CASES) >= 10
