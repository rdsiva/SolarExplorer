import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from .base_module import BaseModule

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

    async def initialize(self) -> bool:
        """Initialize dashboard module"""
        try:
            logger.info("Initializing dashboard module")
            await self._reset_daily_metrics()
            return True
        except Exception as e:
            logger.error(f"Failed to initialize dashboard: {str(e)}")
            return False

    async def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process dashboard data and update metrics"""
        try:
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
                self.metrics['price_trends'].append({
                    'timestamp': datetime.now().isoformat(),
                    'price': data['price_alert'].get('price', 0)
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
            return {
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