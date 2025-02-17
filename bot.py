from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler
import asyncio
import logging
from datetime import datetime
import requests
from config import TELEGRAM_BOT_TOKEN, HEALTH_CHECK_URL, MIN_RATE
from price_monitor import PriceMonitor
from zoneinfo import ZoneInfo
from models import PriceHistory
from app import app

logger = logging.getLogger(__name__)

class EnergyPriceBot:
    def __init__(self):
        self.application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        self.bot = self.application.bot
        self.setup_handlers()

    def setup_handlers(self):
        """Set up command handlers for the bot"""
        self.application.add_handler(CommandHandler("start", self.cmd_start))
        self.application.add_handler(CommandHandler("help", self.cmd_help))
        self.application.add_handler(CommandHandler("start_monitoring", self.cmd_start_monitoring))
        self.application.add_handler(CommandHandler("stop_monitoring", self.cmd_stop_monitoring))
        self.application.add_handler(CommandHandler("check_price", self.cmd_check_price))
        self.application.add_handler(CommandHandler("status", self.cmd_status))
        # Add feedback handler
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
            await self.send_price_alert(update.effective_chat.id, five_min_data)

            hourly_data = await PriceMonitor.check_hourly_price()
            await self.send_price_alert(update.effective_chat.id, hourly_data)

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
        """Format price alert message with prediction information"""
        message = price_data.get('message', '')

        if prediction_data and prediction_data.get('short_term_prediction'):
            message += f"\n\n🔮 Price Prediction:\n"
            message += f"• Next hour: {prediction_data['short_term_prediction']:.1f}¢\n"
            message += f"• Confidence: {prediction_data['confidence']}%\n"
            message += f"• Trend: {prediction_data['trend']}\n\n"
            message += "Please provide feedback on this prediction's accuracy!"

        return message


    def run(self):
        """Start the bot"""
        logger.info("Starting the bot...")
        self.application.run_polling()

if __name__ == '__main__':
    bot = EnergyPriceBot()
    bot.run()