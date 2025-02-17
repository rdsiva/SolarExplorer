from datetime import datetime, timedelta
from app import db
from typing import List, Optional, TYPE_CHECKING
import numpy as np
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'

class PriceHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    provider = db.Column(db.String(50), nullable=False)  # e.g., 'ComEd'
    hourly_price = db.Column(db.Float, nullable=False)
    hourly_average = db.Column(db.Float, nullable=True)  # Current hour average
    day_ahead_price = db.Column(db.Float, nullable=True)
    predicted_price = db.Column(db.Float, nullable=True)
    prediction_accuracy = db.Column(db.Float, nullable=True)  # Store accuracy feedback
    prediction_confidence = db.Column(db.Float, nullable=True)

    def __repr__(self):
        return f'<PriceHistory {self.timestamp}: provider={self.provider}, hourly={self.hourly_price}>'

    @staticmethod
    def add_price_data(hourly_price: float, hourly_average: Optional[float] = None, 
                      day_ahead_price: Optional[float] = None, predicted_price: Optional[float] = None, 
                      prediction_confidence: Optional[float] = None, timestamp: Optional[datetime] = None, 
                      provider: str = "ComEd") -> "PriceHistory":
        """Add new price data to the database"""
        price_record = PriceHistory(
            provider=provider,
            timestamp=timestamp or datetime.utcnow(),
            hourly_price=hourly_price,
            hourly_average=hourly_average,
            day_ahead_price=day_ahead_price,
            predicted_price=predicted_price,
            prediction_confidence=prediction_confidence
        )
        db.session.add(price_record)
        db.session.commit()
        return price_record

    @staticmethod
    def update_prediction_accuracy(record_id: int, accuracy: float) -> bool:
        """Update the prediction accuracy based on feedback"""
        record = PriceHistory.query.get(record_id)
        if record:
            record.prediction_accuracy = accuracy
            db.session.commit()
            return True
        return False

    @staticmethod
    def get_recent_history(provider: str, hours: int = 24) -> List["PriceHistory"]:
        """Get price history for the last specified hours for a specific provider"""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        return PriceHistory.query.filter(
            PriceHistory.provider == provider,
            PriceHistory.timestamp >= cutoff_time
        ).order_by(PriceHistory.timestamp.desc()).all()

    @staticmethod
    def get_recent_predictions_with_accuracy(provider: str) -> List["PriceHistory"]:
        """Get recent predictions that have accuracy feedback for a specific provider"""
        cutoff_time = datetime.utcnow() - timedelta(hours=72)  # Last 3 days
        return PriceHistory.query.filter(
            PriceHistory.provider == provider,
            PriceHistory.timestamp >= cutoff_time,
            PriceHistory.prediction_accuracy.isnot(None)
        ).order_by(PriceHistory.timestamp.desc()).all()

    """Add feedback tracking to prediction model"""
    @staticmethod
    def get_prediction_feedback_stats(provider: str, days: int = 30) -> dict:
        """Get statistics about prediction accuracy based on user feedback"""
        cutoff_time = datetime.utcnow() - timedelta(days=days)
        records = PriceHistory.query.filter(
            PriceHistory.provider == provider,
            PriceHistory.timestamp >= cutoff_time,
            PriceHistory.prediction_accuracy.isnot(None)
        ).order_by(PriceHistory.timestamp.desc()).all()

        if not records:
            return {
                'accuracy': 0.0,
                'total_predictions': 0,
                'feedback_count': 0,
                'confidence_correlation': 0.0
            }

        accuracies = [float(r.prediction_accuracy or 0.0) for r in records]
        confidences = [float(r.prediction_confidence or 0.0) for r in records]

        stats = {
            'accuracy': float(sum(accuracies) / len(accuracies)) if accuracies else 0.0,
            'total_predictions': len(records),
            'feedback_count': len([a for a in accuracies if a is not None]),
        }

        # Calculate correlation between confidence and accuracy
        if len(confidences) > 1 and any(confidences):
            confidence_correlation = np.corrcoef(accuracies, confidences)[0, 1]
            stats['confidence_correlation'] = float(confidence_correlation)
        else:
            stats['confidence_correlation'] = 0.0

        return stats


class UserPreferences(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    chat_id = db.Column(db.String(100), unique=True, nullable=False)
    price_threshold = db.Column(db.Float, nullable=False, default=3.0)  # Default threshold
    alert_frequency = db.Column(db.String(20), nullable=False, default='immediate')  # immediate, hourly, daily
    start_time = db.Column(db.Time, nullable=True)  # Start of alert window
    end_time = db.Column(db.Time, nullable=True)  # End of alert window
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<UserPreferences chat_id={self.chat_id}, threshold={self.price_threshold}>'

    @staticmethod
    def get_user_preferences(chat_id: str) -> Optional["UserPreferences"]:
        """Get preferences for a specific user"""
        return UserPreferences.query.filter_by(chat_id=str(chat_id)).first()

    @staticmethod
    def create_or_update(chat_id: str, **kwargs) -> "UserPreferences":
        """Create or update user preferences"""
        prefs = UserPreferences.get_user_preferences(str(chat_id))
        if not prefs:
            prefs = UserPreferences(chat_id=str(chat_id))
            db.session.add(prefs)

        # Update fields if provided
        for key, value in kwargs.items():
            if hasattr(prefs, key):
                setattr(prefs, key, value)

        db.session.commit()
        return prefs

class UserAnalytics(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    chat_id = db.Column(db.String(100), db.ForeignKey('user_preferences.chat_id'), nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    avg_daily_price = db.Column(db.Float, nullable=True)
    peak_usage_time = db.Column(db.Time, nullable=True)
    low_price_periods = db.Column(db.JSON, nullable=True)  # Store periods of consistently low prices
    high_price_periods = db.Column(db.JSON, nullable=True)  # Store periods of consistently high prices
    monthly_price_trend = db.Column(db.String(20), nullable=True)  # rising, falling, stable

    # Relationship
    user = db.relationship('UserPreferences', backref=db.backref('analytics', lazy=True))

    @staticmethod
    def create_or_update_analytics(chat_id: str, **kwargs) -> "UserAnalytics":
        """Create or update user analytics"""
        analytics = UserAnalytics.query.filter_by(
            chat_id=str(chat_id),
            timestamp=datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        ).first()

        if not analytics:
            analytics = UserAnalytics(chat_id=str(chat_id))
            db.session.add(analytics)

        for key, value in kwargs.items():
            if hasattr(analytics, key):
                setattr(analytics, key, value)

        db.session.commit()
        return analytics

class SavingsInsight(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    chat_id = db.Column(db.String(100), db.ForeignKey('user_preferences.chat_id'), nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    potential_savings = db.Column(db.Float, nullable=False)  # Estimated savings in dollars
    recommendation_type = db.Column(db.String(50), nullable=False)  # e.g., 'shift_usage', 'reduce_peak'
    description = db.Column(db.Text, nullable=False)  # Detailed recommendation
    impact_score = db.Column(db.Integer, nullable=False)  # 1-100 score indicating potential impact
    implemented = db.Column(db.Boolean, default=False)  # Track if user implemented this saving

    # Relationship
    user = db.relationship('UserPreferences', backref=db.backref('savings_insights', lazy=True))

    @staticmethod
    def add_insight(chat_id: str, potential_savings: float, recommendation_type: str, 
                   description: str, impact_score: int) -> "SavingsInsight":
        """Add a new savings insight"""
        insight = SavingsInsight(
            chat_id=str(chat_id),
            potential_savings=potential_savings,
            recommendation_type=recommendation_type,
            description=description,
            impact_score=impact_score
        )
        db.session.add(insight)
        db.session.commit()
        return insight

    @staticmethod
    def get_user_insights(chat_id: str, days: int = 30) -> List["SavingsInsight"]:
        """Get recent insights for a user"""
        cutoff_time = datetime.utcnow() - timedelta(days=days)
        return SavingsInsight.query.filter(
            SavingsInsight.chat_id == str(chat_id),
            SavingsInsight.timestamp >= cutoff_time
        ).order_by(SavingsInsight.timestamp.desc()).all()


class TeslaPreferences(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    chat_id = db.Column(db.String(100), db.ForeignKey('user_preferences.chat_id'), nullable=False)
    enabled = db.Column(db.Boolean, default=False)
    vehicle_id = db.Column(db.String(100), nullable=True)
    access_token = db.Column(db.String(500), nullable=True)
    refresh_token = db.Column(db.String(500), nullable=True)
    token_expiry = db.Column(db.DateTime, nullable=True)
    oauth_state = db.Column(db.String(100), nullable=True)  # Added for OAuth flow
    min_battery_level = db.Column(db.Integer, default=20)
    max_battery_level = db.Column(db.Integer, default=80)
    price_threshold = db.Column(db.Float, default=3.5)
    preferred_start_hour = db.Column(db.Integer, default=22)  # 10 PM
    preferred_end_hour = db.Column(db.Integer, default=6)    # 6 AM
    last_vehicle_status = db.Column(db.JSON, nullable=True)  # Stores battery level, charging state, etc.
    last_status_update = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship with UserPreferences
    user = db.relationship('UserPreferences', backref=db.backref('tesla_preferences', uselist=False))

    @staticmethod
    def get_preferences(chat_id: str) -> Optional["TeslaPreferences"]:
        """Get Tesla preferences for a specific user"""
        return TeslaPreferences.query.filter_by(chat_id=str(chat_id)).first()

    @staticmethod
    def create_or_update(chat_id: str, **kwargs) -> "TeslaPreferences":
        """Create or update Tesla preferences"""
        prefs = TeslaPreferences.get_preferences(str(chat_id))
        if not prefs:
            prefs = TeslaPreferences(chat_id=str(chat_id))
            db.session.add(prefs)

        # Update fields if provided
        for key, value in kwargs.items():
            if hasattr(prefs, key):
                setattr(prefs, key, value)

        db.session.commit()
        return prefs

    def update_vehicle_status(self, status_data: dict) -> None:
        """Update the vehicle status and timestamp"""
        self.last_vehicle_status = status_data
        self.last_status_update = datetime.utcnow()
        db.session.commit()

    def update_auth_tokens(self, access_token: str, refresh_token: str) -> None:
        """Update authentication tokens"""
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.token_expiry = datetime.utcnow() + timedelta(hours=6)  # Tesla tokens typically expire in 8 hours
        db.session.commit()

    def is_preferred_charging_time(self) -> bool:
        """Check if current time is within preferred charging hours"""
        current_hour = datetime.now().hour

        # Handle overnight period (e.g., 22:00-06:00)
        if self.preferred_start_hour > self.preferred_end_hour:
            return current_hour >= self.preferred_start_hour or current_hour < self.preferred_end_hour
        else:
            return self.preferred_start_hour <= current_hour < self.preferred_end_hour

    def should_start_charging(self, current_price: float) -> bool:
        """Determine if charging should start based on price and battery level"""
        if not self.enabled or not self.last_vehicle_status:
            return False

        battery_level = self.last_vehicle_status.get('battery_level', 0)
        charging_state = self.last_vehicle_status.get('charging_state', 'Stopped')

        # Emergency charging if battery is below minimum
        emergency = battery_level <= self.min_battery_level

        # If it's an emergency, charge regardless of time or price
        if emergency:
            return True

        # Check if current time is within preferred charging hours
        if not self.is_preferred_charging_time():
            return False

        # Check if price is below threshold
        price_ok = current_price <= self.price_threshold

        # Check if battery is below max level
        battery_ok = battery_level < self.max_battery_level

        return price_ok and battery_ok

    def should_stop_charging(self, current_price: float) -> bool:
        """Determine if charging should stop based on price and battery level"""
        if not self.enabled or not self.last_vehicle_status:
            return False

        battery_level = self.last_vehicle_status.get('battery_level', 0)
        charging_state = self.last_vehicle_status.get('charging_state', 'Stopped')

        # Stop if price is above threshold or battery is full
        return (current_price > self.price_threshold and battery_level > self.min_battery_level) or battery_level >= self.max_battery_level