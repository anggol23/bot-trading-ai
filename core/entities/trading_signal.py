from dataclasses import dataclass
from typing import Dict, Any, Optional

from core.entities.technical_signal import TechnicalSignal
from core.entities.volume_signal import VolumeSignal


@dataclass
class TradingSignal:
    """Final combined trading signal based on multi-factor analysis."""
    symbol: str
    action: str              # STRONG_BUY, BUY, HOLD, SELL, STRONG_SELL
    confidence: float        # 0.0 - 1.0
    reason: str              # Human-readable explanation

    # Component signals
    technical: Optional[TechnicalSignal] = None
    volume: Optional[VolumeSignal] = None

    # Multi-timeframe confirmation
    timeframes_aligned: int = 0
    total_timeframes: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "action": self.action,
            "confidence": self.confidence,
            "reason": self.reason,
            "technical_trend": self.technical.trend if self.technical else None,
            "technical_momentum": self.technical.momentum if self.technical else None,
            "technical_confidence": self.technical.confidence if self.technical else None,
            "volume_flow": self.volume.net_flow if self.volume else None,
            "volume_intensity": self.volume.intensity if self.volume else None,
            "volume_confidence": self.volume.confidence if self.volume else None,
            "combined_action": self.action,
            "combined_confidence": self.confidence,
            "timeframes_aligned": self.timeframes_aligned,
        }
