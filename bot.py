import os
import logging
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler
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
        """Initialize the bot"""
        self.bot_token = TELEGRAM_BOT_TOKEN
        if not self.bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN is not set")

        logger.info("Initializing bot with token: %s...", self.bot_token[:8])
        self.application = Application.builder().token(self.bot_token).build()
        self.bot = self.application.bot

    def _setup_handlers(self):
        """Set up command handlers for the bot"""
        try:
            logger.info("Setting up command handlers")
            self.application.add_handler(CommandHandler("start", self.cmd_start))
            self.application.add_handler(CommandHandler("help", self.cmd_help))
            self.application.add_handler(CommandHandler("check_price", self.cmd_check_price))
            self.application.add_handler(CommandHandler("status", self.cmd_status))
            self.application.add_handler(CallbackQueryHandler(self.handle_prediction_feedback))
            logger.info("Command handlers setup completed")
        except Exception as e:
            logger.error(f"Error setting up handlers: {str(e)}")
            raise

    async def start(self):
        """Start the bot"""
        self._setup_handlers()
        await self.application.initialize()
        await self.application.start()
        await self.application.run_polling(drop_pending_updates=True)

    async def stop(self):
        """Stop the bot"""
        if self.application.running:
            await self.application.stop()
            await self.application.shutdown()

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle the /start command"""
        try:
            chat_id = update.effective_chat.id
            logger.info(f"Received /start command from chat_id: {chat_id}")
            welcome_message = (
                f"👋 Welcome to the Energy Price Monitor Bot!\n\n"
                f"Your Chat ID is: {chat_id}\n"
                "Please save this ID in your .env file as TELEGRAM_CHAT_ID\n\n"
                f"I can help you track energy prices and notify you when they fall below "
                f"{MIN_RATE} cents.\n\n"
                "Available commands:\n"
                "/check_price - Check current prices\n"
                "/status - Check monitoring status\n"
                "/help - Show this help message"
            )
            await update.message.reply_text(welcome_message)
            logger.info(f"Sent welcome message to chat_id: {chat_id}")
        except Exception as e:
            logger.error(f"Error in /start command: {str(e)}")
            await update.message.reply_text("Sorry, there was an error processing your command.")

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

    async def cmd_check_price(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Check current prices on demand with predictions"""
        try:
            chat_id = update.effective_chat.id
            logger.info(f"Processing /check_price command for chat_id: {chat_id}")

            await update.message.reply_text("🔍 Checking current prices...")

            # Get price data
            hourly_data = await PriceMonitor.check_hourly_price()
            five_min_data = await PriceMonitor.check_five_min_price()

            logger.debug(f"Hourly data: {hourly_data}")
            logger.debug(f"5-min data: {five_min_data}")

            current_price = float(hourly_data.get('price', 0))

            # Generate prediction data
            predicted_price = round(current_price * 1.1, 1)
            prediction_data = {
                'short_term_prediction': predicted_price,
                'confidence': 75,
                'trend': 'rising' if predicted_price > current_price else 'falling',
                'next_hour_range': {
                    'low': round(current_price * 0.9, 1),
                    'high': round(current_price * 1.2, 1)
                }
            }

            # Format the combined price data
            price_data = {
                'five_min_data': five_min_data,
                'hourly_data': hourly_data
            }

            # Send alert with feedback buttons
            await self.send_price_alert(chat_id, price_data, prediction_data)
            logger.info(f"Price check completed for chat_id: {chat_id}")

        except Exception as e:
            error_msg = f"❌ Error checking prices: {str(e)}"
            logger.error(error_msg)
            await update.message.reply_text(error_msg)

    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Check the monitoring status"""
        api_status = "✅ Online" if await self.check_api_health() else "❌ Offline"
        status_message = (
            "📊 System Status\n"
            f"API Status: {api_status}\n"
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
                    hourly_price=float(price_data.get('hourly_data', {}).get('price', 0)),
                    predicted_price=prediction_data['short_term_prediction'],
                    prediction_confidence=prediction_data['confidence']
                )
                price_record_id = price_record.id

        message = self._format_price_message(price_data, prediction_data)
        logger.debug(f"Formatted message: {message}")

        try:
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
            logger.info(f"Successfully sent price alert to chat_id: {chat_id}")
        except Exception as e:
            logger.error(f"Error sending price alert: {str(e)}")
            raise

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
        day_ahead = hourly_data.get('day_ahead_price', 0)
        price_diff = current_price - day_ahead if isinstance(day_ahead, (int, float)) else 0

        if price_diff <= -0.5:
            status_emoji = "🟢"  # Green circle for good prices
            price_status = "GOOD TIME TO USE POWER"
        elif price_diff >= 1.0:
            status_emoji = "🔴"  # Red circle for price spikes
            price_status = "HIGH PRICE ALERT"
        else:
            status_emoji = "🟡"  # Yellow circle for normal prices
            price_status = "NORMAL PRICE LEVELS"

        message = f"{status_emoji} <b>Energy Price Alert: {price_status}</b>\n\n"

        # Add current prices section with full timestamps
        message += "📊 <b>Current Prices:</b>\n"
        message += f"• 5-min price: {five_min_data.get('price', 'N/A')}¢\n"
        message += f"• Hourly price: {hourly_data.get('price', 'N/A')}¢\n"
        if day_ahead and day_ahead != 'N/A':
            message += f"• Day ahead: {day_ahead}¢\n"
        message += "\n"

        # Add analysis section with trends
        message += "📈 <b>Analysis:</b>\n"
        message += f"• Trend: {five_min_data.get('trend', 'unknown').capitalize()}\n"
        message += f"• vs Average: {price_diff:+.1f}¢\n"
        if 'price_range' in hourly_data:
            range_data = hourly_data['price_range']
            message += f"• Day Range: {range_data['min']}¢ - {range_data['max']}¢\n\n"

        # Add prediction section if available
        if prediction_data and prediction_data.get('short_term_prediction'):
            message += "🔮 <b>Price Prediction:</b>\n"
            message += f"• Next hour: {prediction_data['short_term_prediction']:.1f}¢\n"
            message += f"• Range: {prediction_data['next_hour_range']['low']:.1f}¢ - {prediction_data['next_hour_range']['high']:.1f}¢\n"
            message += f"• Confidence: {prediction_data['confidence']}%\n"
            message += f"• Trend: {prediction_data['trend'].capitalize()}\n\n"

        # Add timestamp in CST
        cst_time = datetime.now(ZoneInfo("America/Chicago"))
        message += f"\n⏰ Last Updated: {cst_time.strftime('%Y-%m-%d %I:%M %p %Z')}"

        # Add feedback request if there's a prediction
        if prediction_data and prediction_data.get('short_term_prediction'):
            message += "\n🎯 <b>Help us improve!</b>\n"
            message += "Please rate this prediction's accuracy using the buttons below.\n"

        return message

if __name__ == '__main__':
    bot = EnergyPriceBot()
    try:
        import asyncio
        asyncio.run(bot.start())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.critical(f"Bot failed to start: {str(e)}")
        raise