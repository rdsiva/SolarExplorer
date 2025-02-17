import logging
from typing import Dict, Any, List
from .base_agent import BaseAgent
from telegram.ext import Application
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
import os
import asyncio
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from models import PriceHistory
from app import app

logger = logging.getLogger(__name__)

class NotificationAgent(BaseAgent):
    def __init__(self):
        super().__init__("Notification")
        self.notification_queue: List[Dict[str, Any]] = []
        self.bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.environ.get("TELEGRAM_CHAT_ID")
        self.bot = None

    async def start(self):
        """Initialize the Telegram bot when starting the agent"""
        await super().start()
        self.bot = Bot(token=self.bot_token)
        logger.info("Telegram bot initialized")

    async def process(self, message: Dict[str, Any]) -> Dict[str, Any]:
        if message.get("command") == "send_notification":
            notification_data = message.get("notification_data")
            if not notification_data:
                return {
                    "status": "error",
                    "message": "No notification data provided"
                }

            try:
                await self.queue_notification(notification_data)
                return {
                    "status": "success",
                    "message": "Notification queued successfully"
                }
            except Exception as e:
                logger.error(f"Error queuing notification: {str(e)}")
                return {
                    "status": "error",
                    "message": f"Failed to queue notification: {str(e)}"
                }
        return {
            "status": "error",
            "message": "Unknown command"
        }

    async def queue_notification(self, notification_data: Dict[str, Any]) -> None:
        self.notification_queue.append(notification_data)
        await self.process_queue()

    async def process_queue(self) -> None:
        if not self.bot:
            logger.error("Telegram bot not initialized")
            return

        while self.notification_queue:
            notification = self.notification_queue.pop(0)
            try:
                price_record_id = None
                # Store prediction in database first if available
                if notification.get("prediction", {}).get("short_term_prediction"):
                    with app.app_context():
                        price_record = PriceHistory.add_price_data(
                            hourly_price=notification["price_data"]["hourly_data"]["price"],
                            predicted_price=notification["prediction"]["short_term_prediction"],
                            prediction_confidence=notification["prediction"]["confidence"]
                        )
                        price_record_id = price_record.id

                # Format message with price data, analysis, and predictions
                message = self._format_notification_message(
                    price_data=notification.get("price_data", {}),
                    analysis=notification.get("analysis", {}),
                    prediction=notification.get("prediction", {})
                )

                # Create feedback buttons if we have a prediction and record ID
                reply_markup = None
                if price_record_id is not None:
                    keyboard = [
                        [
                            InlineKeyboardButton(
                                "✅ Accurate",
                                callback_data=f"feedback_accurate_{price_record_id}"
                            ),
                            InlineKeyboardButton(
                                "❌ Inaccurate",
                                callback_data=f"feedback_inaccurate_{price_record_id}"
                            )
                        ]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)

                # Send to Telegram with feedback buttons if applicable
                await self.bot.send_message(
                    chat_id=self.chat_id,
                    text=message,
                    parse_mode='HTML',
                    reply_markup=reply_markup
                )
                logger.info(f"Sent notification to Telegram: {message}")

            except Exception as e:
                logger.error(f"Error sending notification: {str(e)}")
                # Put the notification back in queue if sending failed
                self.notification_queue.insert(0, notification)
                break

    def _format_notification_message(self, price_data: Dict[str, Any] | None = None, analysis: Dict[str, Any] | None = None, prediction: Dict[str, Any] | None = None) -> str:
        """Format price alert message with detailed price information and prediction"""
        five_min_data = price_data.get("five_min_data", {}) if price_data else {}
        hourly_data = price_data.get("hourly_data", {}) if price_data else {}

        current_price = analysis.get("current_price", 0) if analysis else 0
        average_price = analysis.get("average_price", 0) if analysis else 0
        price_diff = current_price - average_price

        # Determine price status emoji and message
        if price_diff <= -0.5:
            status_emoji = "🟢"  # Green circle for good prices
            price_status = "GOOD TIME TO USE POWER"
        elif price_diff >= 1.0:
            status_emoji = "🔴"  # Red circle for price spikes
            price_status = "HIGH PRICE ALERT"
        else:
            status_emoji = "🟡"  # Yellow circle for normal prices
            price_status = "NORMAL PRICE LEVELS"

        # Format timestamps
        five_min_time = datetime.strptime(five_min_data.get('time', ''), '%I:%M %p').strftime('%I:%M %p %Z') if five_min_data.get('time') else 'N/A'
        hourly_time = datetime.strptime(hourly_data.get('time', ''), '%I:%M %p').strftime('%I:%M %p %Z') if hourly_data.get('time') else 'N/A'

        message = (
            f"{status_emoji} <b>Energy Price Alert: {price_status}</b>\n\n"
            f"📊 <b>Current Prices:</b>\n"
            f"• 5-min price ({five_min_time}): {five_min_data.get('price', 'N/A')}¢\n"
            f"• Hourly price ({hourly_time}): {hourly_data.get('price', 'N/A')}¢\n\n"
            f"📈 <b>Analysis:</b>\n"
            f"• Trend: {analysis.get('price_trend', 'stable') if analysis else 'stable'}\n"
            f"• vs Average: {price_diff:+.1f}¢\n"
            f"• Day Range: {analysis.get('min_price', 'N/A') if analysis else 'N/A'}¢ - {analysis.get('max_price', 'N/A') if analysis else 'N/A'}¢\n\n"
        )

        # Add price prediction if available
        if prediction:
            predicted_price = prediction.get("short_term_prediction")
            confidence = prediction.get("confidence")
            next_hour_range = prediction.get("next_hour_range", {})
            trend = prediction.get("trend", "stable")

            if predicted_price is not None and confidence is not None:
                message += (
                    f"🔮 <b>Price Prediction:</b>\n"
                    f"• Next hour: {predicted_price:.1f}¢\n"
                    f"• Range: {next_hour_range.get('low', predicted_price * 0.9):.1f}¢ - {next_hour_range.get('high', predicted_price * 1.1):.1f}¢\n"
                    f"• Confidence: {confidence}%\n"
                    f"• Trend: {trend.capitalize()}\n\n"
                )

                # Add detailed recommendation based on prediction
                if trend == "rising" and confidence >= 70:
                    message += "⚠️ <b>Price Trend Warning:</b>\n"
                    message += "Prices expected to rise. Consider using power now.\n\n"
                elif trend == "falling" and confidence >= 70:
                    message += "💡 <b>Price Trend Opportunity:</b>\n"
                    message += "Prices expected to fall. Consider delaying usage if possible.\n\n"

        # Add current timestamp in CST
        current_time = datetime.now(timezone.utc).astimezone(ZoneInfo("America/Chicago"))
        message += f"⏰ Last Updated: {current_time.strftime('%I:%M %p %Z')}"

        # Add feedback request if there's a prediction
        if prediction and prediction.get("short_term_prediction") is not None:
            message += "\n🎯 <b>Help us improve!</b>\n"
            message += "Please rate this prediction's accuracy using the buttons below.\n"

        return message