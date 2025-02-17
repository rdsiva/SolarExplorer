import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler
from datetime import datetime
from zoneinfo import ZoneInfo
from price_monitor import PriceMonitor
from models import PriceHistory
from app import app, db

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Get bot token from environment
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN environment variable is not set")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /start is issued."""
    chat_id = update.effective_chat.id
    welcome_message = (
        f"👋 Welcome to the Simple Energy Price Monitor!\n\n"
        f"Your Chat ID is: {chat_id}\n\n"
        "Available commands:\n"
        "/check - Check current prices\n"
        "/help - Show this help message"
    )
    await update.message.reply_text(welcome_message)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send help message"""
    await start(update, context)

async def handle_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process user feedback on predictions"""
    query = update.callback_query
    await query.answer()

    try:
        # Extract feedback data
        feedback_type, record_id = query.data.split('_')[1:]
        accuracy = 1.0 if feedback_type == 'accurate' else 0.0
        
        # Update database
        with app.app_context():
            record = PriceHistory.query.get(int(record_id))
            if record:
                record.prediction_accuracy = accuracy
                db.session.commit()
                message = "✅ Thanks for your feedback!"
            else:
                message = "❌ Could not process feedback"
                
        await query.edit_message_reply_markup(reply_markup=None)
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=message
        )
        
    except Exception as e:
        logger.error(f"Feedback error: {str(e)}", exc_info=True)
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="❌ Error processing feedback"
        )

async def check_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check and display current prices with basic prediction"""
    try:
        await update.message.reply_text("🔍 Checking prices...")
        
        # Get price data
        hourly_data = await PriceMonitor.check_hourly_price()
        current_price = float(hourly_data.get('price', 0))
        
        # Simple prediction: 5% change based on trend
        trend = hourly_data.get('trend', 'stable')
        if trend == 'rising':
            predicted_price = round(current_price * 1.05, 1)
        elif trend == 'falling':
            predicted_price = round(current_price * 0.95, 1)
        else:
            predicted_price = round(current_price, 1)
        
        # Store in database
        price_record = None
        with app.app_context():
            try:
                price_record = PriceHistory(
                    hourly_price=current_price,
                    predicted_price=predicted_price,
                    prediction_confidence=70  # Fixed confidence for now
                )
                db.session.add(price_record)
                db.session.commit()
            except Exception as e:
                logger.error(f"Database error: {str(e)}", exc_info=True)
                db.session.rollback()
        
        # Format message
        message = (
            "📊 Energy Price Update\n\n"
            f"Current Price: {current_price}¢\n"
            f"Trend: {trend.capitalize()}\n"
            f"Predicted Next Hour: {predicted_price}¢\n\n"
            f"⏰ Updated: {datetime.now(ZoneInfo('America/Chicago')).strftime('%I:%M %p %Z')}"
        )
        
        # Add feedback buttons if prediction was stored
        if price_record and price_record.id:
            keyboard = [[
                InlineKeyboardButton("✅ Good", callback_data=f"feedback_accurate_{price_record.id}"),
                InlineKeyboardButton("❌ Poor", callback_data=f"feedback_inaccurate_{price_record.id}")
            ]]
            await update.message.reply_text(
                message,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await update.message.reply_text(message)
            
    except Exception as e:
        error_msg = f"❌ Error: {str(e)}"
        logger.error(error_msg, exc_info=True)
        await update.message.reply_text(error_msg)

def main():
    """Start the bot"""
    try:
        # Create application
        application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

        # Add handlers
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("check", check_price))
        application.add_handler(CallbackQueryHandler(handle_feedback))

        # Start polling
        logger.info("Starting bot...")
        application.run_polling(drop_pending_updates=True)
        
    except Exception as e:
        logger.error(f"Bot error: {str(e)}", exc_info=True)
        raise

if __name__ == '__main__':
    main()
