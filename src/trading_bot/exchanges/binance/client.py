from dataclasses import dataclass
from datetime import UTC, datetime

from binance.client import Client
from binance.exceptions import BinanceAPIException, BinanceRequestException


class ClockDriftError(Exception):
    def __init__(self, drift_ms: int):
        self.drift_ms = drift_ms
        direction = "adiantado" if drift_ms > 0 else "atrasado"
        super().__init__(
            f"Clock local está {direction} em {abs(drift_ms)}ms em relação ao servidor Binance. "
            f"Sincronize o relógio do sistema antes de continuar."
        )


@dataclass
class ApiCredentials:
    can_trade: bool
    can_withdraw: bool
    can_deposit: bool


@dataclass
class ExchangeInfo:
    timezone: str
    status: str
    symbols: list[str]


class BinanceWrapper:
    DEFAULT_MAX_CLOCK_DRIFT_MS = 1000

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        testnet: bool = False,
        max_clock_drift_ms: int = DEFAULT_MAX_CLOCK_DRIFT_MS,
    ):
        self._client = Client(api_key, api_secret, testnet=testnet)
        self._max_clock_drift_ms = max_clock_drift_ms

    def ping(self) -> bool:
        try:
            self._client.ping()
            return True
        except (BinanceAPIException, BinanceRequestException):
            return False

    def get_server_time(self) -> datetime:
        try:
            response = self._client.get_server_time()
            timestamp_ms = response["serverTime"]
            server_time = datetime.fromtimestamp(timestamp_ms / 1000, tz=UTC)

            local_time = datetime.now(tz=UTC)
            drift_ms = int((local_time - server_time).total_seconds() * 1000)

            if abs(drift_ms) > self._max_clock_drift_ms:
                raise ClockDriftError(drift_ms)

            return server_time
        except ClockDriftError:
            raise
        except (BinanceAPIException, BinanceRequestException) as e:
            raise ConnectionError(f"Failed to retrieve server time: {e}") from e

    def check_credentials(self) -> ApiCredentials:
        try:
            response = self._client.get_account()
            return ApiCredentials(
                can_trade=response["canTrade"],
                can_withdraw=response["canWithdraw"],
                can_deposit=response["canDeposit"],
            )
        except BinanceAPIException as e:
            raise PermissionError(f"Invalid or unauthorized API credentials: {e}") from e
        except BinanceRequestException as e:
            raise ConnectionError(f"Failed to reach Binance API: {e}") from e

    def get_exchange_info(self) -> ExchangeInfo:
        try:
            response = self._client.get_exchange_info()
            active_symbols = [
                s["symbol"] for s in response["symbols"]
                if s["status"] == "TRADING"
            ]
            status = "TRADING" if active_symbols else "UNAVAILABLE"
            return ExchangeInfo(
                timezone=response["timezone"],
                status=status,
                symbols=active_symbols,
            )
        except (BinanceAPIException, BinanceRequestException) as e:
            raise ConnectionError(f"Failed to retrieve exchange info: {e}") from e