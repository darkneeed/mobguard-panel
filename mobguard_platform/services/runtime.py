from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..runtime import RuntimeContext


@dataclass
class RuntimeConfigService:
    context: RuntimeContext

    def load(self) -> dict[str, Any]:
        return self.context.reload_config()

    def settings(self) -> dict[str, Any]:
        return self.context.config.setdefault("settings", {})
