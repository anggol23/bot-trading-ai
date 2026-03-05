import asyncio
from config.settings import Config
from core.interfaces.database_port import IDatabase
from use_cases.analysis.volume_analyzer import VolumeAnalyzer
from use_cases.analysis.signal_generator import SignalGenerator
from core.entities.technical_signal import TechnicalSignal

class MockDB(IDatabase):
    def save_volume_anomaly(self, event): pass
    def get_volume_anomalies(self, symbol, since):
        return [
            {
                "anomaly_type": "trade_spike",
                "side": "buy",
                "amount": 1000,
                "price": 50000,
                "amount_usd": 50000 * 1000 / 16000, # 3125
                "timestamp": 123456789
            },
            {
                "anomaly_type": "orderbook_wall",
                "side": "buy",
                "amount": 5000,
                "price": 50000,
                "amount_usd": 50000 * 5000 / 16000, # 15625
                "timestamp": 123456789
            }
        ]
    def execute_query(self, query, params=None): pass
    def fetch_all(self, query, params=None): pass
    def fetch_one(self, query, params=None): pass
    def execute_script(self, script): pass
    def close_trade(self, *args, **kwargs): pass
    def get_candles(self, *args, **kwargs): pass
    def get_latest_portfolio_snapshot(self, *args, **kwargs): pass
    def get_open_trades(self, *args, **kwargs): pass
    def get_recent_signals(self, *args, **kwargs): pass
    def get_trades_today(self, *args, **kwargs): pass
    def save_candles(self, *args, **kwargs): pass
    def save_portfolio_snapshot(self, *args, **kwargs): pass
    def save_signal(self, *args, **kwargs): pass
    def save_trade(self, *args, **kwargs): pass

def run_test():
    config = Config()
    config.volume_anomaly.min_usd_value = 1000 # Lower for test
    db = MockDB()
    analyzer = VolumeAnalyzer(config, db)
    
    vol_signal = analyzer.analyze("BTC/IDR")
    
    tech_signal = TechnicalSignal(
        symbol="BTC/IDR",
        trend="BULLISH",
        momentum="STRONG",
        confidence=0.8,
        rsi=60.0,
        timeframe="15m",
        volatility=0.01
    )
    
    generator = SignalGenerator()
    final_signal = generator.generate(tech_signal, vol_signal)
    
    print("\n--- TEST RESULT ---")
    print(f"Action: {final_signal.action}")
    print(f"Confidence: {final_signal.confidence}")
    print(f"Reason: {final_signal.reason}")
    print("-------------------\n")

if __name__ == "__main__":
    run_test()
