from datetime import datetime, timedelta
from app import db

class PriceHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    hourly_price = db.Column(db.Float, nullable=False)
    day_ahead_price = db.Column(db.Float, nullable=True)
    predicted_price = db.Column(db.Float, nullable=True)
    prediction_accuracy = db.Column(db.Float, nullable=True)  # Store accuracy feedback
    prediction_confidence = db.Column(db.Float, nullable=True)

    def __repr__(self):
        return f'<PriceHistory {self.timestamp}: hourly={self.hourly_price}, predicted={self.predicted_price}>'

    @staticmethod
    def add_price_data(hourly_price, day_ahead_price=None, predicted_price=None, prediction_confidence=None):
        price_record = PriceHistory(
            hourly_price=hourly_price,
            day_ahead_price=day_ahead_price,
            predicted_price=predicted_price,
            prediction_confidence=prediction_confidence
        )
        db.session.add(price_record)
        db.session.commit()
        return price_record

    @staticmethod
    def update_prediction_accuracy(record_id, accuracy):
        """Update the prediction accuracy based on feedback"""
        record = PriceHistory.query.get(record_id)
        if record:
            record.prediction_accuracy = accuracy
            db.session.commit()
            return True
        return False

    @staticmethod
    def get_recent_history(hours=24):
        """Get price history for the last specified hours"""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        return PriceHistory.query.filter(
            PriceHistory.timestamp >= cutoff_time
        ).order_by(PriceHistory.timestamp.desc()).all()

    @staticmethod
    def get_recent_predictions_with_accuracy():
        """Get recent predictions that have accuracy feedback"""
        cutoff_time = datetime.utcnow() - timedelta(hours=72)  # Last 3 days
        return PriceHistory.query.filter(
            PriceHistory.timestamp >= cutoff_time,
            PriceHistory.prediction_accuracy.isnot(None)
        ).order_by(PriceHistory.timestamp.desc()).all()