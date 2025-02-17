import os
import logging
import requests
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler
from config import TELEGRAM_BOT_TOKEN, HEALTH_CHECK_URL, MIN_RATE
from modules import ModuleManager, PriceMonitorModule, PatternAnalysisModule, MLPredictionModule, ModuleError
from datetime import datetime
from zoneinfo import ZoneInfo
from app import app
from flask import render_template, request, jsonify

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
            self.application.add_handler(CommandHandler("modules", self.cmd_modules))
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
                f"Your Chat ID is: {chat_id}\n\n"
                f"🔍 Available Commands:\n"
                f"1. Price Monitoring (Required Module):\n"
                f"  • /check_price - Check current energy prices\n"
                f"  • /status - View monitoring status\n\n"
                f"2. Module Management:\n"
                f"  • /modules - List all available modules\n\n"
                f"3. Pattern Analysis (Optional Module):\n"
                f"  • Provides volatility and trend analysis\n\n"
                f"4. ML Predictions (Optional Module):\n"
                f"  • Provides price predictions\n\n"
                f"Type /help to see this message again."
            )
            await update.message.reply_text(welcome_message)
            logger.info(f"Sent welcome message to chat_id: {chat_id}")
        except Exception as e:
            logger.error(f"Error in /start command: {str(e)}")
            await update.message.reply_text("Sorry, there was an error processing your command.")

    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle the /help command"""
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

            message += "\n🌐 Manage modules at:\n"
            message += f"https://{app.config['SERVER_NAME']}/module-management\n\n"
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
        """Check current prices with data from enabled modules"""
        try:
            chat_id = update.effective_chat.id
            logger.info(f"Processing /check_price command for chat_id: {chat_id}")

            await update.message.reply_text("🔍 Checking current prices...")

            try:
                # Process data through enabled modules
                results = await self.module_manager.process_with_enabled_modules({})

                # Get notification data from enabled modules
                notification_data = await self.module_manager.get_notification_data()

                # Format and send the message
                message = self._format_price_message(results, notification_data)

                # Send the message with or without feedback buttons
                if "ml_prediction" in notification_data and notification_data["ml_prediction"].get("predicted_price"):
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

            except Exception as e:
                # If the core price_monitor module fails
                if isinstance(e, ModuleError) and e.module_name == "price_monitor":
                    error_msg = "❌ Unable to fetch current prices. Please try again later."
                    logger.error(f"Core price monitoring failed: {str(e)}")
                else:
                    # If optional modules fail, still show basic price info
                    try:
                        basic_price_data = await self.price_module.get_notification_data()
                        if basic_price_data:
                            message = "📊 Basic Price Information\n\n"
                            message += f"Current Price: {basic_price_data.get('current_price')}¢\n"
                            message += "\n⚠️ Some features are temporarily unavailable."
                            await self.bot.send_message(chat_id=chat_id, text=message)
                            return
                    except Exception as e:
                        error_msg = "❌ Error fetching price data. Please try again later."

                await update.message.reply_text(error_msg)
                return

            logger.info(f"Price check completed for chat_id: {chat_id}")

        except Exception as e:
            error_msg = f"❌ Unexpected error: {str(e)}"
            logger.error(error_msg)
            await update.message.reply_text(
                "Sorry, there was an unexpected error. Please try again later."
            )

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


@app.route('/module-management', methods=['GET'])
def module_management_view():
    """View for module management web interface"""
    modules = bot.module_manager.get_all_modules()
    return render_template('module_manager.html', modules=modules)

@app.route('/api/modules/<module_name>', methods=['POST'])
def toggle_module(module_name):
    """API endpoint to toggle module state"""
    try:
        data = request.get_json()
        action = data.get('action')

        if action == 'enable':
            success = bot.module_manager.enable_module(module_name)
        elif action == 'disable':
            success = bot.module_manager.disable_module(module_name)
        else:
            return jsonify({'success': False, 'message': 'Invalid action'}), 400

        return jsonify({
            'success': success,
            'message': f'Module {module_name} {"enabled" if action == "enable" else "disabled"} successfully'
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

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