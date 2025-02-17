import logging
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error
from app import app
from models import PriceHistory
from weather_provider import weather_provider

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
        """Prepare features for the model including weather data"""
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

        # Add weather features if available
        if 'temperature' in df.columns:
            df['temp_impact'] = df.apply(lambda x: 
                0.15 if x['temperature'] >= 85 else  # Hot weather impact
                0.1 if x['temperature'] <= 32 else   # Cold weather impact
                0.05 if (x['temperature'] >= 75 or x['temperature'] <= 45) else  # Moderate impact
                0.0,  # Normal conditions
                axis=1
            )

            # Create weather condition impact
            df['weather_impact'] = df.apply(lambda x: 
                0.08 if x.get('weather_main', '').lower() in ['thunderstorm', 'rain', 'snow'] else
                0.05 if x.get('weather_main', '').lower() in ['clouds', 'mist'] else
                0.0,
                axis=1
            )

        feature_columns = [
            'hour', 'day_of_week', 'month', 'is_weekend',
            'price_1h_avg', 'price_3h_avg', 'price_24h_avg',
            'price_change_1h', 'price_change_3h'
        ]

        # Add weather features if available
        if 'temperature' in df.columns:
            weather_features = ['temperature', 'humidity', 'temp_impact', 'weather_impact']
            feature_columns.extend(weather_features)

        return df[feature_columns]

    async def _get_training_data(self):
        """Get historical price and weather data for training"""
        with app.app_context():
            # Get last 30 days of price history
            cutoff_time = datetime.utcnow() - timedelta(days=30)
            history = PriceHistory.query.filter(
                PriceHistory.timestamp >= cutoff_time,
                PriceHistory.provider == "ComEd"
            ).order_by(PriceHistory.timestamp.asc()).all()

            if not history:
                raise ValueError("No historical data available for training")

            # Convert to DataFrame
            data = pd.DataFrame([{
                'timestamp': h.timestamp,
                'hourly_price': h.hourly_price,
                'prediction_accuracy': h.prediction_accuracy
            } for h in history])

            # Add weather data
            try:
                weather_data = await weather_provider.get_current_weather()
                if weather_data:
                    for col in ['temperature', 'humidity', 'weather_main']:
                        data[col] = weather_data[col]
                    logger.info("Successfully added weather data to training set")
            except Exception as e:
                logger.warning(f"Could not fetch weather data: {str(e)}")

            return data

    async def train(self, force=False):
        """Train the model on historical data with weather features"""
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
            logger.info("Model trained successfully with weather features. MAE: %.3f", mae)

            return True

        except Exception as e:
            logger.error("Error training model: %s", str(e))
            return False

    async def predict(self, current_price, timestamp=None):
        """Generate price predictions with weather-enhanced confidence scores"""
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

            # Add weather data
            try:
                weather_data = await weather_provider.get_current_weather()
                if weather_data:
                    for col in ['temperature', 'humidity', 'weather_main']:
                        current_data[col] = weather_data[col]
                    logger.info("Added current weather data to prediction")
            except Exception as e:
                logger.warning(f"Could not fetch weather data for prediction: {str(e)}")

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

            # Calculate confidence score based on feature importance and weather impact
            feature_importances = self.model.feature_importances_
            base_confidence = min(95, int(np.mean(feature_importances) * 100))

            # Adjust confidence based on weather data availability
            weather_confidence_adj = 5 if 'temperature' in X.columns else -5
            confidence_score = min(95, base_confidence + weather_confidence_adj)

            # Get prediction range
            predictions = []
            for estimator in self.model.estimators_:
                predictions.append(estimator.predict(X_scaled[-1:])[0])

            prediction_range = {
                'low': float(np.percentile(predictions, 25)),
                'high': float(np.percentile(predictions, 75))
            }

            # Get weather impact for explanation
            weather_impact = None
            if weather_data:
                weather_impact = weather_provider.calculate_weather_impact(weather_data)

            return {
                'predicted_price': float(prediction[0]),
                'confidence': confidence_score,
                'range': prediction_range,
                'trend': 'rising' if prediction[0] > current_price else 'falling',
                'weather_impact': weather_impact
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
                'trend': 'unknown',
                'weather_impact': None
            }

# Create global instance
price_predictor = PricePredictionModel()