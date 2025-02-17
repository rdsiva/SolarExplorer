import os
import logging
import requests
import asyncio
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler
from config import TELEGRAM_BOT_TOKEN, HEALTH_CHECK_URL
from modules import ModuleManager, PriceMonitorModule, PatternAnalysisModule, MLPredictionModule, DashboardModule, ModuleError
from datetime import datetime
from zoneinfo import ZoneInfo
from flask import Flask
from app import app, db
from models import UserPreferences

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class EnergyPriceBot:
    def __init__(self):
        """Initialize the bot"""
        try:
            logger.info("Initializing EnergyPriceBot...")
            self.bot_token = TELEGRAM_BOT_TOKEN
            if not self.bot_token:
                logger.error("TELEGRAM_BOT_TOKEN is not set")
                raise ValueError("TELEGRAM_BOT_TOKEN is not set")

            logger.info("Building application with token...")
            self.application = Application.builder().token(self.bot_token).build()
            self.bot = self.application.bot

            # Initialize module manager and register modules
            logger.info("Initializing ModuleManager...")
            self.module_manager = ModuleManager()
            self._setup_modules()

            # Set up command handlers
            self._setup_handlers()

            logger.info("Bot initialization completed successfully")
        except Exception as e:
            logger.error(f"Failed to initialize bot: {str(e)}")
            raise

    def _setup_modules(self):
        """Set up and register all available modules"""
        try:
            logger.info("Setting up modules...")
            # Initialize modules
            self.price_module = PriceMonitorModule()  # Required module
            logger.info("Price monitor module initialized")

            self.pattern_module = PatternAnalysisModule()  # Optional
            logger.info("Pattern analysis module initialized")

            self.ml_module = MLPredictionModule()  # Optional
            logger.info("ML prediction module initialized")

            self.dashboard_module = DashboardModule()  # Optional
            logger.info("Dashboard module initialized")

            # Register modules
            logger.info("Registering modules with manager...")
            self.module_manager.register_module(self.price_module)
            self.module_manager.register_module(self.pattern_module)
            self.module_manager.register_module(self.ml_module)
            self.module_manager.register_module(self.dashboard_module)

            # Enable price monitoring by default (required)
            logger.info("Enabling required modules...")
            self.module_manager.enable_module("price_monitor")
            self.module_manager.enable_module("dashboard")  # Enable dashboard by default

            logger.info("Modules setup completed successfully")
        except Exception as e:
            logger.error(f"Error setting up modules: {str(e)}")
            raise

    def _setup_handlers(self):
        """Set up command handlers for the bot"""
        try:
            logger.info("Setting up command handlers...")
            self.application.add_handler(CommandHandler("start", self.cmd_start))
            self.application.add_handler(CommandHandler("help", self.cmd_help))
            self.application.add_handler(CommandHandler("check", self.cmd_check_price))
            self.application.add_handler(CommandHandler("status", self.cmd_status))
            self.application.add_handler(CommandHandler("modules", self.cmd_modules))
            self.application.add_handler(CommandHandler("enable", self.cmd_enable_module))
            self.application.add_handler(CommandHandler("disable", self.cmd_disable_module))
            self.application.add_handler(CommandHandler("preferences", self.cmd_preferences))
            self.application.add_handler(CommandHandler("threshold", self.cmd_set_threshold))
            self.application.add_handler(CallbackQueryHandler(self.handle_prediction_feedback))
            logger.info("Command handlers setup completed")
        except Exception as e:
            logger.error(f"Error setting up handlers: {e}")
            raise

    async def start(self):
        """Start the bot"""
        try:
            logger.info("Starting bot...")
            await self.application.initialize()
            await self.application.start()
            await self.application.run_polling(allowed_updates=Update.ALL_TYPES)
        except Exception as e:
            logger.error(f"Error starting bot: {e}")
            raise

    async def stop(self):
        """Stop the bot"""
        try:
            if self.application.running:
                await self.application.stop()
                await self.application.shutdown()
        except Exception as e:
            logger.error(f"Error stopping bot: {e}")

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Send a message when the command /start is issued."""
        try:
            chat_id = update.effective_chat.id
            logger.info(f"Received /start command from chat_id: {chat_id}")

            # Get Replit domain for web interface
            repl_slug = os.environ.get("REPL_SLUG", "")
            repl_owner = os.environ.get("REPL_OWNER", "")
            web_url = f"https://{repl_slug}.{repl_owner}.repl.co/module-management"

            welcome_message = (
                f"👋 Welcome to the Energy Price Monitor Bot!\n\n"
                f"🔍 Available Commands:\n\n"
                f"1. Price Monitoring:\n"
                f"  • /check - Check current energy prices\n"
                f"  • /status - View monitoring status\n\n"
                f"2. Module Management:\n"
                f"  • /modules - List all available modules\n"
                f"  • /enable <module> - Enable a module\n"
                f"  • /disable <module> - Disable a module\n\n"
                f"3. Preferences:\n"
                f"  • /preferences - View your settings\n"
                f"  • /threshold - Set price alert threshold\n\n"
                f"4. Web Management:\n"
                f"  • Web Interface: {web_url}\n\n"
                f"Type /help to see this message again."
            )
            await update.message.reply_text(welcome_message)
            logger.info(f"Sent welcome message to chat_id: {chat_id}")
        except Exception as e:
            logger.error(f"Error in /start command: {str(e)}")
            await update.message.reply_text("Sorry, there was an error processing your command.")

    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show help information"""
        await self.cmd_start(update, context)

    async def cmd_modules(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """List all available modules and their status"""
        try:
            modules = self.module_manager.get_all_modules()
            message = "📊 Available Modules:\n\n"

            # First list the required price monitor module
            for module in modules:
                if module["name"] == "price_monitor":
                    status = "✅ Always Enabled (Required)"
                    message += (
                        f"1. {module['name'].replace('_', ' ').title()} 🔒\n"
                        f"   • Status: {status}\n"
                        f"   • Description: {module['description']}\n\n"
                    )
                    break

            # Then list optional modules
            optional_count = 2
            for module in modules:
                if module["name"] != "price_monitor":
                    status = "✅ Enabled" if module["enabled"] else "❌ Disabled"
                    message += (
                        f"{optional_count}. {module['name'].replace('_', ' ').title()} (Optional)\n"
                        f"   • Status: {status}\n"
                        f"   • Description: {module['description']}\n\n"
                    )
                    optional_count += 1

            message += "Note: The price monitor module is required and cannot be disabled."

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
        """Handle the /check_price command"""
        try:
            chat_id = update.effective_chat.id
            logger.info(f"Processing /check_price command for chat_id: {chat_id}")

            await update.message.reply_text("🔍 Checking current prices...")

            try:
                # Get basic price data first
                logger.debug("Fetching price data from price monitor module")
                price_data = await self.price_module.get_notification_data()
                if not price_data:
                    error_msg = "❌ Unable to fetch current prices. Please try again later."
                    logger.error("Price monitor returned no data")
                    await update.message.reply_text(error_msg)
                    await self._send_admin_notification(
                        self.module_manager.admin_chat_id,
                        f"Price monitor failed to return data for chat_id: {chat_id}"
                    )
                    return

                # Format basic message with price data
                message = "📊 Energy Price Update\n\n"
                message += f"Current Price: {price_data['current_price']}¢\n"
                message += f"Provider: {price_data.get('provider', 'Unknown')}\n"
                message += f"Last Updated: {price_data['time']}\n"
                message += f"Status: {price_data.get('status', 'unknown')}\n\n"

                # Try to get additional data from other modules
                try:
                    logger.debug("Fetching additional module data")
                    notification_data = await self.module_manager.get_notification_data()

                    # Add pattern analysis if available
                    if 'pattern_analysis' in notification_data:
                        pattern_data = notification_data['pattern_analysis']
                        if pattern_data:
                            message += "📈 Pattern Analysis:\n"
                            message += f"• Trend: {pattern_data.get('trend', 'Unknown')}\n"
                            message += f"• Volatility: {pattern_data.get('volatility', 'N/A')}\n\n"

                    # Add ML predictions if available
                    if 'ml_prediction' in notification_data:
                        ml_data = notification_data['ml_prediction']
                        if ml_data:
                            message += "🔮 Price Prediction:\n"
                            message += f"• Next Hour: {ml_data.get('predicted_price', 'N/A')}¢\n"
                            message += f"• Confidence: {ml_data.get('confidence', 'N/A')}%\n\n"

                except Exception as module_error:
                    logger.error(f"Error processing optional modules: {str(module_error)}")
                    message += "\n⚠️ Some features are temporarily unavailable."
                    await self._send_admin_notification(
                        self.module_manager.admin_chat_id,
                        f"Optional modules failed for chat_id {chat_id}: {str(module_error)}"
                    )

                # Add timestamp
                message += f"\n⏰ Last Updated: {datetime.now(ZoneInfo('America/Chicago')).strftime('%Y-%m-%d %I:%M %p %Z')}"

                await update.message.reply_text(message)
                logger.info(f"Successfully sent price update to chat_id: {chat_id}")

            except ModuleError as me:
                error_msg = f"❌ {str(me)}"
                logger.error(error_msg)
                await self._send_admin_notification(
                    self.module_manager.admin_chat_id,
                    f"Critical module error in price check: {str(me)}"
                )
                await update.message.reply_text(error_msg)

        except Exception as e:
            logger.error(f"Critical error in check_price command: {str(e)}")
            await update.message.reply_text(
                "❌ Sorry, there was an unexpected error. Please try again later."
            )
            if self.module_manager.admin_chat_id:
                await self._send_admin_notification(
                    self.module_manager.admin_chat_id,
                    f"Critical bot error in check_price: {str(e)}"
                )

    async def _send_admin_notification(self, chat_id: str, message: str):
        """Send notification to admin"""
        try:
            if not chat_id:
                logger.warning("Admin chat ID not set, skipping notification")
                return
            await self.bot.send_message(
                chat_id=chat_id,
                text=f"🤖 Bot Admin Alert:\n{message}"
            )
        except Exception as e:
            logger.error(f"Failed to send admin notification: {str(e)}")

    def _format_price_message(self, results: dict, notification_data: dict) -> str:
        """Format price message with data from enabled modules"""
        message = "📊 Energy Price Update\n\n"

        # Price monitoring data (always present)
        price_data = notification_data.get("price_monitor", {})
        if price_data:
            message += f"Current Price: {price_data.get('current_price')}¢\n"
            message += f"Five-min Price: {price_data.get('five_min_price')}¢\n"
            message += f"Trend: {price_data.get('trend', 'unknown').capitalize()}\n\n"
        else:
            message += "⚠️ Basic price data unavailable\n\n"

        # Pattern analysis data (if enabled and available)
        pattern_data = notification_data.get("pattern_analysis")
        if pattern_data:
            message += "📈 Pattern Analysis:\n"
            message += f"• Current Trend: {pattern_data.get('current_trend', 'unknown').capitalize()}\n"
            message += f"• Volatility: {pattern_data.get('volatility', 0):.2f}\n\n"

        # ML predictions (if enabled and available)
        ml_data = notification_data.get("ml_prediction")
        if ml_data and ml_data.get("predicted_price"):
            message += "🔮 Price Prediction:\n"
            message += f"• Next Hour: {ml_data.get('predicted_price')}¢\n"
            message += f"• Confidence: {ml_data.get('confidence')}%\n\n"

        # Add timestamp
        cst_time = datetime.now(ZoneInfo("America/Chicago"))
        message += f"\n⏰ Last Updated: {cst_time.strftime('%Y-%m-%d %I:%M %p %Z')}"

        if not any(notification_data.values()):
            message += "\n\n⚠️ Some features are currently unavailable."

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

    # Added command handlers for preferences and threshold
    async def cmd_preferences(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show user preferences"""
        try:
            chat_id = update.effective_chat.id
            logger.info(f"Showing preferences for chat_id: {chat_id}")

            with app.app_context():
                prefs = UserPreferences.get_user_preferences(str(chat_id))
                if prefs:
                    message = (
                        "🔧 Your Current Preferences:\n\n"
                        f"• Price Threshold: {prefs.price_threshold}¢\n"
                        f"• Alert Frequency: {prefs.alert_frequency}\n"
                        f"• Active: {'Yes' if prefs.is_active else 'No'}\n"
                    )
                    if prefs.start_time and prefs.end_time:
                        message += f"• Alert Window: {prefs.start_time.strftime('%I:%M %p')} - {prefs.end_time.strftime('%I:%M %p')}"
                else:
                    message = (
                        "❌ No preferences found.\n"
                        "Use /threshold to set your price alert threshold."
                    )

            await update.message.reply_text(message)
            logger.info(f"Sent preferences to chat_id: {chat_id}")

        except Exception as e:
            logger.error(f"Error showing preferences: {str(e)}")
            await update.message.reply_text("Sorry, there was an error fetching your preferences.")

    async def cmd_set_threshold(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Set price alert threshold"""
        try:
            chat_id = update.effective_chat.id
            logger.info(f"Setting threshold for chat_id: {chat_id}")

            # Check if a threshold value was provided
            if not context.args:
                await update.message.reply_text(
                    "Please provide a threshold value in cents (e.g., /threshold 3.5)\n"
                    "This is the price above which you'll receive alerts."
                )
                return

            try:
                threshold = float(context.args[0])
                if threshold <= 0:
                    await update.message.reply_text("❌ Threshold must be a positive number.")
                    return

                with app.app_context():
                    prefs = UserPreferences.create_or_update(str(chat_id), price_threshold=threshold)

                await update.message.reply_text(
                    f"✅ Price threshold set to {threshold}¢\n"
                    "You'll receive alerts when prices exceed this threshold."
                )
                logger.info(f"Set threshold to {threshold} for chat_id: {chat_id}")

            except ValueError:
                await update.message.reply_text(
                    "❌ Please enter a valid number (e.g., 3.5)"
                )

        except Exception as e:
            logger.error(f"Error setting threshold: {str(e)}")
            await update.message.reply_text("Sorry, there was an error setting your threshold.")



def main():
    """Start the bot."""
    try:
        # Create the bot instance
        logger.info("Starting new bot instance...")
        bot = EnergyPriceBot()

        # Initialize modules
        logger.info("Initializing modules...")

        # Set up asyncio event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # Initialize modules
        loop.run_until_complete(bot.module_manager.initialize_modules())

        # Start the bot
        logger.info("Starting bot...")
        loop.run_until_complete(bot.start())

        # Run forever
        try:
            loop.run_forever()
        except KeyboardInterrupt:
            logger.info("Bot stopped by user")
            loop.run_until_complete(bot.stop())
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
            raise
        finally:
            loop.close()

    except Exception as e:
        logger.critical(f"Bot failed to start: {str(e)}")
        raise

if __name__ == '__main__':
    main()