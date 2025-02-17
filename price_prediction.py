import logging
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error
from app import app
from models import PriceHistory

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class PricePredictionModel:
    def __init__(self):
        self.model = RandomForestRegressor(
            n_estimators=100,
            random_state=42,
            n_jobs=-1
        )
        self.scaler = StandardScaler()
        self.is_trained = False
        self.last_training_time = None
        self.training_interval = timedelta(hours=6)  # Retrain every 6 hours

    def _prepare_features(self, df):
        """Prepare features for the model"""
        # Extract time-based features
        df['hour'] = df['timestamp'].dt.hour
        df['day_of_week'] = df['timestamp'].dt.dayofweek
        df['month'] = df['timestamp'].dt.month
        df['is_weekend'] = df['day_of_week'].isin([5, 6]).astype(int)

        # Add rolling statistics
        df['price_1h_avg'] = df['hourly_price'].rolling(window=1, min_periods=1).mean()
        df['price_3h_avg'] = df['hourly_price'].rolling(window=3, min_periods=1).mean()
        df['price_24h_avg'] = df['hourly_price'].rolling(window=24, min_periods=1).mean()

        # Calculate price changes
        df['price_change_1h'] = df['hourly_price'].diff()
        df['price_change_3h'] = df['hourly_price'] - df['price_3h_avg']

        feature_columns = [
            'hour', 'day_of_week', 'month', 'is_weekend',
            'price_1h_avg', 'price_3h_avg', 'price_24h_avg',
            'price_change_1h', 'price_change_3h'
        ]

        return df[feature_columns]

    async def _get_training_data(self):
        """Get historical price data for training"""
        with app.app_context():
            # Get last 30 days of price history
            cutoff_time = datetime.utcnow() - timedelta(days=30)
            history = PriceHistory.query.filter(
                PriceHistory.timestamp >= cutoff_time,
                PriceHistory.provider == "ComEd"  # Explicitly specify the provider
            ).order_by(PriceHistory.timestamp.asc()).all()

            if not history:
                raise ValueError("No historical data available for training")

            # Convert to DataFrame
            data = pd.DataFrame([{
                'timestamp': h.timestamp,
                'hourly_price': h.hourly_price,
                'prediction_accuracy': h.prediction_accuracy
            } for h in history])

            return data

    async def train(self, force=False):
        """Train the model on historical data"""
        try:
            # Check if we need to train
            if (not force and self.is_trained and self.last_training_time and 
                datetime.utcnow() - self.last_training_time < self.training_interval):
                logger.info("Using existing model, last trained: %s", self.last_training_time)
                return True

            # Get and prepare training data
            df = await self._get_training_data()
            X = self._prepare_features(df)
            y = df['hourly_price']

            # Scale features
            X_scaled = self.scaler.fit_transform(X)

            # Train model
            self.model.fit(X_scaled, y)
            self.is_trained = True
            self.last_training_time = datetime.utcnow()

            # Calculate training accuracy
            y_pred = self.model.predict(X_scaled)
            mae = mean_absolute_error(y, y_pred)
            logger.info("Model trained successfully. MAE: %.3f", mae)

            return True

        except Exception as e:
            logger.error("Error training model: %s", str(e))
            return False

    async def predict(self, current_price, timestamp=None):
        """Generate price predictions"""
        try:
            if not self.is_trained:
                if not await self.train():
                    raise ValueError("Could not train model")

            timestamp = timestamp or datetime.utcnow()

            # Create a DataFrame with current data
            current_data = pd.DataFrame([{
                'timestamp': timestamp,
                'hourly_price': current_price
            }])

            # Add historical context
            with app.app_context():
                history_cutoff = timestamp - timedelta(hours=24)
                historical_prices = PriceHistory.query.filter(
                    PriceHistory.timestamp >= history_cutoff,
                    PriceHistory.provider == "ComEd"
                ).order_by(PriceHistory.timestamp.desc()).all()

                for h in historical_prices:
                    current_data = pd.concat([
                        current_data,
                        pd.DataFrame([{
                            'timestamp': h.timestamp,
                            'hourly_price': h.hourly_price
                        }])
                    ])

            # Prepare features
            X = self._prepare_features(current_data.sort_values('timestamp'))
            X_scaled = self.scaler.transform(X)

            # Make prediction
            prediction = self.model.predict(X_scaled[-1:])

            # Calculate confidence score based on feature importance
            feature_importances = self.model.feature_importances_
            confidence_score = min(95, int(np.mean(feature_importances) * 100))

            # Get prediction range
            predictions = []
            for estimator in self.model.estimators_:
                predictions.append(estimator.predict(X_scaled[-1:])[0])

            prediction_range = {
                'low': float(np.percentile(predictions, 25)),
                'high': float(np.percentile(predictions, 75))
            }

            return {
                'predicted_price': float(prediction[0]),
                'confidence': confidence_score,
                'range': prediction_range,
                'trend': 'rising' if prediction[0] > current_price else 'falling'
            }

        except Exception as e:
            logger.error("Error making prediction: %s", str(e))
            # Fallback to simple prediction
            return {
                'predicted_price': current_price * 1.05,
                'confidence': 50,
                'range': {
                    'low': current_price * 0.95,
                    'high': current_price * 1.15
                },
                'trend': 'unknown'
            }

# Create global instance
price_predictor = PricePredictionModel()