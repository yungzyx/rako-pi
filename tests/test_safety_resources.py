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


def test_crisis_resources_are_short_for_voice() -> None:
    rendered = render_crisis_resources()

    # Por voz nombramos la unidad y dejamos SOLO el SAMU 131 (corto); el resto
    # de números no se recitan — el detalle llega por WhatsApp y la app.
    assert "Bienestar UDD" in rendered
    assert "SAMU: 131" in rendered
    assert "WhatsApp" in rendered
    assert "app" in rendered
    assert "+56 2 2820 3419" not in rendered
    assert "800 200 125" not in rendered
    assert "+56 9 8821 9885" not in rendered
    assert len(rendered) < 220


def test_resources_are_immutable() -> None:
    # CHILE_HELPLINES y UDD_RESOURCES deben ser tuplas, no listas.
    assert isinstance(CHILE_HELPLINES, tuple)
    assert isinstance(UDD_RESOURCES, tuple)
