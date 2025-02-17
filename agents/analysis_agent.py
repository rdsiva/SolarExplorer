import logging
from typing import Dict, Any, List
from .base_agent import BaseAgent

logger = logging.getLogger(__name__)

class AnalysisAgent(BaseAgent):
    def __init__(self):
        super().__init__("Analysis")
        self.price_history: List[Dict[str, Any]] = []

    async def process(self, message: Dict[str, Any]) -> Dict[str, Any]:
        if message.get("command") == "analyze_prices":
            price_data = message.get("price_data")
            if not price_data:
                return {
                    "status": "error",
                    "message": "No price data provided"
                }

            try:
                analysis_result = self.analyze_price_trends(price_data)
                return {
                    "status": "success",
                    "analysis": analysis_result
                }
            except Exception as e:
                logger.error(f"Error analyzing price data: {str(e)}")
                return {
                    "status": "error",
                    "message": f"Failed to analyze price data: {str(e)}"
                }
        return {
            "status": "error",
            "message": "Unknown command"
        }

    def analyze_price_trends(self, price_data: Dict[str, Any]) -> Dict[str, Any]:
        # Add to price history
        self.price_history.append(price_data)
        if len(self.price_history) > 288:  # Keep 24 hours of 5-min data
            self.price_history.pop(0)

        # Calculate basic statistics from five_min_data
        five_min_prices = [
            float(data.get('five_min_data', {}).get('price', 0)) 
            for data in self.price_history
        ]

        if not five_min_prices:
            return {
                "current_price": 0,
                "average_price": 0,
                "min_price": 0,
                "max_price": 0,
                "price_trend": "unknown"
            }

        return {
            "current_price": five_min_prices[-1],
            "average_price": sum(five_min_prices) / len(five_min_prices),
            "min_price": min(five_min_prices),
            "max_price": max(five_min_prices),
            "price_trend": "rising" if len(five_min_prices) > 1 and five_min_prices[-1] > five_min_prices[-2] else "falling"
        }