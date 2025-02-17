import logging
from typing import Dict, Any, List, Tuple
from datetime import datetime, timedelta
from .base_agent import BaseAgent

logger = logging.getLogger(__name__)

class AnalysisAgent(BaseAgent):
    def __init__(self):
        super().__init__("Analysis")
        self.price_history: List[Dict[str, Any]] = []
        self.max_history_size = 288  # Store 24 hours of 5-min data

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

        # Keep only last 24 hours of data
        if len(self.price_history) > self.max_history_size:
            self.price_history.pop(0)

        # Extract prices from both 5-min and hourly data
        five_min_prices = [
            float(data.get('five_min_data', {}).get('price', 0)) 
            for data in self.price_history
            if data.get('five_min_data', {}).get('price') is not None
        ]

        hourly_prices = [
            float(data.get('hourly_data', {}).get('price', 0))
            for data in self.price_history
            if data.get('hourly_data', {}).get('price') is not None
        ]

        # Combine prices for overall analysis
        all_prices = five_min_prices + hourly_prices

        if not all_prices:
            return {
                "current_price": 0,
                "average_price": 0,
                "min_price": 0,
                "max_price": 0,
                "price_trend": "unknown"
            }

        # Calculate current price (prefer 5-min price if available)
        current_price = (
            float(price_data.get('five_min_data', {}).get('price', 0)) or
            float(price_data.get('hourly_data', {}).get('price', 0))
        )

        # Calculate price trend
        if len(five_min_prices) >= 2:
            previous_price = five_min_prices[-2] if len(five_min_prices) > 1 else five_min_prices[0]
            trend = "rising" if current_price > previous_price else "falling" if current_price < previous_price else "stable"
        else:
            trend = "unknown"

        # Calculate statistics
        avg_price = sum(all_prices) / len(all_prices)
        min_price = min(all_prices)
        max_price = max(all_prices)

        return {
            "current_price": current_price,
            "average_price": avg_price,
            "min_price": min_price,
            "max_price": max_price,
            "price_trend": trend,
            "price_volatility": max_price - min_price,
            "data_points": len(all_prices)
        }