import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import numpy as np
from .base_agent import BaseAgent
from models import PriceHistory
from app import app

logger = logging.getLogger(__name__)

class PricePredictionAgent(BaseAgent):
    def __init__(self):
        super().__init__("PricePrediction")
        self.min_history_points = 6  # Minimum data points needed for prediction
        self.provider = "ComEd"  # Default provider

    async def process(self, message: Dict[str, Any]) -> Dict[str, Any]:
        if message.get("command") == "predict_prices":
            try:
                # Get historical data from database using Flask application context
                with app.app_context():
                    historical_records = PriceHistory.get_recent_history(hours=24, provider=self.provider)
                    feedback_records = PriceHistory.get_recent_predictions_with_accuracy(provider=self.provider)

                if not historical_records or len(historical_records) < self.min_history_points:
                    logger.warning(f"Limited historical data. Using basic prediction with {len(historical_records) if historical_records else 0} points.")
                    return {
                        "status": "success",
                        "predictions": self.get_limited_prediction(historical_records)
                    }

                predictions = self.predict_future_prices(historical_records, feedback_records)

                # Store prediction in database
                with app.app_context():
                    if historical_records:
                        current_price = historical_records[0].hourly_price
                        PriceHistory.add_price_data(
                            hourly_price=current_price,
                            predicted_price=predictions["short_term_prediction"],
                            prediction_confidence=predictions["confidence"],
                            provider=self.provider
                        )

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

    def predict_future_prices(self, historical_records: List[PriceHistory], feedback_records: List[PriceHistory]) -> Dict[str, Any]:
        """Predict future prices using historical data and feedback from database"""
        # Extract price data
        prices = [record.hourly_price for record in historical_records if record.hourly_price is not None]

        if not prices:
            return self.get_limited_prediction([])

        # Calculate moving averages with feedback adjustment
        prediction_weights = self.calculate_prediction_weights(feedback_records)
        weighted_ma = self._calculate_weighted_moving_average(prices, prediction_weights)

        # Calculate trend and momentum
        trend = self._determine_trend(prices, weighted_ma)
        momentum = self._calculate_momentum(prices)

        # Calculate base prediction
        base_prediction = weighted_ma * (1 + momentum)

        # Adjust prediction based on feedback accuracy
        avg_accuracy = float(np.mean([record.prediction_accuracy for record in feedback_records])) if feedback_records else 0.7
        confidence_factor = min(avg_accuracy * 1.2, 1.0)  # Scale up accuracy but cap at 1.0

        # Calculate final prediction and confidence
        final_prediction = float(base_prediction * (1 + (momentum * confidence_factor)))  # Convert to float
        confidence = float(self._calculate_confidence(prices, feedback_records))  # Convert to float

        return {
            "short_term_prediction": round(final_prediction, 2),
            "confidence": round(confidence, 1),
            "trend": trend,
            "feedback_quality": round(float(avg_accuracy * 100), 1) if feedback_records else None
        }

    def calculate_prediction_weights(self, feedback_records: List[PriceHistory]) -> Dict[str, float]:
        """Calculate prediction weights based on historical accuracy"""
        if not feedback_records:
            return {"trend": 0.4, "momentum": 0.3, "historical": 0.3}

        accuracies = [record.prediction_accuracy for record in feedback_records if record.prediction_accuracy is not None]
        if not accuracies:
            return {"trend": 0.4, "momentum": 0.3, "historical": 0.3}

        avg_accuracy = np.mean(accuracies)

        # Adjust weights based on historical accuracy
        if avg_accuracy > 0.8:
            return {"trend": 0.5, "momentum": 0.3, "historical": 0.2}
        elif avg_accuracy > 0.6:
            return {"trend": 0.4, "momentum": 0.3, "historical": 0.3}
        else:
            return {"trend": 0.3, "momentum": 0.3, "historical": 0.4}

    def _calculate_weighted_moving_average(self, prices: List[float], weights: Dict[str, float]) -> float:
        """Calculate weighted moving average based on feedback-adjusted weights"""
        if not prices:
            return 0.0

        window_size = min(len(prices), 12)  # Use up to 12 hours of data
        recent_prices = prices[:window_size]

        # Apply exponential weights that sum to 1
        exp_weights = np.exp(-np.arange(len(recent_prices)) * weights["historical"])
        exp_weights = exp_weights / exp_weights.sum()

        return np.average(recent_prices, weights=exp_weights)

    def _calculate_momentum(self, prices: List[float]) -> float:
        """Calculate price momentum"""
        if len(prices) < 2:
            return 0.0

        recent_changes = np.diff(prices[:12] if len(prices) >= 12 else prices)
        return np.mean(recent_changes) / prices[0] if prices[0] != 0 else 0.0

    def _determine_trend(self, prices: List[float], weighted_ma: float) -> str:
        """Determine price trend using weighted moving average"""
        if not prices:
            return "unknown"

        current_price = prices[0]
        return "rising" if current_price > weighted_ma else "falling" if current_price < weighted_ma else "stable"

    def _calculate_confidence(self, prices: List[float], feedback_records: List[PriceHistory]) -> float:
        """Calculate prediction confidence based on historical accuracy and current market conditions"""
        if not prices or not feedback_records:
            return 50.0  # Base confidence

        # Calculate volatility
        volatility = np.std(prices) / np.mean(prices) if np.mean(prices) != 0 else 0.1

        # Get average historical accuracy
        accuracies = [record.prediction_accuracy for record in feedback_records if record.prediction_accuracy is not None]
        avg_accuracy = np.mean(accuracies) if accuracies else 0.7

        # Base confidence starts at 50
        confidence = 50.0

        # Adjust based on number of data points (up to +20)
        confidence += min(len(prices), 20)

        # Adjust based on historical accuracy (up to +20)
        confidence += avg_accuracy * 20

        # Penalize for volatility (up to -20)
        confidence -= min(volatility * 100, 20)

        return min(max(confidence, 0), 100)  # Ensure confidence is between 0 and 100

    def get_limited_prediction(self, historical_records: List[PriceHistory]) -> Dict[str, Any]:
        """Generate a basic prediction with limited data"""
        if not historical_records:
            return {
                "short_term_prediction": None,
                "confidence": 0,
                "trend": "unknown",
                "feedback_quality": None
            }

        prices = [record.hourly_price for record in historical_records if record.hourly_price is not None]

        if not prices:
            return {
                "short_term_prediction": None,
                "confidence": 0,
                "trend": "unknown",
                "feedback_quality": None
            }

        current_price = prices[0]
        avg_price = np.mean(prices)
        trend = "rising" if current_price > avg_price else "falling" if current_price < avg_price else "stable"

        return {
            "short_term_prediction": round(current_price * (1.02 if trend == "rising" else 0.98 if trend == "falling" else 1.0), 2),
            "confidence": 30.0,  # Low confidence due to limited data
            "trend": trend,
            "feedback_quality": None
        }