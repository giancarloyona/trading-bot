from datetime import UTC, datetime
from unittest.mock import MagicMock, create_autospec, patch

import pytest
from binance.client import Client
from binance.exceptions import BinanceAPIException, BinanceRequestException
from freezegun import freeze_time

from trading_bot.exchanges.binance.client import (
    ApiCredentials,
    BinanceWrapper,
    ClockDriftError,
    ExchangeInfo,
)


def make_api_exception(status_code: int, code: int, msg: str) -> BinanceAPIException:
    response = MagicMock(status_code=status_code)
    return BinanceAPIException(response, status_code, f'{{"code": {code}, "msg": "{msg}"}}')


SERVER_TIME_MS = int(datetime.now(UTC).timestamp() * 1000)
FROZEN_DATETIME = datetime.fromtimestamp(SERVER_TIME_MS / 1000, tz=UTC).isoformat()


MOCK_EXCHANGE_RESPONSE = {
    "timezone": "UTC",
    "serverTime": FROZEN_DATETIME,
    "rateLimits": [],
    "exchangeFilters": [],
    "symbols": [
        {"symbol": "BTCUSDT", "status": "TRADING"},
        {"symbol": "ETHUSDT", "status": "TRADING"},
        {"symbol": "XYZUSDT", "status": "BREAK"},
        {"symbol": "ABCUSDT", "status": "PRE_DELIVERING"},
    ],
}

MOCK_ACCOUNT_RESPONSE = {
    "canTrade": True,
    "canWithdraw": False,
    "canDeposit": True,
}

@pytest.fixture
def mock_client():
    with patch("trading_bot.exchanges.binance.client.Client") as mock_class:
        client = create_autospec(Client, instance=True)
        mock_class.return_value = client
        yield client


@pytest.fixture
def wrapper(mock_client):
    return BinanceWrapper(api_key="fake_key", api_secret="fake_secret")


class TestPing:
    def test_returns_true_on_success(self, wrapper, mock_client):
        mock_client.ping.return_value = {}
        assert wrapper.ping() is True

    def test_returns_false_on_request_exception(self, wrapper, mock_client):
        mock_client.ping.side_effect = BinanceRequestException("connection error")
        assert wrapper.ping() is False

    def test_returns_false_on_api_exception(self, wrapper, mock_client):
        mock_client.ping.side_effect = make_api_exception(401, -2014, "API-key format invalid.")
        assert wrapper.ping() is False


class TestGetServerTime:
    def test_returns_datetime_utc_on_success(self, wrapper, mock_client):
        mock_client.get_server_time.return_value = {"serverTime": SERVER_TIME_MS}

        with freeze_time(FROZEN_DATETIME):
            result = wrapper.get_server_time()

        assert isinstance(result, datetime)
        assert result.tzinfo == UTC

    def test_converts_milliseconds_correctly(self, wrapper, mock_client):
        mock_client.get_server_time.return_value = {"serverTime": SERVER_TIME_MS}

        with freeze_time(FROZEN_DATETIME):
            result = wrapper.get_server_time()

        expected = datetime.fromtimestamp(SERVER_TIME_MS / 1000, tz=UTC)
        assert result == expected

    def test_raises_connection_error_on_request_exception(self, wrapper, mock_client):
        mock_client.get_server_time.side_effect = BinanceRequestException("timeout")
        with pytest.raises(ConnectionError):
            wrapper.get_server_time()

    def test_raises_connection_error_on_api_exception(self, wrapper, mock_client):
        mock_client.get_server_time.side_effect = make_api_exception(500, -1000, "Unknown error.")
        with pytest.raises(ConnectionError):
            wrapper.get_server_time()


class TestGetServerTimeDrift:
    def test_returns_datetime_when_drift_is_within_threshold(self, wrapper, mock_client):
        mock_client.get_server_time.return_value = {"serverTime": SERVER_TIME_MS}

        with freeze_time(FROZEN_DATETIME):
            result = wrapper.get_server_time()

        assert isinstance(result, datetime)

    def test_raises_clock_drift_error_when_local_clock_is_behind(self, wrapper, mock_client):
        mock_client.get_server_time.return_value = {"serverTime": SERVER_TIME_MS}
        behind_time = datetime.fromtimestamp((SERVER_TIME_MS - 2000) / 1000, tz=UTC).isoformat()

        with freeze_time(behind_time), pytest.raises(ClockDriftError) as exc_info:
            wrapper.get_server_time()

        assert exc_info.value.drift_ms == -2000

    def test_raises_clock_drift_error_when_local_clock_is_ahead(self, wrapper, mock_client):
        mock_client.get_server_time.return_value = {"serverTime": SERVER_TIME_MS}
        ahead_time = datetime.fromtimestamp((SERVER_TIME_MS + 2000) / 1000, tz=UTC).isoformat()

        with freeze_time(ahead_time), pytest.raises(ClockDriftError) as exc_info:
            wrapper.get_server_time()

        assert exc_info.value.drift_ms == 2000

    def test_respects_custom_drift_threshold(self, mock_client):
        mock_client.get_server_time.return_value = {"serverTime": SERVER_TIME_MS}
        slightly_ahead = datetime.fromtimestamp((SERVER_TIME_MS + 1500) / 1000, tz=UTC).isoformat()

        wrapper = BinanceWrapper(
            api_key="fake_key",
            api_secret="fake_secret",
            max_clock_drift_ms=2000,
        )

        with freeze_time(slightly_ahead):
            result = wrapper.get_server_time()

        assert isinstance(result, datetime)

    def test_clock_drift_error_message_contains_drift_value(self, wrapper, mock_client):
        mock_client.get_server_time.return_value = {"serverTime": SERVER_TIME_MS}
        ahead_time = datetime.fromtimestamp((SERVER_TIME_MS + 2000) / 1000, tz=UTC).isoformat()

        with freeze_time(ahead_time), pytest.raises(ClockDriftError) as exc_info:
            wrapper.get_server_time()

        assert "2000" in str(exc_info.value)


class TestCheckCredentials:
    def test_returns_api_credentials_instance(self, wrapper, mock_client):
        mock_client.get_account.return_value = MOCK_ACCOUNT_RESPONSE
        assert isinstance(wrapper.check_credentials(), ApiCredentials)

    def test_maps_permissions_correctly(self, wrapper, mock_client):
        mock_client.get_account.return_value = MOCK_ACCOUNT_RESPONSE
        result = wrapper.check_credentials()
        assert result.can_trade is True
        assert result.can_withdraw is False
        assert result.can_deposit is True

    def test_raises_permission_error_on_invalid_key(self, wrapper, mock_client):
        mock_client.get_account.side_effect = make_api_exception(401, -2014, "API-key format invalid.")
        with pytest.raises(PermissionError):
            wrapper.check_credentials()

    def test_raises_connection_error_on_request_failure(self, wrapper, mock_client):
        mock_client.get_account.side_effect = BinanceRequestException("timeout")
        with pytest.raises(ConnectionError):
            wrapper.check_credentials()


class TestGetExchangeInfo:
    def test_returns_exchange_info_instance(self, wrapper, mock_client):
        mock_client.get_exchange_info.return_value = MOCK_EXCHANGE_RESPONSE
        assert isinstance(wrapper.get_exchange_info(), ExchangeInfo)

    def test_maps_timezone_and_status_correctly(self, wrapper, mock_client):
        mock_client.get_exchange_info.return_value = MOCK_EXCHANGE_RESPONSE
        result = wrapper.get_exchange_info()
        assert result.timezone == "UTC"
        assert result.status == "TRADING"

    def test_returns_only_active_symbols(self, wrapper, mock_client):
        mock_client.get_exchange_info.return_value = MOCK_EXCHANGE_RESPONSE
        result = wrapper.get_exchange_info()
        assert "BTCUSDT" in result.symbols
        assert "ETHUSDT" in result.symbols
        assert "XYZUSDT" not in result.symbols
        assert "ABCUSDT" not in result.symbols

    def test_raises_connection_error_on_api_exception(self, wrapper, mock_client):
        mock_client.get_exchange_info.side_effect = make_api_exception(500, -1000, "Unknown error.")
        with pytest.raises(ConnectionError):
            wrapper.get_exchange_info()

    def test_raises_connection_error_on_request_exception(self, wrapper, mock_client):
        mock_client.get_exchange_info.side_effect = BinanceRequestException("timeout")
        with pytest.raises(ConnectionError):
            wrapper.get_exchange_info()