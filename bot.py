import os
import logging
import requests  # Add this import
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler
from config import TELEGRAM_BOT_TOKEN, HEALTH_CHECK_URL, MIN_RATE
from modules import ModuleManager, PriceMonitorModule, PatternAnalysisModule, MLPredictionModule
from datetime import datetime
from zoneinfo import ZoneInfo
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

        # Initialize module manager and register modules
        self.module_manager = ModuleManager()
        self._setup_modules()

    def _setup_modules(self):
        """Set up and register all available modules"""
        # Initialize modules
        self.price_module = PriceMonitorModule()  # Required module
        self.pattern_module = PatternAnalysisModule()  # Optional
        self.ml_module = MLPredictionModule()  # Optional

        # Register modules
        self.module_manager.register_module(self.price_module)
        self.module_manager.register_module(self.pattern_module)
        self.module_manager.register_module(self.ml_module)

        # Enable price monitoring by default (required)
        self.module_manager.enable_module("price_monitor")

    def _setup_handlers(self):
        """Set up command handlers for the bot"""
        try:
            logger.info("Setting up command handlers")
            self.application.add_handler(CommandHandler("start", self.cmd_start))
            self.application.add_handler(CommandHandler("help", self.cmd_help))
            self.application.add_handler(CommandHandler("check_price", self.cmd_check_price))
            self.application.add_handler(CommandHandler("status", self.cmd_status))
            self.application.add_handler(CommandHandler("modules", self.cmd_list_modules))
            self.application.add_handler(CommandHandler("enable", self.cmd_enable_module))
            self.application.add_handler(CommandHandler("disable", self.cmd_disable_module))
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
                "/modules - List available modules and their status\n"
                "/enable <module> - Enable a specific module\n"
                "/disable <module> - Disable a specific module\n"
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

    async def cmd_list_modules(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """List all available modules and their status"""
        try:
            modules = self.module_manager.get_all_modules()
            message = "📊 Available Modules:\n\n"

            for module in modules:
                status = "✅ Enabled" if module["enabled"] else "❌ Disabled"
                required = " (Required)" if module["name"] == "price_monitor" else ""
                message += f"• {module['name']}{required}: {status}\n"
                message += f"  Description: {module['description']}\n\n"

            message += "\nUse /enable <module> to enable or /disable <module> to disable a module"
            await update.message.reply_text(message)
        except Exception as e:
            logger.error(f"Error listing modules: {str(e)}")
            await update.message.reply_text("Sorry, there was an error listing the modules.")

    async def cmd_enable_module(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Enable a specific module"""
        try:
            if not context.args:
                await update.message.reply_text("Please specify a module name. Use /modules to see available modules.")
                return

            module_name = context.args[0].lower()
            if module_name == "price_monitor":
                await update.message.reply_text("The price monitoring module is required and always enabled.")
                return

            if self.module_manager.enable_module(module_name):
                await update.message.reply_text(f"✅ Module '{module_name}' has been enabled.")
            else:
                await update.message.reply_text(f"❌ Could not enable module '{module_name}'. Please check the module name.")
        except Exception as e:
            logger.error(f"Error enabling module: {str(e)}")
            await update.message.reply_text("Sorry, there was an error enabling the module.")

    async def cmd_disable_module(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Disable a specific module"""
        try:
            if not context.args:
                await update.message.reply_text("Please specify a module name. Use /modules to see available modules.")
                return

            module_name = context.args[0].lower()
            if module_name == "price_monitor":
                await update.message.reply_text("⚠️ The price monitoring module cannot be disabled as it is required.")
                return

            if self.module_manager.disable_module(module_name):
                await update.message.reply_text(f"✅ Module '{module_name}' has been disabled.")
            else:
                await update.message.reply_text(f"❌ Could not disable module '{module_name}'. Please check the module name.")
        except Exception as e:
            logger.error(f"Error disabling module: {str(e)}")
            await update.message.reply_text("Sorry, there was an error disabling the module.")

    async def cmd_check_price(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Check current prices with data from enabled modules"""
        try:
            chat_id = update.effective_chat.id
            logger.info(f"Processing /check_price command for chat_id: {chat_id}")

            await update.message.reply_text("🔍 Checking current prices...")

            # Process data through all enabled modules
            results = await self.module_manager.process_with_enabled_modules({})

            # Get notification data from enabled modules
            notification_data = await self.module_manager.get_notification_data()

            # Format and send the message
            message = self._format_price_message(results, notification_data)

            # Send alert with feedback buttons if ML module is enabled
            if "ml_prediction" in notification_data:
                keyboard = [
                    [
                        InlineKeyboardButton("✅ Accurate", callback_data="feedback_accurate"),
                        InlineKeyboardButton("❌ Inaccurate", callback_data="feedback_inaccurate")
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

            logger.info(f"Price check completed for chat_id: {chat_id}")

        except Exception as e:
            error_msg = f"❌ Error checking prices: {str(e)}"
            logger.error(error_msg)
            await update.message.reply_text(error_msg)

    def _format_price_message(self, results: dict, notification_data: dict) -> str:
        """Format price message with data from enabled modules"""
        message = "📊 Energy Price Update\n\n"

        # Price monitoring data (always present)
        price_data = notification_data.get("price_monitor", {})
        if price_data:
            message += f"Current Price: {price_data.get('current_price')}¢\n"
            message += f"Five-min Price: {price_data.get('five_min_price')}¢\n"
            message += f"Trend: {price_data.get('trend', 'unknown').capitalize()}\n\n"

        # Pattern analysis data (if enabled)
        pattern_data = notification_data.get("pattern_analysis")
        if pattern_data:
            message += "📈 Pattern Analysis:\n"
            message += f"• Current Trend: {pattern_data.get('current_trend', 'unknown').capitalize()}\n"
            message += f"• Volatility: {pattern_data.get('volatility', 0):.2f}\n\n"

        # ML predictions (if enabled)
        ml_data = notification_data.get("ml_prediction")
        if ml_data:
            message += "🔮 Price Prediction:\n"
            message += f"• Next Hour: {ml_data.get('predicted_price')}¢\n"
            message += f"• Confidence: {ml_data.get('confidence')}%\n\n"

        # Add timestamp
        cst_time = datetime.now(ZoneInfo("America/Chicago"))
        message += f"\n⏰ Last Updated: {cst_time.strftime('%Y-%m-%d %I:%M %p %Z')}"

        return message

    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Check the monitoring status"""
        enabled_modules = self.module_manager.get_enabled_modules()
        status_message = (
            "📊 System Status\n\n"
            f"Active Modules: {len(enabled_modules)}\n"
            "Enabled Modules:\n"
        )

        for module_name in enabled_modules:
            status_message += f"• {module_name}\n"

        await update.message.reply_text(status_message)

    async def handle_prediction_feedback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle feedback on price predictions"""
        query = update.callback_query
        await query.answer()

        try:
            feedback_type = query.data.split('_')[1]
            accuracy = 1.0 if feedback_type == 'accurate' else 0.0

            if self.ml_module.is_enabled():
                # Update ML module with feedback
                await self.ml_module.process({
                    "command": "update_feedback",
                    "accuracy": accuracy
                })

            feedback_msg = "✅ Thank you for your feedback!" if accuracy == 1.0 else "👍 Thanks for helping us improve!"

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

    async def check_api_health(self):
        """Check if the API is accessible"""
        try:
            response = requests.get(HEALTH_CHECK_URL)
            return response.status_code == 200
        except:
            return False


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