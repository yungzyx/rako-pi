from __future__ import annotations

from product.whatsapp_templates import list_whatsapp_templates, whatsapp_templates_to_dict


def test_whatsapp_templates_are_privacy_safe_for_meta_submission() -> None:
    templates = list_whatsapp_templates()
    payload = whatsapp_templates_to_dict()

    assert len(templates) >= 3
    assert all(template.safe_outside_24h_window for template in templates)
    assert "task titles" in payload["notes"][1]
    assert all("{{" in template.body or template.variables == () for template in templates)
