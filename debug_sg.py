import sys
import os
from pprint import pprint

sys.path.append("/home/razdan/Documents/PROJECT LIAR/AI TRADING")

from use_cases.analysis.signal_generator import SignalGenerator
from core.entities.technical_signal import TechnicalSignal
from core.entities.volume_signal import VolumeSignal

tech_signal = TechnicalSignal(
    symbol="ETH/IDR",
    timeframe="1h",
    trend="BEARISH",
    momentum="STRONG",
    volatility="NORMAL",
    confidence=1.0,
    rsi=34.4,
    macd_histogram=-343054.40,
)

volume_signal = VolumeSignal(
    symbol="ETH/IDR",
    net_flow="NEUTRAL",
    intensity="HIGH",
    imbalance_score=-0.25,
    confidence=0.55
)

sg = SignalGenerator()

print("volume_signal is None?", volume_signal is None)
print("generate() with volume:")
sig = sg.generate(tech_signal, volume_signal)
print(sig.to_dict())

print("generate() without volume:")
sig2 = sg.generate(tech_signal, None)
print(sig2.to_dict())
