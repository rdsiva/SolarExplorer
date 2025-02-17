import logging
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error
from scipy.stats import entropy
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
        self.pattern_types = {
            'spike': {'threshold': 0.2, 'window': 3},
            'dip': {'threshold': -0.2, 'window': 3},
            'trend': {'threshold': 0.1, 'window': 12},
            'cycle': {'min_period': 12, 'max_period': 24}
        }

    def _prepare_features(self, df):
        """Enhanced feature preparation with pattern recognition"""
        # Basic time-based features
        df['hour'] = df['timestamp'].dt.hour
        df['day_of_week'] = df['timestamp'].dt.dayofweek
        df['month'] = df['timestamp'].dt.month
        df['is_weekend'] = df['day_of_week'].isin([5, 6]).astype(int)

        # Advanced rolling statistics
        windows = [1, 3, 6, 12, 24]
        for window in windows:
            df[f'price_{window}h_avg'] = df['hourly_price'].rolling(window=window, min_periods=1).mean()
            df[f'price_{window}h_std'] = df['hourly_price'].rolling(window=window, min_periods=1).std()
            df[f'price_{window}h_max'] = df['hourly_price'].rolling(window=window, min_periods=1).max()
            df[f'price_{window}h_min'] = df['hourly_price'].rolling(window=window, min_periods=1).min()

        # Pattern recognition features
        df['price_acceleration'] = df['hourly_price'].diff().diff()
        df['volatility'] = df['hourly_price'].rolling(window=12).std() / df['hourly_price'].rolling(window=12).mean()

        # Detect seasonal patterns
        df['daily_pattern'] = df['hour'].map(self._calculate_hourly_pattern(df))
        df['weekly_pattern'] = df['day_of_week'].map(self._calculate_daily_pattern(df))

        # Calculate entropy for pattern complexity
        df['pattern_complexity'] = df['hourly_price'].rolling(window=24).apply(
            lambda x: entropy(np.abs(np.diff(x)) + 1e-10)
        )

        feature_columns = [
            'hour', 'day_of_week', 'month', 'is_weekend',
            'price_acceleration', 'volatility', 'pattern_complexity', 
            'daily_pattern', 'weekly_pattern'
        ] + [f'price_{w}h_{stat}' for w in windows for stat in ['avg', 'std', 'max', 'min']]

        return df[feature_columns].fillna(0)

    def _calculate_hourly_pattern(self, df):
        """Calculate typical price patterns for each hour"""
        hourly_patterns = df.groupby('hour')['hourly_price'].mean()
        return (hourly_patterns - hourly_patterns.mean()) / hourly_patterns.std()

    def _calculate_daily_pattern(self, df):
        """Calculate typical price patterns for each day of week"""
        daily_patterns = df.groupby('day_of_week')['hourly_price'].mean()
        return (daily_patterns - daily_patterns.mean()) / daily_patterns.std()

    def _detect_patterns(self, prices):
        """Detect specific price patterns in the time series"""
        patterns = {}

        # Detect price spikes and dips
        price_changes = np.diff(prices)
        for pattern, params in self.pattern_types.items():
            if pattern in ['spike', 'dip']:
                threshold = params['threshold']
                window = params['window']
                rolling_std = pd.Series(prices).rolling(window=window).std()
                if pattern == 'spike':
                    patterns[pattern] = any(price_changes > (threshold * rolling_std[:-1]))
                else:  # dip
                    patterns[pattern] = any(price_changes < (threshold * rolling_std[:-1]))

            elif pattern == 'trend':
                # Detect consistent price trends
                window = params['window']
                trends = pd.Series(prices).rolling(window=window).apply(
                    lambda x: np.polyfit(range(len(x)), x, 1)[0]
                )
                patterns[pattern] = abs(trends.mean()) > params['threshold']

            elif pattern == 'cycle':
                # Detect cyclical patterns using autocorrelation
                acf = np.correlate(prices - np.mean(prices), prices - np.mean(prices), mode='full')
                acf = acf[len(acf)//2:]
                peaks = np.where(np.diff(np.sign(np.diff(acf))) < 0)[0] + 1
                if len(peaks) > 0:
                    cycle_length = peaks[0]
                    patterns[pattern] = params['min_period'] <= cycle_length <= params['max_period']
                else:
                    patterns[pattern] = False

        return patterns

    async def _get_training_data(self):
        """Get historical price data for training"""
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
        """Generate price predictions with pattern analysis"""
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

            # Detect patterns in recent price history
            recent_prices = current_data['hourly_price'].values
            patterns = self._detect_patterns(recent_prices)

            # Calculate confidence score based on feature importance and pattern recognition
            feature_importances = self.model.feature_importances_
            pattern_confidence = sum(patterns.values()) / len(patterns) if patterns else 0 #Handle empty patterns
            base_confidence = float(np.mean(feature_importances) * 100)
            confidence_score = min(95, int((base_confidence + pattern_confidence * 100) / 2))

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
                'trend': 'rising' if prediction[0] > current_price else 'falling',
                'patterns': patterns
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
                'patterns': {}
            }

# Create global instance
price_predictor = PricePredictionModel()