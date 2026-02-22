from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

from core.entities.order_plan import OrderPlan


class IExecutor(ABC):
    """Port for executing trades on an exchange."""

    @abstractmethod
    async def execute(self, plan: OrderPlan) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    async def close_position(self, trade: Dict[str, Any], current_price: float, reason: str) -> bool:
        pass
