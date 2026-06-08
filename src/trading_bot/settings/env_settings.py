import os
from pathlib import Path

from dotenv import dotenv_values

ENV_FILE = Path(__file__).resolve().parent / ".env"

ESSENTIAL_ENV_KEYS: tuple[str, ...] = (
    "BINANCE_API_KEY",
    "BINANCE_API_SECRET",
    "BINANCE_TESTNET",
)

_PLACEHOLDER_VALUES: dict[str, frozenset[str]] = {
    "BINANCE_API_KEY": frozenset({"<your_binance_api_key>"}),
    "BINANCE_API_SECRET": frozenset({"<your_binance_api_secret>"}),
}

_VALID_TESTNET_VALUES = frozenset({"true", "false"})


def load_env_values(path: Path | None = None) -> dict[str, str | None]:
    return dotenv_values(path or ENV_FILE)


def load_env_from_os() -> dict[str, str | None]:
    return {key: os.environ.get(key) for key in ESSENTIAL_ENV_KEYS}


def missing_essential_keys(values: dict[str, str | None]) -> list[str]:
    missing: list[str] = []
    for key in ESSENTIAL_ENV_KEYS:
        raw = values.get(key)
        if raw is None:
            missing.append(key)
            continue
        value = raw.strip()
        if not value:
            missing.append(key)
            continue
        if key in _PLACEHOLDER_VALUES and value in _PLACEHOLDER_VALUES[key]:
            missing.append(key)
            continue
        if key == "BINANCE_TESTNET" and value.lower() not in _VALID_TESTNET_VALUES:
            missing.append(key)
    return missing