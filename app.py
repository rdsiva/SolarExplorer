import os
from flask import Flask, render_template, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from modules import ModuleManager, PriceMonitorModule, PatternAnalysisModule, MLPredictionModule
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Log initialization start
logger.info("Starting Flask application initialization...")

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)
app = Flask(__name__)

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

# Initialize the module manager
logger.info("Initializing ModuleManager...")
module_manager = ModuleManager()
price_module = PriceMonitorModule()
pattern_module = PatternAnalysisModule()
ml_module = MLPredictionModule()

# Register modules
logger.info("Registering modules...")
module_manager.register_module(price_module)
module_manager.register_module(pattern_module)
module_manager.register_module(ml_module)

# Enable price monitoring by default (required)
logger.info("Enabling required price monitor module...")
module_manager.enable_module("price_monitor")

logger.info("Initializing database...")
db.init_app(app)

@app.route('/module-management')
def module_management():
    """View for module management interface"""
    try:
        logger.info("Accessing module management view")
        modules = module_manager.get_all_modules()
        logger.info(f"Retrieved modules: {modules}")
        return render_template('module_manager.html', modules=modules)
    except Exception as e:
        logger.error(f"Error in module management view: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route('/api/modules/<module_name>', methods=['POST'])
def toggle_module(module_name):
    """API endpoint to toggle module state"""
    try:
        if module_name == 'price_monitor':
            return jsonify({
                'success': False,
                'message': 'Price monitor module cannot be disabled as it is required.'
            }), 400

        data = request.get_json()
        if not data or 'action' not in data:
            return jsonify({
                'success': False,
                'message': 'Missing action parameter'
            }), 400

        action = data['action']
        if action not in ['enable', 'disable']:
            return jsonify({
                'success': False,
                'message': 'Invalid action. Must be either "enable" or "disable"'
            }), 400

        success = module_manager.enable_module(module_name) if action == 'enable' else module_manager.disable_module(module_name)

        return jsonify({
            'success': success,
            'message': f"Module {module_name} {'enabled' if action == 'enable' else 'disabled'} successfully" if success else "Operation failed"
        })
    except Exception as e:
        logger.error(f"Error toggling module {module_name}: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500

logger.info("Creating database tables...")
with app.app_context():
    import models
    db.create_all()
    logger.info("Database tables created successfully")

logger.info("Flask application initialization completed")

if __name__ == "__main__":
    logger.info("Starting Flask development server...")
    app.run(host="0.0.0.0", port=5000, debug=True)