from pathlib import Path


def test_case_cards_use_shared_copy_and_title_wrappers():
    case_list = Path(
        "mielenosoitukset_fi/templates/admin_V2/cases/all.html"
    ).read_text(encoding="utf-8")
    case_detail = Path(
        "mielenosoitukset_fi/templates/admin_V2/cases/case.html"
    ).read_text(encoding="utf-8")

    assert case_list.count("<div><span>{{ _(") >= 4
    assert case_detail.count('class="admin-section-card__title"><h2>') >= 5
