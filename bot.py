from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, ContextTypes
import asyncio
import logging
from datetime import datetime
import requests

from config import TELEGRAM_BOT_TOKEN, HEALTH_CHECK_URL, MIN_RATE
from price_monitor import PriceMonitor

logger = logging.getLogger(__name__)

class EnergyPriceBot:
    def __init__(self):
        self.application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        self.setup_handlers()

    def setup_handlers(self):
        """Set up command handlers for the bot"""
        self.application.add_handler(CommandHandler("start", self.cmd_start))
        self.application.add_handler(CommandHandler("help", self.cmd_help))
        self.application.add_handler(CommandHandler("start_monitoring", self.cmd_start_monitoring))
        self.application.add_handler(CommandHandler("stop_monitoring", self.cmd_stop_monitoring))
        self.application.add_handler(CommandHandler("check_price", self.cmd_check_price))
        self.application.add_handler(CommandHandler("status", self.cmd_status))

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
            await context.bot.send_message(
                chat_id=context.job.chat_id,
                text=five_min_data['message']
            )

            # Check hourly price
            hourly_data = await PriceMonitor.check_hourly_price()
            await context.bot.send_message(
                chat_id=context.job.chat_id,
                text=hourly_data['message']
            )

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

            five_min_data = await PriceMonitor.check_five_min_price()
            await update.message.reply_text(five_min_data['message'])

            hourly_data = await PriceMonitor.check_hourly_price()
            await update.message.reply_text(hourly_data['message'])

        except Exception as e:
            await update.message.reply_text(f"❌ Error checking prices: {str(e)}")

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

    def run(self):
        """Start the bot"""
        logger.info("Starting the bot...")
        self.application.run_polling()

if __name__ == '__main__':
    bot = EnergyPriceBot()
    bot.run()