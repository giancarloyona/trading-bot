import pytest

from trading_bot.settings.env_settings import (
    ENV_FILE,
    ESSENTIAL_ENV_KEYS,
    load_env_from_os,
    load_env_values,
    missing_essential_keys,
)


@pytest.fixture
def valid_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BINANCE_API_KEY", "test_api_key")
    monkeypatch.setenv("BINANCE_API_SECRET", "test_api_secret")
    monkeypatch.setenv("BINANCE_TESTNET", "true")


def test_env_file_exists() -> None:
    assert ENV_FILE.is_file(), f".env file not found at {ENV_FILE}"


def test_env_file_has_essential_keys() -> None:
    if not ENV_FILE.is_file():
        pytest.skip(".env file not found — skipping key validation")

    values = load_env_values()
    missing = missing_essential_keys(values)

    assert not missing, f"Missing or invalid keys in .env: {missing}"


def test_os_environ_has_all_essential_keys(valid_env: None) -> None:
    missing = missing_essential_keys(load_env_from_os())

    assert missing == []


@pytest.mark.parametrize("unset_key", ESSENTIAL_ENV_KEYS)
def test_os_environ_missing_key(
    monkeypatch: pytest.MonkeyPatch,
    valid_env: None,
    unset_key: str,
) -> None:
    monkeypatch.delenv(unset_key, raising=False)

    missing = missing_essential_keys(load_env_from_os())

    assert unset_key in missing


@pytest.mark.parametrize(
    ("key", "placeholder"),
    [
        ("BINANCE_API_KEY", "<your_binance_api_key>"),
        ("BINANCE_API_SECRET", "<your_binance_api_secret>"),
    ],
)
def test_os_environ_rejects_placeholders(
    monkeypatch: pytest.MonkeyPatch,
    valid_env: None,
    key: str,
    placeholder: str,
) -> None:
    monkeypatch.setenv(key, placeholder)

    missing = missing_essential_keys(load_env_from_os())

    assert key in missing


@pytest.mark.parametrize("invalid_value", ["", "maybe", "1"])
def test_os_environ_rejects_invalid_testnet(
    monkeypatch: pytest.MonkeyPatch,
    valid_env: None,
    invalid_value: str,
) -> None:
    monkeypatch.setenv("BINANCE_TESTNET", invalid_value)

    missing = missing_essential_keys(load_env_from_os())

    assert "BINANCE_TESTNET" in missing


@pytest.mark.parametrize("testnet_value", ["true", "false", "True", "FALSE"])
def test_os_environ_accepts_valid_testnet_values(
    monkeypatch: pytest.MonkeyPatch,
    valid_env: None,
    testnet_value: str,
) -> None:
    monkeypatch.setenv("BINANCE_TESTNET", testnet_value)

    missing = missing_essential_keys(load_env_from_os())

    assert missing == []