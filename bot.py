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
        """Initialize the bot with polling configuration"""
        self.application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        self.bot = self.application.bot
        logger.info("Initializing bot in polling mode")
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
            # Check both 5-minute and hourly prices
            five_min_data = await PriceMonitor.check_five_min_price()
            hourly_data = await PriceMonitor.check_hourly_price()

            # Format the combined price data
            price_data = {
                'five_min_data': five_min_data,
                'hourly_data': hourly_data
            }

            # Generate prediction data based on hourly price
            current_price = float(hourly_data.get('price', 0))
            predicted_price = round(current_price * 1.1, 1)  # Example prediction
            prediction_data = {
                'short_term_prediction': predicted_price,
                'confidence': 75,
                'trend': 'rising' if predicted_price > current_price else 'falling',
                'next_hour_range': {
                    'low': round(current_price * 0.9, 1),
                    'high': round(current_price * 1.2, 1)
                }
            }

            # Send alert with all data
            await self.send_price_alert(context.job.chat_id, price_data, prediction_data)

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
            "✅ Price monitoring started! You'll receive hourly updates and predictions "
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
        """Check current prices on demand with predictions"""
        try:
            await update.message.reply_text("🔍 Checking current prices...")

            hourly_data = await PriceMonitor.check_hourly_price()
            current_price = float(hourly_data.get('price', 0))

            # Generate prediction data
            predicted_price = round(current_price * 1.1, 1)  # Example prediction
            confidence = 75
            trend = 'rising' if predicted_price > current_price else 'falling'

            prediction_data = {
                'short_term_prediction': predicted_price,
                'confidence': confidence,
                'trend': trend,
                'next_hour_range': {
                    'low': round(current_price * 0.9, 1),
                    'high': round(current_price * 1.2, 1)
                }
            }

            # Store prediction in database and send alert with feedback buttons
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

    async def send_price_alert(self, chat_id: int, price_data: dict, prediction_data: dict | None = None):
        """Send price alert with feedback buttons"""
        price_record_id = None

        # Store prediction in database if available
        if prediction_data and prediction_data.get('short_term_prediction'):
            with app.app_context():
                price_record = PriceHistory.add_price_data(
                    hourly_price=float(price_data.get('hourly_data').get('price', 0)),
                    predicted_price=prediction_data['short_term_prediction'],
                    prediction_confidence=prediction_data['confidence']
                )
                price_record_id = price_record.id

        # Format message with price and prediction data
        message = self._format_price_message(price_data, prediction_data)

        # Add feedback buttons if there's a prediction
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
        await query.answer()

        try:
            feedback_type, record_id = query.data.split('_')[1:]
            accuracy = 1.0 if feedback_type == 'accurate' else 0.0

            with app.app_context():
                success = PriceHistory.update_prediction_accuracy(int(record_id), accuracy)
                feedback_msg = "✅ Thank you for your feedback!" if success else "❌ Couldn't process feedback"

            await query.edit_message_reply_markup(reply_markup=None)
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
        """Format price alert message with detailed price information and prediction"""
        five_min_data = price_data.get('five_min_data', {})
        hourly_data = price_data.get('hourly_data', {})

        # Format the header based on price trend
        current_price = float(hourly_data.get('price', 0))
        message = f"🔔 Energy Price Alert\n\n"

        # Add current prices section
        message += "📊 Current Prices:\n"
        message += f"• 5-min price: {five_min_data.get('price', 'N/A')}¢\n"
        message += f"• Hourly price: {hourly_data.get('price', 'N/A')}¢\n"
        if hourly_data.get('day_ahead_price'):
            message += f"• Day ahead: {hourly_data.get('day_ahead_price')}¢\n"
        message += "\n"

        # Add prediction section if available
        if prediction_data and prediction_data.get('short_term_prediction'):
            message += "🔮 Next Hour Prediction:\n"
            message += f"• Predicted: {prediction_data['short_term_prediction']:.1f}¢\n"
            message += f"• Range: {prediction_data['next_hour_range']['low']}¢ - {prediction_data['next_hour_range']['high']}¢\n"
            message += f"• Confidence: {prediction_data['confidence']}%\n"
            message += f"• Trend: {prediction_data['trend'].capitalize()}\n\n"

            # Add specific recommendation based on prediction
            if prediction_data['trend'] == 'rising' and prediction_data['confidence'] >= 70:
                message += "⚠️ Price expected to rise - Consider using power now\n"
            elif prediction_data['trend'] == 'falling' and prediction_data['confidence'] >= 70:
                message += "💡 Price expected to fall - Consider delaying usage\n"

            message += "\n🎯 Help improve predictions!\n"
            message += "Please rate this prediction's accuracy using the buttons below.\n"

        # Add timestamp
        cst_time = datetime.now(ZoneInfo("America/Chicago"))
        message += f"\n⏰ Last Updated: {cst_time.strftime('%I:%M %p')} CST"

        return message

    async def run(self):
        """Start the bot in polling mode"""
        try:
            logger.info("Starting the bot in polling mode...")
            await self.application.initialize()
            await self.application.start()
            await self.application.run_polling(allowed_updates=Update.ALL_TYPES)
        except Exception as e:
            logger.error(f"Error running bot: {str(e)}")
            raise

if __name__ == '__main__':
    try:
        bot = EnergyPriceBot()
        asyncio.run(bot.run())
    except Exception as e:
        logger.critical(f"Bot failed to start: {str(e)}")
        raise