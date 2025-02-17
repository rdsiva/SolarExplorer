import os
import logging
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler
import asyncio
import requests
from datetime import datetime
from config import TELEGRAM_BOT_TOKEN, HEALTH_CHECK_URL, MIN_RATE
from price_monitor import PriceMonitor
from zoneinfo import ZoneInfo
from models import PriceHistory
from app import app

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class EnergyPriceBot:
    def __init__(self):
        """Initialize the bot with webhook configuration"""
        self.application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        self.bot = self.application.bot

        # Get Replit domain from environment
        repl_id = os.environ.get('REPL_ID', '')
        if not repl_id:
            raise ValueError("REPL_ID not set in environment variables")

        # Use Replit's domain for webhook
        self.webhook_url = f"https://{repl_id}.id.repl.co"
        self.webhook_path = f'/telegram-webhook-{TELEGRAM_BOT_TOKEN}'

        logger.info(f"Initializing bot with webhook URL: {self.webhook_url}")
        self.setup_handlers()

    def setup_handlers(self):
        """Set up command handlers for the bot"""
        self.application.add_handler(CommandHandler("start", self.cmd_start))
        self.application.add_handler(CommandHandler("help", self.cmd_help))
        self.application.add_handler(CommandHandler("start_monitoring", self.cmd_start_monitoring))
        self.application.add_handler(CommandHandler("stop_monitoring", self.cmd_stop_monitoring))
        self.application.add_handler(CommandHandler("check_price", self.cmd_check_price))
        self.application.add_handler(CommandHandler("status", self.cmd_status))
        self.application.add_handler(CallbackQueryHandler(self.handle_prediction_feedback))

    async def setup_webhook(self):
        """Set up webhook for the bot"""
        webhook_url = f"{self.webhook_url}{self.webhook_path}"
        try:
            logger.info("Deleting existing webhook...")
            await self.bot.delete_webhook(drop_pending_updates=True)

            logger.info(f"Setting up new webhook at {webhook_url}")
            await self.bot.set_webhook(
                url=webhook_url,
                allowed_updates=['message', 'callback_query'],
                drop_pending_updates=True
            )

            # Verify webhook was set correctly
            webhook_info = await self.bot.get_webhook_info()
            logger.info(f"Webhook info: {webhook_info.to_dict()}")

            if webhook_info.url == webhook_url:
                logger.info("Webhook setup successful!")
            else:
                logger.error(f"Webhook URL mismatch. Expected: {webhook_url}, Got: {webhook_info.url}")
                raise ValueError("Webhook setup failed: URL mismatch")

        except Exception as e:
            logger.error(f"Failed to set up webhook: {str(e)}")
            raise

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle the /start command"""
        chat_id = update.effective_chat.id
        welcome_message = (
            f"👋 Welcome to the Energy Price Monitor Bot!\n\n"
            f"Your Chat ID is: {chat_id}\n"
            "Please save this ID in your .env file as TELEGRAM_CHAT_ID\n\n"
            f"I can help you track energy prices and notify you when they fall below "
            f"{MIN_RATE} cents.\n\n"
            "Available commands:\n"
            "/start_monitoring - Start price monitoring\n"
            "/stop_monitoring - Stop price monitoring\n"
            "/check_price - Check current prices\n"
            "/status - Check monitoring status\n"
            "/help - Show this help message"
        )
        await update.message.reply_text(welcome_message)

    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle the /help command"""
        await self.cmd_start(update, context)

    async def check_api_health(self):
        """Check if the API is accessible"""
        try:
            response = requests.get(HEALTH_CHECK_URL)
            return response.status_code == 200
        except:
            return False

    async def price_monitor_job(self, context: ContextTypes.DEFAULT_TYPE):
        """Regular job to check prices and send notifications"""
        try:
            # Check 5-minute price
            five_min_data = await PriceMonitor.check_five_min_price()
            await self.send_price_alert(context.job.chat_id, five_min_data)

            # Check hourly price
            hourly_data = await PriceMonitor.check_hourly_price()
            await self.send_price_alert(context.job.chat_id, hourly_data)

        except Exception as e:
            error_message = f"❌ Error during price monitoring: {str(e)}"
            logger.error(error_message)
            await context.bot.send_message(
                chat_id=context.job.chat_id,
                text=error_message
            )

    async def cmd_start_monitoring(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start the price monitoring job"""
        chat_id = update.effective_chat.id

        if 'monitoring_job' in context.chat_data:
            await update.message.reply_text("⚠️ Monitoring is already active!")
            return

        if not await self.check_api_health():
            await update.message.reply_text("❌ Cannot start monitoring - API is not accessible")
            return

        # Start monitoring job - runs every hour
        job = context.job_queue.run_repeating(
            self.price_monitor_job,
            interval=3600,  # 1 hour
            first=0,  # Run immediately
            chat_id=chat_id
        )
        context.chat_data['monitoring_job'] = job

        await update.message.reply_text(
            "✅ Price monitoring started! You'll receive hourly updates and notifications "
            f"when prices fall below {MIN_RATE} cents."
        )

    async def cmd_stop_monitoring(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Stop the price monitoring job"""
        if 'monitoring_job' not in context.chat_data:
            await update.message.reply_text("⚠️ No active monitoring to stop!")
            return

        job = context.chat_data['monitoring_job']
        job.schedule_removal()
        del context.chat_data['monitoring_job']
        await update.message.reply_text("✅ Price monitoring stopped!")

    async def cmd_check_price(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Check current prices on demand"""
        try:
            await update.message.reply_text("🔍 Checking current prices...")

            # Log current CST time for verification
            cst_time = await self.test_cst_time()
            logger.info(f"Initiating price check at CST: {cst_time}")

            five_min_data = await PriceMonitor.check_five_min_price()
            hourly_data = await PriceMonitor.check_hourly_price()

            # Create prediction data with enhanced details
            current_price = float(hourly_data.get('price', 0))
            predicted_price = round(current_price * 1.1, 1)  # 10% higher than current for testing
            confidence = 75
            trend = 'rising'

            prediction_data = {
                'short_term_prediction': predicted_price,
                'confidence': confidence,
                'trend': trend,
                'next_hour_range': {
                    'low': round(current_price * 0.9, 1),
                    'high': round(current_price * 1.2, 1)
                },
                'recommendation': self.get_recommendation(
                    current_price,
                    predicted_price,
                    trend,
                    confidence
                )
            }

            # Send alerts with prediction data and feedback buttons
            await self.send_price_alert(update.effective_chat.id, five_min_data, prediction_data)
            await self.send_price_alert(update.effective_chat.id, hourly_data, prediction_data)

        except Exception as e:
            error_msg = f"❌ Error checking prices: {str(e)}"
            logger.error(error_msg)
            await update.message.reply_text(error_msg)

    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Check the monitoring status"""
        api_status = "✅ Online" if await self.check_api_health() else "❌ Offline"
        monitoring_status = "✅ Active" if 'monitoring_job' in context.chat_data else "❌ Inactive"

        status_message = (
            "📊 System Status\n"
            f"API Status: {api_status}\n"
            f"Monitoring: {monitoring_status}\n"
            f"Price Threshold: {MIN_RATE} cents"
        )
        await update.message.reply_text(status_message)

    async def test_cst_time(self):
        """Test CST time calculation"""
        cst_now = datetime.now(ZoneInfo("America/Chicago"))
        logger.info(f"Current CST Time: {cst_now.strftime('%Y-%m-%d %I:%M %p')}")
        return cst_now

    async def send_price_alert(self, chat_id: int, price_data: dict, prediction_data: dict | None = None):
        """Send price alert with feedback buttons"""
        price_record_id = None

        # Store prediction in database first if available
        if prediction_data and prediction_data.get('short_term_prediction'):
            with app.app_context():
                price_record = PriceHistory.add_price_data(
                    hourly_price=float(price_data.get('price', 0)),
                    predicted_price=prediction_data['short_term_prediction'],
                    prediction_confidence=prediction_data['confidence']
                )
                price_record_id = price_record.id

        message = self._format_price_message(price_data, prediction_data)

        # Only add feedback buttons if there's a prediction and record ID
        if price_record_id is not None:
            keyboard = [
                [
                    InlineKeyboardButton("✅ Accurate", callback_data=f"feedback_accurate_{price_record_id}"),
                    InlineKeyboardButton("❌ Inaccurate", callback_data=f"feedback_inaccurate_{price_record_id}")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await self.bot.send_message(
                chat_id=chat_id,
                text=message,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
        else:
            await self.bot.send_message(
                chat_id=chat_id,
                text=message,
                parse_mode='HTML'
            )


    async def handle_prediction_feedback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle feedback on price predictions"""
        query = update.callback_query
        await query.answer()  # Acknowledge the button click

        try:
            feedback_type, record_id = query.data.split('_')[1:]  # feedback_accurate_id or feedback_inaccurate_id
            accuracy = 1.0 if feedback_type == 'accurate' else 0.0

            # Update prediction accuracy in database
            with app.app_context():
                success = PriceHistory.update_prediction_accuracy(int(record_id), accuracy)

                if success:
                    feedback_msg = "✅ Thank you for your feedback! This helps improve future predictions."
                else:
                    feedback_msg = "❌ Sorry, couldn't process your feedback. Please try again later."

            # Edit original message to reflect feedback
            await query.edit_message_reply_markup(reply_markup=None)  # Remove feedback buttons
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=feedback_msg
            )

        except Exception as e:
            logger.error(f"Error processing prediction feedback: {str(e)}")
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="❌ Sorry, there was an error processing your feedback."
            )

    def _format_price_message(self, price_data: dict, prediction_data: dict | None = None) -> str:
        """Format price alert message with prediction information and recommendations"""
        message = price_data.get('message', '')

        if prediction_data and prediction_data.get('short_term_prediction'):
            message += f"\n\n🔮 Next Hour Price Prediction:\n"
            message += f"• Current price: {price_data.get('price', 'N/A')}¢\n"
            message += f"• Predicted: {prediction_data['short_term_prediction']:.1f}¢\n"
            message += f"• Range: {prediction_data['next_hour_range']['low']}¢ - {prediction_data['next_hour_range']['high']}¢\n"
            message += f"• Confidence: {prediction_data['confidence']}%\n"
            message += f"• Trend: {prediction_data['trend']}\n\n"

            # Add the specific recommendation
            message += prediction_data.get('recommendation', '')

            message += "\n📊 Help improve predictions!\n"
            message += "Please rate this prediction's accuracy using the buttons below.\n"

        return message

    async def run_webhook(self):
        """Start the bot in webhook mode"""
        try:
            await self.setup_webhook()
            logger.info("Starting the bot in webhook mode...")

            await self.application.run_webhook(
                listen="0.0.0.0",
                port=80,  # Use port 80 for external access
                webhook_url=f"{self.webhook_url}{self.webhook_path}",
                url_path=self.webhook_path.lstrip('/'),
                drop_pending_updates=True
            )
        except Exception as e:
            logger.error(f"Error running webhook: {str(e)}")
            raise

    def get_recommendation(self, current_price: float, predicted_price: float, trend: str, confidence: float) -> str:
        """Generate specific recommendations based on price predictions"""
        price_diff = predicted_price - current_price
        percent_change = (price_diff / current_price) * 100

        recommendation = "🎯 Next Hour Recommendation:\n"

        if confidence < 50:
            recommendation += "⚠️ Low prediction confidence. Monitor prices closely.\n"
            return recommendation

        if percent_change > 10 and confidence >= 70:
            recommendation += "⚡ URGENT: Consider immediate power usage!\n"
            recommendation += "• Prices expected to rise significantly\n"
            recommendation += "• Recommended actions:\n"
            recommendation += "  - Run major appliances now\n"
            recommendation += "  - Charge electric vehicles\n"
            recommendation += "  - Complete energy-intensive tasks\n"
        elif percent_change > 5:
            recommendation += "⏰ Consider using power in the next 30 minutes\n"
            recommendation += "• Moderate price increase expected\n"
        elif percent_change < -10 and confidence >= 70:
            recommendation += "⏳ Consider delaying power usage\n"
            recommendation += "• Significant price drop expected\n"
            recommendation += "• Wait if possible for:\n"
            recommendation += "  - Laundry and dishes\n"
            recommendation += "  - EV charging\n"
            recommendation += "  - Air conditioning adjustments\n"
        elif percent_change < -5:
            recommendation += "💡 Slight price decrease expected\n"
            recommendation += "• Consider minor delays in power usage\n"
        else:
            recommendation += "✅ Stable prices expected\n"
            recommendation += "• Proceed with normal power usage\n"

        return recommendation


if __name__ == '__main__':
    try:
        bot = EnergyPriceBot()
        asyncio.run(bot.run_webhook())
    except Exception as e:
        logger.critical(f"Bot failed to start: {str(e)}")
        raise