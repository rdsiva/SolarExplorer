import os
from flask import Flask, render_template, jsonify, request
import logging
from datetime import datetime, timedelta
import random
from database import db, init_db

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)
logger.info("Starting Flask application initialization...")

try:
    # Log environment variables (without sensitive data)
    logger.info("Checking environment variables...")
    if not os.environ.get("SESSION_SECRET"):
        logger.error("SESSION_SECRET environment variable is not set")
    if not os.environ.get("DATABASE_URL"):
        logger.error("DATABASE_URL environment variable is not set")

    app.secret_key = os.environ.get("SESSION_SECRET")

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

    # Initialize database
    logger.info("Initializing database...")
    init_db(app)

    # Initialize agent manager after database is ready
    with app.app_context():
        from agents.agent_manager import AgentManager
        logger.info("Initializing AgentManager...")
        agent_manager = AgentManager()

        # Import routes last, after all initialization is complete
        logger.info("Registering routes...")
        from routes import *  # This will register all routes with the app

    logger.info("Flask application initialization completed")

except Exception as e:
    logger.critical(f"Failed to initialize Flask application: {str(e)}", exc_info=True)
    raise

if __name__ == "__main__":
    logger.info("Starting Flask development server...")
    app.run(host="0.0.0.0", port=5001, debug=True)