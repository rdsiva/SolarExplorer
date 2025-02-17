import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler, ConversationHandler, MessageHandler, filters
import requests
from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo
from price_monitor import PriceMonitor
from config import TELEGRAM_BOT_TOKEN
from models import PriceHistory, UserPreferences
from app import app, db
from price_prediction import price_predictor

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Conversation states
THRESHOLD = 1

# Add the escape function at the top of the file, after imports
def escape_markdown(text):
    """Escape special characters for MarkdownV2 format"""
    characters_to_escape = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in characters_to_escape:
        text = text.replace(char, f'\\{char}')
    return text

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /start is issued."""
    chat_id = update.effective_chat.id

    # Create default preferences for new user
    with app.app_context():
        UserPreferences.create_or_update(str(chat_id))

    welcome_message = (
        f"👋 Welcome to the Energy Price Monitor Bot!\n\n"
        f"Your Chat ID is: {chat_id}\n"
        "Available commands:\n"
        "/check - Check current prices\n"
        "/threshold - Set custom price alert threshold\n"
        "/preferences - Show your current preferences\n"
        "/help - Show this help message"
    )
    await update.message.reply_text(welcome_message)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /help is issued."""
    await start(update, context)

async def show_preferences(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show current user preferences"""
    chat_id = update.effective_chat.id

    with app.app_context():
        prefs = UserPreferences.get_user_preferences(str(chat_id))
        if prefs:
            message = (
                "🔧 Your Current Preferences:\n\n"
                f"Price Threshold: {prefs.price_threshold}¢\n"
                f"Alert Frequency: {prefs.alert_frequency}\n"
                f"Active: {'Yes' if prefs.is_active else 'No'}\n"
            )
            if prefs.start_time and prefs.end_time:
                message += f"Alert Window: {prefs.start_time.strftime('%I:%M %p')} - {prefs.end_time.strftime('%I:%M %p')}"
        else:
            message = "❌ No preferences found. Use /start to set up your preferences."

    await update.message.reply_text(message)

async def set_threshold(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start the threshold setting conversation."""
    await update.message.reply_text(
        "Please enter your desired price threshold in cents (e.g., 3.5 for 3.5¢)\n"
        "This is the price above which you'll receive alerts."
    )
    return THRESHOLD

async def save_threshold(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Save the user's price threshold."""
    try:
        threshold = float(update.message.text)
        if threshold <= 0:
            raise ValueError("Threshold must be positive")

        chat_id = update.effective_chat.id
        with app.app_context():
            prefs = UserPreferences.create_or_update(str(chat_id), price_threshold=threshold)

        await update.message.reply_text(
            f"✅ Price threshold set to {threshold}¢\n"
            "You'll receive alerts when prices exceed this threshold."
        )
        return ConversationHandler.END

    except ValueError:
        await update.message.reply_text(
            "❌ Please enter a valid number (e.g., 3.5)\n"
            "Try again or use /cancel to stop."
        )
        return THRESHOLD

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel the current conversation."""
    await update.message.reply_text("Operation cancelled.")
    return ConversationHandler.END

@app.route('/')
async def check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check current prices with ML predictions and pattern analysis"""
    try:
        chat_id = update.effective_chat.id
        await update.message.reply_text("🔍 Checking current prices with ML analysis...")

        # Get price data
        hourly_data = await PriceMonitor.check_hourly_price()
        five_min_data = await PriceMonitor.check_five_min_price()

        # Safely get current price, defaulting to None if not available
        try:
            current_price = float(hourly_data.get('price', 0)) if hourly_data.get('price') != 'N/A' else None
        except (ValueError, TypeError):
            current_price = None

        if current_price is None:
            await update.message.reply_text(
                escape_markdown("❌ Error: Current price data is not available. Please try again later."),
                parse_mode="MarkdownV2"
            )
            return

        # Get user's custom threshold
        with app.app_context():
            prefs = UserPreferences.get_user_preferences(str(chat_id))
            threshold = prefs.price_threshold if prefs else 3.0

        # Generate ML-based prediction with pattern analysis
        prediction = await price_predictor.predict(current_price)

        if not prediction:
            await update.message.reply_text(
                escape_markdown("❌ Error generating price prediction. Please try again later."),
                parse_mode="MarkdownV2"
            )
            return

        predicted_price = prediction['predicted_price']
        confidence = prediction['confidence']
        prediction_range = prediction['range']
        patterns = prediction.get('patterns', {})

        # Store prediction in database
        price_record = None
        with app.app_context():
            try:
                price_record = PriceHistory(
                    hourly_price=current_price,
                    predicted_price=predicted_price,
                    prediction_confidence=confidence,
                    provider="ComEd"
                )
                db.session.add(price_record)
                db.session.commit()
                logger.info(f"Stored ML prediction record with ID: {price_record.id}")
            except Exception as db_error:
                logger.error(f"Database error while storing prediction: {str(db_error)}")
                db.session.rollback()

        # Format message with ML predictions and patterns
        message_parts = []
        message_parts.append("📊 Current Energy Prices:\n")
        message_parts.append(f"5\\-min price: {escape_markdown(str(five_min_data.get('price', 'N/A')))}")
        message_parts.append(f"Hourly price: {escape_markdown(f'{current_price:.2f}')}")
        message_parts.append(f"Alert Threshold: {escape_markdown(f'{threshold:.1f}')}")

        # Add pattern analysis section
        message_parts.append("\n🔍 Pattern Analysis:")
        if patterns:
            pattern_emojis = {
                'spike': '⚡',
                'dip': '📉',
                'trend': '📈',
                'cycle': '🔄'
            }
            for pattern, detected in patterns.items():
                if detected:
                    message_parts.append(f"{pattern_emojis.get(pattern, '•')} {pattern.title()} pattern detected")
        else:
            message_parts.append("No significant patterns detected")

        # Add smart price alert based on ML prediction
        if predicted_price > threshold:
            message_parts.append("\n⚠️ Warning: ML model predicts price will exceed your threshold\\!")
            message_parts.append(f"Expected to reach {escape_markdown(f'{predicted_price:.1f}')}¢ \\(Confidence: {escape_markdown(str(int(confidence)))}%\\)")
        elif current_price > threshold:
            message_parts.append("\n🔴 Currently Above Threshold")
        else:
            message_parts.append("\n🟢 Below Threshold")

        message_parts.append(f"Trend: {prediction['trend'].capitalize()}")

        # Add ML prediction section
        message_parts.append("\n🤖 ML Price Prediction:")
        message_parts.append(f"Next hour: {escape_markdown(f'{predicted_price:.1f}')}¢")
        # Fix the dictionary access in the f-string
        low_price = escape_markdown(f"{prediction_range['low']:.1f}")
        high_price = escape_markdown(f"{prediction_range['high']:.1f}")
        message_parts.append(f"Range: {low_price}¢ \\- {high_price}¢")
        message_parts.append(f"Confidence: {escape_markdown(str(int(confidence)))}%")

        # Add timestamp
        cst_time = datetime.now(ZoneInfo("America/Chicago"))
        message_parts.append(f"\n⏰ Last Updated: {escape_markdown(cst_time.strftime('%Y-%m-%d %I:%M %p %Z'))}")

        # Add dashboard link with proper MarkdownV2 escaping
        dashboard_url = "https://" + os.environ.get("REPL_SLUG", "0-0-0-0") + ".repl.co/dashboard/" + str(chat_id)
        message_parts.append(f"\n\n📈 [View Your Analytics Dashboard]({escape_markdown(dashboard_url)})")

        # Combine all parts with proper line endings
        message = "\n".join(message_parts)

        # Add feedback request if prediction was stored
        if price_record and price_record.id:
            message += "\n\n🎯 Help us improve\\! Was this prediction accurate?"
            keyboard = [[
                InlineKeyboardButton("✅ Good", callback_data=f"feedback_accurate_{price_record.id}"),
                InlineKeyboardButton("❌ Poor", callback_data=f"feedback_inaccurate_{price_record.id}")
            ]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                text=message,
                parse_mode="MarkdownV2",
                reply_markup=reply_markup,
                disable_web_page_preview=True
            )
        else:
            await update.message.reply_text(
                text=message,
                parse_mode="MarkdownV2",
                disable_web_page_preview=True
            )

    except Exception as e:
        error_msg = f"❌ Error checking prices: {str(e)}"
        logger.error(error_msg, exc_info=True)
        await update.message.reply_text(
            text=escape_markdown(error_msg),
            parse_mode="MarkdownV2"
        )

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
                feedback_msg = "✅ Thank you for your feedback\\!" if success else "❌ Could not process feedback\\."
                logger.info(f"Feedback processing {'successful' if success else 'failed'}")
            except Exception as db_error:
                logger.error(f"Database error while processing feedback: {str(db_error)}", exc_info=True)
                success = False
                feedback_msg = "❌ Error processing feedback\\."

        await query.edit_message_reply_markup(reply_markup=None)
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=escape_markdown(feedback_msg),
            parse_mode="MarkdownV2"
        )
        logger.info("Feedback confirmation sent to user")

    except Exception as e:
        logger.error(f"Error processing prediction feedback: {str(e)}", exc_info=True)
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=escape_markdown("❌ Sorry, there was an error processing your feedback."),
            parse_mode="MarkdownV2"
        )

def main():
    """Start the bot."""
    try:
        # Create the Application
        application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

        # Add conversation handler for setting threshold
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler('threshold', set_threshold)],
            states={
                THRESHOLD: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_threshold)],
            },
            fallbacks=[CommandHandler('cancel', cancel)],
        )

        # Add handlers with updated command names
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("check", check))
        application.add_handler(CommandHandler("preferences", show_preferences))
        application.add_handler(conv_handler)
        application.add_handler(CallbackQueryHandler(handle_prediction_feedback))

        # Start the bot
        logger.info("Starting bot...")
        application.run_polling(drop_pending_updates=True)

    except Exception as e:
        logger.error(f"Error starting bot: {e}")
        raise

if __name__ == '__main__':
    main()