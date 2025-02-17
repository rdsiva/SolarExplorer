from datetime import datetime, timedelta
from app import db
from typing import List

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
    def add_price_data(provider: str, hourly_price: float, hourly_average: float = None, 
                      day_ahead_price: float = None, predicted_price: float = None, 
                      prediction_confidence: float = None, timestamp: datetime = None):
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
    def get_recent_history(provider: str, hours: int = 24) -> List[PriceHistory]:
        """Get price history for the last specified hours for a specific provider"""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        return PriceHistory.query.filter(
            PriceHistory.provider == provider,
            PriceHistory.timestamp >= cutoff_time
        ).order_by(PriceHistory.timestamp.desc()).all()

    @staticmethod
    def get_recent_predictions_with_accuracy(provider: str) -> List[PriceHistory]:
        """Get recent predictions that have accuracy feedback for a specific provider"""
        cutoff_time = datetime.utcnow() - timedelta(hours=72)  # Last 3 days
        return PriceHistory.query.filter(
            PriceHistory.provider == provider,
            PriceHistory.timestamp >= cutoff_time,
            PriceHistory.prediction_accuracy.isnot(None)
        ).order_by(PriceHistory.timestamp.desc()).all()