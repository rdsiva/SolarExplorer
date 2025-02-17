from typing import Dict, Any, Optional
import logging
import numpy as np
from datetime import datetime, timedelta
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
from .base_module import BaseModule

logger = logging.getLogger(__name__)

class MLPredictionModule(BaseModule):
    """Module for ML-based price predictions and warnings"""

    def __init__(self):
        super().__init__(
            name="ml_prediction",
            description="Provides ML-based price predictions and warnings"
        )
        self.model = RandomForestRegressor(n_estimators=100, random_state=42)
        self.scaler = StandardScaler()
        self.price_history = []
        self.prediction_history = []
        self.is_model_trained = False

    async def initialize(self) -> bool:
        """Initialize the ML prediction module"""
        try:
            logger.info("Initializing ML prediction module")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize ML prediction module: {str(e)}")
            return False

    def _prepare_features(self, prices: list) -> np.ndarray:
        """Prepare feature matrix for prediction"""
        if len(prices) < 24:
            return np.array([])

        features = []
        for i in range(len(prices) - 24):
            window = prices[i:i+24]
            features.append([
                np.mean(window),
                np.std(window),
                np.min(window),
                np.max(window),
                window[-1],  # Last price
                window[-1] - window[0],  # Price change
                np.mean(window[-6:]),  # Short-term average
                np.mean(window)  # Long-term average
            ])
        return np.array(features)

    def _prepare_targets(self, prices: list) -> np.ndarray:
        """Prepare target values for training"""
        if len(prices) < 25:
            return np.array([])

        targets = []
        for i in range(len(prices) - 24):
            targets.append(prices[i+24])  # Next hour's price
        return np.array(targets)

    def _update_model(self):
        """Update the model with recent price data"""
        if len(self.price_history) < 48:  # Need at least 48 hours of data
            return

        try:
            prices = [p['price'] for p in self.price_history]
            X = self._prepare_features(prices)
            y = self._prepare_targets(prices)

            if len(X) == 0 or len(y) == 0:
                return

            # Scale features
            X_scaled = self.scaler.fit_transform(X)

            # Train model
            self.model.fit(X_scaled, y)
            self.is_model_trained = True

        except Exception as e:
            logger.error(f"Error updating model: {str(e)}")

    def _calculate_prediction_confidence(self, prediction: float, actual: float) -> float:
        """Calculate confidence score based on prediction accuracy"""
        if actual == 0:
            return 0.0

        error = abs(prediction - actual) / actual
        confidence = max(0, 100 * (1 - error))
        return round(confidence, 1)

    async def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process current price data and make predictions"""
        try:
            current_price = data.get('current_price', 0)
            timestamp = data.get('timestamp', datetime.now())

            # Add to price history
            self.price_history.append({
                'price': current_price,
                'timestamp': timestamp
            })

            # Clean old data (keep last 7 days)
            cutoff = datetime.now() - timedelta(days=7)
            self.price_history = [
                point for point in self.price_history 
                if point['timestamp'] > cutoff
            ]

            # Update model if needed
            self._update_model()

            # If we don't have enough data yet, return a waiting status
            if len(self.price_history) < 48:
                prediction_data = {
                    "short_term_prediction": current_price,
                    "confidence": 50.0,
                    "trend": "stable",
                    "next_hour_range": {
                        "low": current_price * 0.95,
                        "high": current_price * 1.05
                    },
                    "warning_level": "normal"
                }

                # Store prediction for notification data
                self.prediction_history.append({
                    'timestamp': timestamp,
                    'prediction': current_price,
                    'confidence': 50.0
                })

                return {
                    "status": "success",
                    "message": "Collecting data for initial training",
                    "predictions": prediction_data
                }

            # Prepare current data for prediction
            prices = [p['price'] for p in self.price_history[-24:]]
            X = self._prepare_features([prices[-24:]])

            if len(X) == 0:
                prediction_data = {
                    "short_term_prediction": current_price,
                    "confidence": 50.0,
                    "trend": "stable",
                    "next_hour_range": {
                        "low": current_price * 0.95,
                        "high": current_price * 1.05
                    },
                    "warning_level": "normal"
                }

                # Store prediction for notification data
                self.prediction_history.append({
                    'timestamp': timestamp,
                    'prediction': current_price,
                    'confidence': 50.0
                })

                return {
                    "status": "success",
                    "message": "Insufficient recent data for prediction",
                    "predictions": prediction_data
                }

            # Scale and predict
            X_scaled = self.scaler.transform(X)
            prediction = self.model.predict(X_scaled)[-1]

            # Calculate confidence
            confidence = 70.0  # Base confidence
            if len(self.prediction_history) > 0:
                last_prediction = self.prediction_history[-1]
                if 'actual' in last_prediction:
                    accuracy = self._calculate_prediction_confidence(
                        last_prediction['prediction'],
                        last_prediction['actual']
                    )
                    confidence = accuracy

            # Determine trend
            trend = "stable"
            if prediction > current_price * 1.05:
                trend = "rising"
            elif prediction < current_price * 0.95:
                trend = "falling"

            # Store prediction
            self.prediction_history.append({
                'timestamp': timestamp,
                'prediction': prediction,
                'confidence': confidence
            })

            prediction_data = {
                "short_term_prediction": round(float(prediction), 2),
                "confidence": confidence,
                "trend": trend,
                "next_hour_range": {
                    "low": round(prediction * 0.9, 2),
                    "high": round(prediction * 1.1, 2)
                },
                "warning_level": "high" if abs(prediction - current_price) > current_price * 0.2 else "normal"
            }

            return {
                "status": "success",
                "predictions": prediction_data
            }

        except Exception as e:
            logger.error(f"Error in ML prediction: {str(e)}")
            return {
                "status": "error",
                "message": str(e)
            }

    async def get_notification_data(self) -> Optional[Dict[str, Any]]:
        """Get prediction data for notifications"""
        try:
            # Always provide prediction data, even during training phase
            if not self.prediction_history:
                # If no predictions yet, return None
                return None

            latest = self.prediction_history[-1]
            return {
                "predicted_price": round(latest['prediction'], 2),
                "confidence": latest['confidence'],
                "timestamp": latest['timestamp']
            }
        except Exception as e:
            logger.error(f"Error getting notification data: {str(e)}")
            return None