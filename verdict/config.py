"""Configuration: everything secret comes from environment variables (or a local .env)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _load_dotenv(path: Path) -> None:
    """Minimal .env loader (no dependency). Existing env vars win."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


_load_dotenv(Path(__file__).resolve().parent.parent / ".env")


@dataclass(frozen=True)
class Settings:
    paypal_client_id: str = os.environ.get("PAYPAL_CLIENT_ID", "")
    paypal_client_secret: str = os.environ.get("PAYPAL_CLIENT_SECRET", "")
    paypal_environment: str = os.environ.get("PAYPAL_ENVIRONMENT", "sandbox")
    anthropic_api_key: str = os.environ.get("ANTHROPIC_API_KEY", "")
    handling_cost_usd: float = float(os.environ.get("VERDICT_HANDLING_COST_USD", "8"))
    data_dir: Path = Path(os.environ.get("VERDICT_DATA_DIR", Path(__file__).resolve().parent.parent / "data"))

    @property
    def paypal_base_url(self) -> str:
        return "https://api-m.paypal.com" if self.paypal_environment == "live" else "https://api-m.sandbox.paypal.com"

    @property
    def llm_enabled(self) -> bool:
        return bool(self.anthropic_api_key)


settings = Settings()
settings.data_dir.mkdir(parents=True, exist_ok=True)
