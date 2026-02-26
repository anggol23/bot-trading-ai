import json
import re
from typing import Dict, Any, Optional
from infrastructure.ai.llm_client import GeminiClient
from core.entities.trading_signal import TradingSignal
from utils.logger import get_logger

logger = get_logger(__name__)

class LLMStrategist:
    """Uses LLM to audit and validate trading signals."""
    
    def __init__(self, client: GeminiClient):
        self.client = client
        
    async def analyze_signal(
        self, 
        signal: TradingSignal, 
        market_stats: Dict[str, Any],
        recent_news: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send signal data to LLM and get a strategic decision.
        
        Returns:
            Dict containing 'decision' (APPROVE, REJECT, WAIT) and 'reasoning'.
        """
        prompt = self._build_prompt(signal, market_stats, recent_news)
        
        response = await self.client.generate_response(prompt)
        if not response:
            return {"decision": "APPROVE", "reasoning": "LLM validation skipped/failed."}
            
        return self._parse_llm_response(response)
        
    def _build_prompt(self, signal: TradingSignal, stats: Dict[str, Any], news: Optional[str]) -> str:
        # Construct a detailed prompt
        return f"""
Sebagai Lead Crypto Strategist, tugas Anda adalah memvalidasi sinyal trading berikut.

DATA SINYAL:
- Simbol: {signal.symbol}
- Aksi: {signal.action}
- Confidence Teknis: {signal.confidence * 100:.1f}%
- Alasan Teknis: {signal.reason}

DATA PASAR (Indikator):
{json.dumps(stats, indent=2)}

BERITA TERBARU:
{news if news else "Tidak ada berita fundamental terbaru yang tersedia."}

INSTRUKSI:
1. Analisis apakah sinyal teknis ini valid atau hanya "noise" pasar.
2. FILTRASI BIAYA (FEES): Indodax memiliki Taker Fee ~0.51% per transaksi. Total biaya beli-jual adalah ~1.1%. 
3. PROFIT HURDLE: Tolak (REJECT) setiap sinyal yang potensi profitnya (Take Profit) terlihat "tipis" atau di bawah 2% untuk memastikan net profit yang sehat setelah dipotong biaya.
4. ORDERBOOK GUARD: Perhatikan komposisi antrian (jika rasio Bids/Asks tersedia di Data Pasar). Hati-hati dengan tembok harga palsu (Spoofing).
5. Perhatikan korelasi antara trend teknis, anomali volume whale, dan sentimen berita.
6. Berikan keputusan akhir: APPROVE, REJECT, atau WAIT (menunggu konfirmasi).

FORMAT JAWABAN (WAJIB JSON):
{{
  "decision": "APPROVE" | "REJECT" | "WAIT",
  "reasoning": "Penjelasan singkat dalam Bahasa Indonesia mengapa Anda mengambil keputusan tersebut (Sebutkan faktor profit vs fees jika relevan)."
}}
"""

    def _parse_llm_response(self, text: str) -> Dict[str, Any]:
        try:
            # Try to find JSON in the text
            json_match = re.search(r'\{.*\}', text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(0))
            
            # Fallback if text is not clear JSON
            if "APPROVE" in text.upper(): return {"decision": "APPROVE", "reasoning": "LLM Approved (Parsed from text)."}
            if "REJECT" in text.upper(): return {"decision": "REJECT", "reasoning": "LLM Rejected (Parsed from text)."}
            return {"decision": "WAIT", "reasoning": "LLM suggested WAIT or response unclear."}
            
        except Exception as e:
            logger.error(f"❌ LLM Parsing error: {e}")
            return {"decision": "APPROVE", "reasoning": "Parsing error, defaulted to approve to avoid block."}
