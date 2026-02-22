"""
News Port - Interface for fetching crypto-related news.
"""

from typing import List, Dict, Any
from abc import ABC, abstractmethod


class INewsData(ABC):
    """Abstract interface for fetching cryptocurrency news."""

    @abstractmethod
    async def fetch_recent_headlines(self, symbol: str, limit: int = 20) -> List[str]:
        """
        Fetch the most recent news headlines for a specific trading pair.
        
        Args:
            symbol: Trading pair (e.g., 'BTC/IDR' or 'BTC')
            limit: Maximum number of headlines to fetch
            
        Returns:
            List of headline strings
        """
        pass
