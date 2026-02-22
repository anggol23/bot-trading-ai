"""
Sentiment Analyzer - Uses NLP to score crypto headlines and detect panic/euphoria.
"""

from typing import List, Dict, Optional, Any
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from config.settings import Config
from core.interfaces.news_port import INewsData
from utils.logger import get_logger

logger = get_logger(__name__)


class SentimentAnalyzer:
    """
    Analyzes crypto news headlines using VADER sentiment analysis.
    Produces a composite SentimentSignal used for trade vetoing.
    """

    def __init__(self, config: Config, news_provider: INewsData):
        self.config = config
        self.news_provider = news_provider
        self.analyzer = SentimentIntensityAnalyzer()
        
        # Add custom crypto vocabulary weightings to VADER
        # VADER is built for social media, so we tweak it for crypto context
        crypto_lexicon = {
            'hack': -3.5,
            'scam': -3.5,
            'bankrupt': -3.0,
            'sec': -1.5,
            'lawsuit': -2.0,
            'delisted': -3.0,
            'ban': -2.5,
            'bullish': 2.5,
            'moon': 2.0,
            'ath': 3.0,
            'partnership': 2.0,
            'listing': 2.5,
            'adoption': 2.0
        }
        self.analyzer.lexicon.update(crypto_lexicon)

    async def analyze_sentiment(self, symbol: str) -> Dict[str, Any]:
        """
        Fetch and analyze headlines for the given symbol.
        Returns a dictionary with sentiment classification.
        """
        # Fast exit if disabled
        if not self.config.risk.enable_sentiment_veto:
            return {"status": "DISABLED", "score": 0.0}
            
        try:
            headlines = await self.news_provider.fetch_recent_headlines(symbol, limit=15)
            
            if not headlines:
                return {"status": "NEUTRAL", "score": 0.0, "reason": "No recent news found."}

            compound_scores = []
            for h in headlines:
                scores = self.analyzer.polarity_scores(h)
                compound_scores.append(scores['compound'])

            # Calculate average sentiment across all recent headlines
            avg_score = sum(compound_scores) / len(compound_scores)
            
            # Classify the sentiment
            if avg_score <= -0.25: # Very negative threshold
                status = "NEGATIVE"
            elif avg_score >= 0.25:
                status = "POSITIVE"
            else:
                status = "NEUTRAL"
                
            logger.info(f"📰 {symbol} Sentiment: {status} (Score: {avg_score:.2f} based on {len(headlines)} headlines)")

            return {
                "status": status,
                "score": avg_score,
                "reason": f"Analyzed {len(headlines)} latest headlines."
            }

        except Exception as e:
            logger.error(f"❌ Sentiment analysis failed for {symbol}: {e}")
            return {"status": "NEUTRAL", "score": 0.0, "reason": "Fetch error."}
