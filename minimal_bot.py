import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from price_monitor import PriceMonitor
from config import TELEGRAM_BOT_TOKEN
from models import PriceHistory
from app import app, db
import numpy as np

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Get chat ID from environment
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
if not TELEGRAM_CHAT_ID:
    raise ValueError("TELEGRAM_CHAT_ID environment variable is not set")

def calculate_prediction(current_price: float, hourly_data: dict) -> tuple[float, int]:
    """Calculate price prediction using historical data and trends"""
    try:
        day_ahead_price = float(hourly_data.get('day_ahead_price', current_price))
        trend = hourly_data.get('trend', 'stable')

        with app.app_context():
            # Get recent price history
            recent_prices = PriceHistory.query.order_by(
                PriceHistory.timestamp.desc()
            ).limit(24).all()

            if recent_prices:
                # Calculate trend-based adjustment
                trend_factor = 1.0
                if trend == 'rising':
                    trend_factor = 1.05
                elif trend == 'falling':
                    trend_factor = 0.95

                # Calculate weighted average of recent prices
                weights = np.array([0.8 ** i for i in range(len(recent_prices))])
                weights = weights / weights.sum()
                historical_prices = np.array([p.hourly_price for p in recent_prices])
                weighted_historical = np.average(historical_prices, weights=weights)

                # Combine current price, day-ahead price, and historical data
                prediction = (
                    0.4 * current_price + 
                    0.3 * day_ahead_price + 
                    0.3 * weighted_historical
                ) * trend_factor

                # Calculate confidence based on prediction accuracy history
                accurate_predictions = len([p for p in recent_prices if p.prediction_accuracy == 1.0])
                total_predictions = len([p for p in recent_prices if p.prediction_accuracy is not None])
                confidence = int((accurate_predictions / total_predictions * 100) if total_predictions > 0 else 75)

                return round(prediction, 1), confidence

    except Exception as e:
        logger.error(f"Error calculating prediction: {str(e)}", exc_info=True)

    # Fallback to simple prediction if anything fails
    return round(current_price * 1.05, 1), 60

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /start is issued."""
    chat_id = update.effective_chat.id
    welcome_message = (
        f"👋 Welcome to the Energy Price Monitor Bot!\n\n"
        f"Your Chat ID is: {chat_id}\n"
        "Available commands:\n"
        "/check_price - Check current prices\n"
        "/help - Show this help message"
    )
    await update.message.reply_text(welcome_message)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /help is issued."""
    await start(update, context)

async def handle_prediction_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle feedback on price predictions"""
    query = update.callback_query
    await query.answer()

    try:
        logger.info(f"Received feedback callback: {query.data}")
        feedback_type, record_id = query.data.split('_')[1:]
        accuracy = 1.0 if feedback_type == 'accurate' else 0.0

        logger.info(f"Processing feedback for record {record_id} with accuracy {accuracy}")

        with app.app_context():
            try:
                success = PriceHistory.update_prediction_accuracy(int(record_id), accuracy)
                feedback_msg = "✅ Thank you for your feedback!" if success else "❌ Couldn't process feedback"
                logger.info(f"Feedback processing {'successful' if success else 'failed'}")
            except Exception as db_error:
                logger.error(f"Database error while processing feedback: {str(db_error)}", exc_info=True)
                success = False
                feedback_msg = "❌ Error processing feedback"

        await query.edit_message_reply_markup(reply_markup=None)
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=feedback_msg
        )
        logger.info("Feedback confirmation sent to user")

    except Exception as e:
        logger.error(f"Error processing prediction feedback: {str(e)}", exc_info=True)
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="❌ Sorry, there was an error processing your feedback."
        )

async def check_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check current prices when the command /check_price is issued."""
    try:
        await update.message.reply_text("🔍 Checking current prices...")

        # Get price data
        hourly_data = await PriceMonitor.check_hourly_price()
        five_min_data = await PriceMonitor.check_five_min_price()

        # Generate a simple prediction (we'll improve this later)
        current_price = float(hourly_data.get('price', 0))
        predicted_price, confidence = calculate_prediction(current_price, hourly_data)


        # Store prediction in database
        price_record = None
        with app.app_context():
            try:
                price_record = PriceHistory(
                    hourly_price=current_price,
                    predicted_price=predicted_price,
                    prediction_confidence=confidence
                )
                db.session.add(price_record)
                db.session.commit()
                logger.info(f"Stored prediction record with ID: {price_record.id}")
            except Exception as db_error:
                logger.error(f"Database error while storing prediction: {str(db_error)}", exc_info=True)
                db.session.rollback()

        # Format message with prediction
        message = "📊 Current Energy Prices:\n\n"
        message += f"5-min price: {five_min_data.get('price', 'N/A')}¢\n"
        message += f"Hourly price: {hourly_data.get('price', 'N/A')}¢\n"
        message += f"Trend: {hourly_data.get('trend', 'unknown').capitalize()}\n\n"

        # Add prediction section
        message += "🔮 Price Prediction:\n"
        message += f"Next hour: {predicted_price}¢\n"
        message += f"Confidence: {confidence}%\n\n"

        # Add timestamp
        cst_time = datetime.now(ZoneInfo("America/Chicago"))
        message += f"⏰ Last Updated: {cst_time.strftime('%Y-%m-%d %I:%M %p %Z')}"

        # Add feedback request and buttons if prediction was stored successfully
        if price_record and price_record.id:
            message += "\n\n🎯 Help us improve! Was this prediction accurate?"
            keyboard = [
                [
                    InlineKeyboardButton("✅ Accurate", callback_data=f"feedback_accurate_{price_record.id}"),
                    InlineKeyboardButton("❌ Inaccurate", callback_data=f"feedback_inaccurate_{price_record.id}")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(message, reply_markup=reply_markup)
        else:
            await update.message.reply_text(message)

    except Exception as e:
        error_msg = f"❌ Error checking prices: {str(e)}"
        logger.error(error_msg, exc_info=True)
        await update.message.reply_text(error_msg)

def main():
    """Start the bot."""
    try:
        # Create the Application
        application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

        # Add handlers
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("check_price", check_price))
        application.add_handler(CallbackQueryHandler(handle_prediction_feedback))

        # Start the bot
        logger.info("Starting bot...")
        application.run_polling(drop_pending_updates=True)

    except Exception as e:
        logger.error(f"Error starting bot: {e}")
        raise

if __name__ == '__main__':
    main()