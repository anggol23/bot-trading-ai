from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import pandas as pd


class IMarketData(ABC):
    """Port for fetching market data from an exchange."""

    @abstractmethod
    async def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int = 200) -> pd.DataFrame:
        pass

    @abstractmethod
    async def fetch_multi_timeframe(self, symbol: str, timeframes: List[str]) -> Dict[str, pd.DataFrame]:
        pass

    @abstractmethod
    async def fetch_ticker(self, symbol: str) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def fetch_order_book(self, symbol: str, limit: int = 20) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def fetch_trades(self, symbol: str, limit: int = 50) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    async def fetch_balance(self) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def get_available_pairs(self) -> List[str]:
        pass

    @abstractmethod
    async def validate_pairs(self, pairs: List[str]) -> List[str]:
        pass
