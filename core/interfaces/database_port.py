from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional


class IDatabase(ABC):
    """Port for all database operations."""

    @abstractmethod
    def save_candles(self, symbol: str, timeframe: str, candles: List[List]):
        pass

    @abstractmethod
    def get_candles(self, symbol: str, timeframe: str, limit: int = 200) -> List[Dict]:
        pass

    @abstractmethod
    def save_volume_anomaly(self, event: Dict[str, Any]):
        pass

    @abstractmethod
    def get_volume_anomalies(self, symbol: str, since_timestamp: int) -> List[Dict]:
        pass

    @abstractmethod
    def save_signal(self, signal_dict: Dict[str, Any]) -> int:
        pass

    @abstractmethod
    def get_recent_signals(self, limit: int = 10) -> List[Dict]:
        pass

    @abstractmethod
    def save_trade(self, trade: Dict[str, Any]) -> int:
        pass

    @abstractmethod
    def close_trade(self, trade_id: int, close_price: float, reason: str):
        pass

    @abstractmethod
    def get_open_trades(self) -> List[Dict]:
        pass

    @abstractmethod
    def get_trades_today(self) -> List[Dict]:
        pass

    @abstractmethod
    def save_portfolio_snapshot(self, snapshot: Dict[str, Any]):
        pass

    @abstractmethod
    def get_latest_portfolio_snapshot(self) -> Optional[Dict]:
        pass
