"""Tests para los recursos de derivación (Chile)."""

from __future__ import annotations

from safety.resources import CHILE_HELPLINES, HelpResource


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


def test_resources_are_immutable() -> None:
    # CHILE_HELPLINES debe ser una tupla, no una lista.
    assert isinstance(CHILE_HELPLINES, tuple)
