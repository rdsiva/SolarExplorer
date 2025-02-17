import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import numpy as np
from .base_agent import BaseAgent

logger = logging.getLogger(__name__)

class PricePredictionAgent(BaseAgent):
    def __init__(self):
        super().__init__("PricePrediction")
        self.prediction_window = 12  # Predict next 1 hour (12 * 5 minutes)
        self.min_history_points = 6  # Minimum data points needed for prediction (30 minutes)

    async def process(self, message: Dict[str, Any]) -> Dict[str, Any]:
        if message.get("command") == "predict_prices":
            price_history = message.get("price_history", [])
            if not price_history or len(price_history) < self.min_history_points:
                logger.warning(f"Limited historical data. Using basic prediction with {len(price_history)} points.")
                return {
                    "status": "success",
                    "predictions": self.get_limited_prediction(price_history)
                }

            try:
                predictions = self.predict_future_prices(price_history)
                return {
                    "status": "success",
                    "predictions": predictions
                }
            except Exception as e:
                logger.error(f"Error predicting prices: {str(e)}")
                return {
                    "status": "error",
                    "message": f"Failed to predict prices: {str(e)}"
                }
        return {
            "status": "error",
            "message": "Unknown command"
        }

    def get_limited_prediction(self, price_history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate a basic prediction with limited data"""
        if not price_history:
            return {
                "short_term_prediction": None,
                "confidence": 0,
                "trend": "unknown",
                "next_hour_range": {"low": None, "high": None}
            }

        # Extract recent prices
        prices = [
            float(data.get('five_min_data', {}).get('price', 0))
            for data in price_history
            if data.get('five_min_data', {}).get('price') is not None
        ]

        if not prices:
            return {
                "short_term_prediction": None,
                "confidence": 0,
                "trend": "unknown",
                "next_hour_range": {"low": None, "high": None}
            }

        # Use simple moving average for trend
        current_price = prices[-1]
        avg_price = sum(prices) / len(prices)
        trend = "rising" if current_price > avg_price else "falling" if current_price < avg_price else "stable"

        # Basic volatility calculation
        volatility = np.std(prices) if len(prices) > 1 else 0.1
        base_confidence = 30  # Base confidence for limited data

        # Adjust confidence based on number of data points and volatility
        confidence = min(base_confidence + (len(prices) * 5), 70)  # Max 70% confidence with limited data
        confidence *= max(0.5, 1 - (volatility / 2))  # Reduce confidence with high volatility

        return {
            "short_term_prediction": round(current_price * (1.02 if trend == "rising" else 0.98 if trend == "falling" else 1.0), 2),
            "confidence": round(min(confidence, 100), 1),
            "trend": trend,
            "next_hour_range": {
                "low": round(current_price * (1 - volatility), 2),
                "high": round(current_price * (1 + volatility), 2)
            }
        }

    def predict_future_prices(self, price_history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Predict future prices using historical data"""
        # Extract price data
        prices = [
            float(data.get('five_min_data', {}).get('price', 0))
            for data in price_history
            if data.get('five_min_data', {}).get('price') is not None
        ]

        if not prices:
            return self.get_limited_prediction([])

        # Calculate moving averages
        short_ma = self._calculate_moving_average(prices, min(6, len(prices)))   # 30-min MA
        long_ma = self._calculate_moving_average(prices, min(12, len(prices)))   # 1-hour MA

        # Calculate momentum and trend
        momentum = (short_ma - long_ma) if (short_ma is not None and long_ma is not None) else 0
        trend = self._determine_trend(momentum)

        # Calculate weighted prediction
        weights = np.array([0.5, 0.3, 0.2])  # Adjusted weights for recent prices
        recent_prices = prices[-3:] if len(prices) >= 3 else prices

        if len(recent_prices) >= 3:
            prediction = np.average(recent_prices, weights=weights[-len(recent_prices):])
        else:
            prediction = np.mean(recent_prices)

        # Adjust prediction based on trend
        trend_factor = 1.05 if trend == "rising" else 0.95 if trend == "falling" else 1.0
        prediction *= trend_factor

        # Calculate prediction confidence
        volatility = np.std(prices[-12:] if len(prices) >= 12 else prices)
        max_expected_volatility = 2.0  # Maximum expected price volatility
        base_confidence = 50 + (min(len(prices), 24) * 2)  # Higher base confidence with more data
        confidence = base_confidence * (1 - volatility/max_expected_volatility)

        # Calculate price range based on volatility and trend
        range_factor = max(0.02, min(volatility, 0.1))  # 2-10% range based on volatility

        return {
            "short_term_prediction": round(prediction, 2),
            "confidence": round(min(confidence, 100), 1),
            "trend": trend,
            "next_hour_range": {
                "low": round(prediction * (1 - range_factor), 2),
                "high": round(prediction * (1 + range_factor), 2)
            }
        }

    def _calculate_moving_average(self, prices: List[float], window: int) -> Optional[float]:
        """Calculate moving average for the given window size"""
        if len(prices) < window:
            return None
        return sum(prices[-window:]) / window

    def _determine_trend(self, momentum: float) -> str:
        """Determine price trend based on momentum"""
        if momentum > 0.1:
            return "rising"
        elif momentum < -0.1:
            return "falling"
        return "stable"