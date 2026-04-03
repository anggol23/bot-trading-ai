import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.settings import Config
from use_cases.trading.risk_manager import RiskManager
from core.interfaces.database_port import IDatabase

class MockDB(IDatabase):
    def __init__(self, mock_loss: float):
        self._mock_loss = mock_loss

    def get_open_trades(self):
        return []

    def get_trades_today(self):
        # Mengembalikan mock trades dari hari ini
        return [
            {"pnl": self._mock_loss} if self._mock_loss < 0 else {},
        ]
    
    # Required dummy methods
    def save_trade(self, trade): pass
    def update_trade(self, trade): pass
    def get_trade(self, symbol, status): pass
    def save_signal(self, payload): pass
    def save_volume_anomaly(self, anomaly): pass
    def get_recent_anomalies(self, limit): pass
    def update_portfolio_snapshot(self, equity, balance, unrealized): pass
    def close_trade(self, *args, **kwargs): pass
    def get_candles(self, *args, **kwargs): pass
    def get_latest_portfolio_snapshot(self, *args, **kwargs): pass
    def get_recent_signals(self, *args, **kwargs): pass
    def get_volume_anomalies(self, *args, **kwargs): pass
    def save_candles(self, *args, **kwargs): pass
    def save_portfolio_snapshot(self, *args, **kwargs): pass

def test_scenario():
    print("--- MENGUJI LOGIKA MANAJEMEN RISIKO (HUKUMAN & LOSS STREAK) ---")
    config = Config()
    config.risk.stop_loss_atr_multiplier = 2.0
    config.risk.punishment_drawdown_pct = 0.02
    config.risk.risk_per_trade = 0.05
    config.risk.max_consecutive_losses = 2
    
    symbol = "BTC/IDR"
    side = "buy"
    entry_price = 1_000_000
    atr = 50_000
    equity = 100_000_000
    
    print(f"Modal: Rp {equity:,.0f} | Harga: Rp {entry_price:,.0f} | ATR: Rp {atr:,.0f}")
    
    # Skenario 1: Normal (Belum Target, Belum Kena Hukuman Drawdown)
    print("\n[Skenario 1] Normal: Belum mencapai Daily Target, dan tidak ada loss hari ini")
    db_normal = MockDB(mock_loss=0)
    risk_mngr = RiskManager(config, db_normal)
    plan_1 = risk_mngr.calculate_order(symbol, side, entry_price, atr, equity, daily_target_met=False)
    
    # Skenario 2: Hukuman Drawdown (Sudah Loss > 2%)
    print("\n[Skenario 2] Hukuman Aktif: Loss hari ini sudah 2.5%")
    # PNL = -2,500,000 (2.5% of 100,000,000)
    db_punished = MockDB(mock_loss=-2_500_000)
    risk_mngr2 = RiskManager(config, db_punished)
    plan_2 = risk_mngr2.calculate_order(symbol, side, entry_price, atr, equity, daily_target_met=False)

    print("\n--- HASIL ---")
    print(f"[Normal]    Size: {plan_1.position_size:.8f} | Risk %: {plan_1.risk_percent}% | SL Multiplier Jarak: Rp {entry_price - plan_1.stop_loss:,.0f} | Cost: Rp {plan_1.cost:,.0f}")
    print(f"[Punished]  Size: {plan_2.position_size:.8f} | Risk %: {plan_2.risk_percent}% | SL Multiplier Jarak: Rp {entry_price - plan_2.stop_loss:,.0f} | Cost: Rp {plan_2.cost:,.0f}")

    expected_punished_risk_pct = config.risk.risk_per_trade * 100 * 0.5 * 0.75
    assert round(plan_1.risk_percent, 2) == 5.0, "Risk normal tidak sesuai base risk yang diharapkan"
    assert round(plan_2.risk_percent, 2) == round(expected_punished_risk_pct, 2), "Penalty drawdown + loss streak tidak bekerja sesuai desain"
    assert (entry_price - plan_1.stop_loss) == atr * 2.0, "Stop loss normal harus mengikuti ATR multiplier tanpa pelebaran paksa"

    print("\n✅ PENGUJIAN BERHASIL: AI kini menurunkan risk saat drawdown dan loss streak tanpa memperlebar stop loss secara agresif.")

if __name__ == "__main__":
    test_scenario()
