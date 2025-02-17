import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from flask import current_app
from .base_module import BaseModule
from database import get_db
from models import PriceHistory

logger = logging.getLogger(__name__)

class DashboardModule(BaseModule):
    """Module for managing analytics dashboard and data visualization"""

    def __init__(self):
        super().__init__(
            name="dashboard",
            description="Provides analytics dashboard and data visualization capabilities"
        )
        self.metrics = {
            'active_users': 0,
            'total_predictions': 0,
            'accuracy_rate': 0.0,
            'price_alerts_sent': 0,
            'price_trends': []
        }
        self.latest_price_data = None

    async def initialize(self) -> bool:
        """Initialize dashboard module"""
        try:
            logger.info("Initializing dashboard module")
            await self._reset_daily_metrics()
            try:
                with current_app.app_context():
                    self._load_latest_price_data()
            except RuntimeError:
                logger.warning("No Flask application context available, skipping database operations")
                self.latest_price_data = {'price': 0, 'timestamp': datetime.now(), 'trend': 'unknown'}
            return True
        except Exception as e:
            logger.error(f"Failed to initialize dashboard: {str(e)}")
            return False

    def _load_latest_price_data(self):
        """Load the latest price data from database"""
        try:
            db = get_db()
            latest_record = PriceHistory.query.order_by(
                PriceHistory.timestamp.desc()
            ).first()

            if latest_record:
                self.latest_price_data = {
                    'price': latest_record.hourly_price,
                    'timestamp': latest_record.timestamp,
                    'trend': 'stable'  # Default trend
                }
                logger.info(f"Loaded latest price data: {self.latest_price_data}")
            else:
                logger.warning("No price history data found")
                self.latest_price_data = {'price': 0, 'timestamp': datetime.now(), 'trend': 'unknown'}
        except Exception as e:
            logger.error(f"Error loading price data: {str(e)}")
            self.latest_price_data = {'price': 0, 'timestamp': datetime.now(), 'trend': 'unknown'}

    async def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process dashboard data and update metrics"""
        try:
            if 'price_data' in data:
                self.latest_price_data = data['price_data']
                logger.info(f"Updated latest price data: {self.latest_price_data}")

            if 'user_activity' in data:
                self.metrics['active_users'] += 1

            if 'prediction_result' in data:
                self.metrics['total_predictions'] += 1
                # Update accuracy based on actual vs predicted
                predicted = data['prediction_result'].get('predicted_price', 0)
                actual = data['prediction_result'].get('actual_price', 0)
                if actual != 0:
                    accuracy = 1 - abs(predicted - actual) / actual
                    self.metrics['accuracy_rate'] = (
                        (self.metrics['accuracy_rate'] * (self.metrics['total_predictions'] - 1) + accuracy) 
                        / self.metrics['total_predictions']
                    )

            if 'price_alert' in data:
                self.metrics['price_alerts_sent'] += 1
                if self.latest_price_data:
                    self.metrics['price_trends'].append({
                        'timestamp': self.latest_price_data['timestamp'].isoformat(),
                        'price': self.latest_price_data['price']
                    })
                    # Keep only last 24 hours of price trends
                    self._cleanup_price_trends()

            return {
                "status": "success",
                "message": "Dashboard data processed successfully",
                "metrics": self.metrics
            }
        except Exception as e:
            logger.error(f"Error processing dashboard data: {str(e)}")
            return {
                "status": "error",
                "message": str(e)
            }

    async def get_notification_data(self) -> Optional[Dict[str, Any]]:
        """Get dashboard data for notifications"""
        try:
            if not self.latest_price_data:
                try:
                    with current_app.app_context():
                        self._load_latest_price_data()
                except RuntimeError:
                    logger.warning("No Flask application context available")

            return {
                "current_price": self.latest_price_data['price'] if self.latest_price_data else None,
                "active_users": self.metrics['active_users'],
                "total_predictions": self.metrics['total_predictions'],
                "accuracy_rate": round(self.metrics['accuracy_rate'] * 100, 2),
                "alerts_sent": self.metrics['price_alerts_sent'],
                "price_trend": self._get_price_trend_summary()
            }
        except Exception as e:
            logger.error(f"Error getting dashboard notification data: {str(e)}")
            return None

    async def _reset_daily_metrics(self) -> None:
        """Reset daily metrics at midnight"""
        self.metrics['active_users'] = 0
        self.metrics['price_alerts_sent'] = 0

    def _cleanup_price_trends(self) -> None:
        """Remove price trends older than 24 hours"""
        now = datetime.now()
        self.metrics['price_trends'] = [
            trend for trend in self.metrics['price_trends']
            if (now - datetime.fromisoformat(trend['timestamp'])) < timedelta(hours=24)
        ]

    def _get_price_trend_summary(self) -> Dict[str, Any]:
        """Get summary of price trends for the last 24 hours"""
        if not self.metrics['price_trends']:
            return {"trend": "stable", "change": 0}

        prices = [t['price'] for t in self.metrics['price_trends']]
        if len(prices) >= 2:
            change = ((prices[-1] - prices[0]) / prices[0]) * 100
            trend = "up" if change > 0 else "down" if change < 0 else "stable"
            return {
                "trend": trend,
                "change": round(change, 2)
            }
        return {"trend": "stable", "change": 0}