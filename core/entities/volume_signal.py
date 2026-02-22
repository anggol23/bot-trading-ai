from dataclasses import dataclass


@dataclass
class VolumeSignal:
    """Result of volume anomaly analysis."""
    symbol: str
    net_flow: str         # ACCUMULATING, DISTRIBUTING, NEUTRAL
    intensity: str        # HIGH, MEDIUM, LOW
    imbalance_score: float # -1.0 to +1.0 (negative = sell bias, positive = buy bias)
    confidence: float     # 0.0 - 1.0

    def to_dict(self):
        return {
            "symbol": self.symbol,
            "net_flow": self.net_flow,
            "intensity": self.intensity,
            "imbalance_score": self.imbalance_score,
            "confidence": self.confidence,
        }
