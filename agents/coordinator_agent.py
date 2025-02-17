import logging
import asyncio
from typing import Dict, Any, Optional
from .base_agent import BaseAgent
from .data_collection_agent import DataCollectionAgent
from .analysis_agent import AnalysisAgent
from .notification_agent import NotificationAgent
from .prediction_agent import PricePredictionAgent

logger = logging.getLogger(__name__)

class CoordinatorAgent(BaseAgent):
    def __init__(self):
        super().__init__("Coordinator")
        self.data_collector = DataCollectionAgent()
        self.analyzer = AnalysisAgent()
        self.predictor = PricePredictionAgent()
        self.notifier = NotificationAgent()
        self.agents = [self.data_collector, self.analyzer, self.predictor, self.notifier]

    async def start_all(self):
        """Start all agents"""
        for agent in self.agents:
            await agent.start()
        await self.start()

    async def stop_all(self):
        """Stop all agents"""
        for agent in self.agents:
            await agent.stop()
        await self.stop()

    async def process(self, message: Dict[str, Any]) -> Dict[str, Any]:
        if message.get("command") == "monitor_prices":
            try:
                # 1. Collect price data
                price_data = await self.data_collector.process({"command": "fetch_prices"})
                if price_data.get("status") != "success":
                    return price_data

                # 2. Analyze the data
                analysis_result = await self.analyzer.process({
                    "command": "analyze_prices",
                    "price_data": price_data.get("data", {})
                })

                if analysis_result.get("status") != "success":
                    return analysis_result

                analysis_data = analysis_result.get("analysis", {})

                # 3. Generate price predictions
                prediction_result = await self.predictor.process({
                    "command": "predict_prices",
                    "price_history": self.analyzer.price_history
                })

                prediction_data = prediction_result.get("predictions", {}) if prediction_result.get("status") == "success" else {}

                # 4. Send notifications if needed
                if self.should_send_notification(analysis_data, prediction_data):
                    notification_result = await self.notifier.process({
                        "command": "send_notification",
                        "notification_data": {
                            "price_data": price_data.get("data", {}),
                            "analysis": analysis_data,
                            "prediction": prediction_data
                        }
                    })
                    if notification_result.get("status") != "success":
                        return notification_result

                return {
                    "status": "success",
                    "message": "Price monitoring cycle completed successfully",
                    "data": {
                        "price_data": price_data.get("data", {}),
                        "analysis": analysis_data,
                        "prediction": prediction_data
                    }
                }

            except Exception as e:
                logger.error(f"Error in price monitoring cycle: {str(e)}")
                return {
                    "status": "error",
                    "message": f"Price monitoring cycle failed: {str(e)}"
                }

        return {
            "status": "error",
            "message": "Unknown command"
        }

    def should_send_notification(self, analysis: Dict[str, Any], prediction: Dict[str, Any]) -> bool:
        """Determine if a notification should be sent based on analysis and predictions"""
        current_price = analysis.get("current_price", 0)
        average_price = analysis.get("average_price", 0)
        max_price = analysis.get("max_price", 0)
        predicted_price = prediction.get("short_term_prediction")
        prediction_confidence = prediction.get("confidence", 0)

        # Current price conditions (from previous implementation)
        price_drop = current_price <= (average_price - 0.5)
        price_spike = current_price >= (average_price + 1.0)
        near_daily_low = current_price <= (analysis.get("min_price", 0) + 0.3)
        trending_down = analysis.get("price_trend") == "falling"

        # Prediction-based conditions
        predicted_significant_drop = (
            predicted_price is not None and
            prediction_confidence >= 70 and
            predicted_price <= (current_price - 0.5)
        )

        predicted_significant_spike = (
            predicted_price is not None and
            prediction_confidence >= 70 and
            predicted_price >= (current_price + 1.0)
        )

        # Return notification conditions
        return (
            price_drop or 
            price_spike or 
            (trending_down and near_daily_low) or
            predicted_significant_drop or
            predicted_significant_spike
        )