"""
Volume & Imbalance Analyzer
Analyzes volume anomalies (large trades, orderbook walls) to determine 
smart money flow direction (Accumulation or Distribution).
"""

import time

from config.settings import Config
from core.interfaces.database_port import IDatabase
from core.entities.volume_signal import VolumeSignal
from utils.logger import get_logger

logger = get_logger(__name__)

class VolumeAnalyzer:
    """
    Analyzes historical and real-time volume anomalies from the database
    to determine the direction of smart money flow.
    """

    def __init__(self, config: Config, db: IDatabase):
        self.config = config
        self.db = db

    def analyze(self, symbol: str) -> VolumeSignal:
        """
        Analyze volume anomalies for a symbol to generate a direction signal.
        """
        # Look back 24 hours (86400000 ms)
        lookback_ms = int(time.time() * 1000) - (24 * 60 * 60 * 1000)
        anomalies = self.db.get_volume_anomalies(symbol, lookback_ms)
        
        if not anomalies:
            return VolumeSignal(symbol, "NEUTRAL", "LOW", 0.0, 0.0)

        # 0. Check for Spoofing Veto
        spoof_lookback = int(time.time() * 1000) - (self.config.volume_anomaly.spoofing_blacklist_seconds * 1000)
        recent_spoofs = [a for a in anomalies if a['anomaly_type'] == 'spoofing_trap' and a['timestamp'] >= spoof_lookback]
        
        if recent_spoofs:
            logger.warning(f"🚫 {symbol} is currently under SPOOFING BLACKLIST. Vetoing Volume Signal.")
            return VolumeSignal(symbol, "NEUTRAL", "LOW", 0.0, 0.0)

        # 1. Calculate Imbalance Score based on USD volume
        valid_anomalies = [a for a in anomalies if a['anomaly_type'] != 'spoofing_trap']
        buy_usd = sum(e["amount_usd"] for e in valid_anomalies if e["side"] == "buy")
        sell_usd = sum(e["amount_usd"] for e in valid_anomalies if e["side"] == "sell")
        
        total_usd = buy_usd + sell_usd
        
        if total_usd == 0:
            return VolumeSignal(symbol, "NEUTRAL", "LOW", 0.0, 0.0)
            
        # Imbalance Score: -1.0 to 1.0
        # Positive = Buyers dominating (huge buy trades or massive support walls)
        # Negative = Sellers dominating (huge sell trades or massive resistance walls)
        imbalance_score = (buy_usd - sell_usd) / total_usd
        
        # 2. Determine Net Flow
        if imbalance_score > 0.3:
            net_flow = "ACCUMULATING"
        elif imbalance_score < -0.3:
            net_flow = "DISTRIBUTING"
        else:
            net_flow = "NEUTRAL"
            
        # 3. Determine Intensity based on total anomaly volume
        # We define a "high" intensity if total anomaly volume is very 
        # significant vs the minimum threshold
        min_usd = self.config.volume_anomaly.min_usd_value
        if total_usd > min_usd * 10:
            intensity = "HIGH"
        elif total_usd > min_usd * 3:
            intensity = "MEDIUM"
        else:
            intensity = "LOW"
            
        # 4. Confidence Score
        # High volume + strong one-sided imbalance = high confidence
        safe_min_usd = max(min_usd, 1.0)
        volume_factor = min(1.0, total_usd / (safe_min_usd * 15))
        imbalance_factor = abs(imbalance_score)
        
        # Confidence is a blend of how much volume we saw and how one-sided it was
        confidence = (volume_factor * 0.4) + (imbalance_factor * 0.6)
        
        # Calculate Whale Score (1-10)
        whale_score = max(1, min(10, int(confidence * 10))) if total_usd > 0 else 0
        
        # Build Indonesian Whale Reason
        flow_text = "Tekanan Beli (Net Inflow)" if net_flow == "ACCUMULATING" else ("Tekanan Jual (Net Outflow)" if net_flow == "DISTRIBUTING" else "Netral")
        
        # Find dominant anomaly for description
        walls = [a for a in valid_anomalies if a['anomaly_type'] == 'orderbook_wall']
        trades = [a for a in valid_anomalies if a['anomaly_type'] == 'trade_spike']
        
        largest_wall = max(walls, key=lambda x: x['amount_usd']) if walls else None
        largest_trade = max(trades, key=lambda x: x['amount_usd']) if trades else None
        
        reason_parts = [f"Terdeteksi {flow_text}."]
        if largest_wall and largest_wall['amount_usd'] > min_usd * 2:
            w_side = "buy" if largest_wall['side'] == 'buy' else "sell"
            reason_parts.append(f"Terdapat {w_side} wall raksasa senilai ${largest_wall['amount_usd']:,.0f} di level Rp {largest_wall['price']:,.0f}.")
        if largest_trade and largest_trade['amount_usd'] > min_usd:
            t_side = "pembelian" if largest_trade['side'] == 'buy' else "penjualan"
            reason_parts.append(f"Terdapat lonjakan {t_side} >3x rata-rata senilai ${largest_trade['amount_usd']:,.0f}.")
            
        whale_reason = " ".join(reason_parts)
        
        signal = VolumeSignal(
            symbol=symbol,
            net_flow=net_flow,
            intensity=intensity,
            imbalance_score=round(imbalance_score, 3),
            confidence=round(confidence, 2),
            whale_score=whale_score,
            whale_reason=whale_reason
        )
        
        logger.info(
            f"📊 {symbol} Volume Anomaly → {net_flow} ({intensity}) | "
            f"Imbalance: {imbalance_score:+.2f} | Conf: {confidence:.0%} | Whale: {whale_score}/10"
        )
        
        return signal
