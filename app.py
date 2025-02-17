import os
from flask import Flask, render_template, jsonify, request
import logging
from datetime import datetime, timedelta
import random
from database import db, init_db

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Log initialization start
logger.info("Starting Flask application initialization...")

try:
    app = Flask(__name__)

    # Log environment variables (without sensitive data)
    logger.info("Checking environment variables...")
    if not os.environ.get("SESSION_SECRET"):
        logger.error("SESSION_SECRET environment variable is not set")
    if not os.environ.get("DATABASE_URL"):
        logger.error("DATABASE_URL environment variable is not set")

    app.secret_key = os.environ.get("SESSION_SECRET", "default-dev-secret")

    # Configure the database
    logger.info("Configuring database connection...")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_recycle": 300,
        "pool_pre_ping": True,
    }
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # Register Jinja2 filters
    def format_datetime(value, format='%Y-%m-%d %H:%M:%S'):
        if value is None:
            return ''
        return value.strftime(format)

    app.jinja_env.filters['strftime'] = format_datetime

    # Initialize database first
    logger.info("Initializing database...")
    init_db(app)

    def init_modules():
        """Initialize modules after app context is created"""
        from modules import (
            ModuleManager,
            get_price_monitor_module,
            get_pattern_analysis_module,
            get_ml_prediction_module,
            get_dashboard_module
        )

        # Initialize the module manager
        logger.info("Initializing ModuleManager...")
        module_manager = ModuleManager()

        # Initialize modules using factory functions
        price_module = get_price_monitor_module()()
        pattern_module = get_pattern_analysis_module()()
        ml_module = get_ml_prediction_module()()
        dashboard_module = get_dashboard_module()()

        logger.info("Registering modules...")
        module_manager.register_module(price_module)
        module_manager.register_module(pattern_module)
        module_manager.register_module(ml_module)
        module_manager.register_module(dashboard_module)

        # Enable required modules
        logger.info("Enabling required price monitor module...")
        module_manager.enable_module("price_monitor")
        logger.info("Enabling dashboard module...")
        module_manager.enable_module("dashboard")

        return module_manager

    # Initialize modules after database setup
    with app.app_context():
        module_manager = init_modules()

    # Import routes after app initialization
    import routes

    logger.info("Flask application initialization completed")

except Exception as e:
    logger.critical(f"Failed to initialize Flask application: {str(e)}", exc_info=True)
    raise

if __name__ == "__main__":
    logger.info("Starting Flask development server...")
    app.run(host="0.0.0.0", port=5001, debug=True)