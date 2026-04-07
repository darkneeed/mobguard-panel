from __future__ import annotations

import re
from typing import Any, Callable


PLACEHOLDER_RE = re.compile(r"\{\{([A-Za-z0-9_]+)\}\}")


def render_optional_template(
    template: str,
    context: dict[str, Any],
    formatter: Callable[[Any], str],
) -> str:
    rendered_lines: list[str] = []
    for line in template.splitlines():
        placeholders = PLACEHOLDER_RE.findall(line)
        if any(context.get(name) in (None, "") for name in placeholders):
            continue
        rendered = line
        for key, value in context.items():
            rendered = rendered.replace(f"{{{{{key}}}}}", formatter(value) if value is not None else "")
        rendered_lines.append(rendered)
    return "\n".join(rendered_lines)
