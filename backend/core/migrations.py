"""Schema migrations (SPEC §3: after v0.1 every data-shape change needs one).
Registered on `default_migrations`, applied by Storage.read_doc (file is rewritten)."""

from __future__ import annotations

from typing import Any

from backend.core.storage import default_migrations


@default_migrations.register("map", 1)
def _map_v1_to_v2(d: dict[str, Any]) -> dict[str, Any]:
    """v0.1 maps had status_mode "manual" everywhere. Nodes the user already set by hand stay manual;
    untouched ones (not_started) become auto so performance-based status (v0.2) can take over."""
    for n in (d.get("nodes") or {}).values():
        if n.get("status", "not_started") == "not_started":
            n["status_mode"] = "auto"
        else:
            n["status_mode"] = "manual"
    return d
