"""Tests para los recursos de derivación (Chile)."""

from __future__ import annotations

from safety.resources import CHILE_HELPLINES, UDD_RESOURCES, HelpResource, render_crisis_resources


def test_chile_helplines_is_non_empty() -> None:
    assert len(CHILE_HELPLINES) > 0


def test_chile_helplines_all_have_required_fields() -> None:
    for resource in CHILE_HELPLINES:
        assert isinstance(resource, HelpResource)
        assert resource.name
        assert resource.contact
        assert resource.description


def test_salud_responde_is_present() -> None:
    names = [r.name.lower() for r in CHILE_HELPLINES]

    assert any("salud responde" in n for n in names)


def test_udd_resources_include_required_contacts() -> None:
    rendered = render_crisis_resources()

    assert "+56 2 2820 3419" in rendered
    assert "800 200 125" in rendered
    assert "+56 9 8821 9885" in rendered
    assert "600 360 7777" in rendered


def test_resources_are_immutable() -> None:
    # CHILE_HELPLINES y UDD_RESOURCES deben ser tuplas, no listas.
    assert isinstance(CHILE_HELPLINES, tuple)
    assert isinstance(UDD_RESOURCES, tuple)
