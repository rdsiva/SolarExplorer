import os
from flask import Flask, render_template, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from modules import ModuleManager, PriceMonitorModule, PatternAnalysisModule, MLPredictionModule
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET")

# Configure the database
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}

# Initialize the module manager
module_manager = ModuleManager()
price_module = PriceMonitorModule()
pattern_module = PatternAnalysisModule()
ml_module = MLPredictionModule()

# Register modules
module_manager.register_module(price_module)
module_manager.register_module(pattern_module)
module_manager.register_module(ml_module)

# Enable price monitoring by default (required)
module_manager.enable_module("price_monitor")

db.init_app(app)

@app.route('/module-management')
def module_management():
    """View for module management interface"""
    try:
        modules = module_manager.get_all_modules()
        return render_template('module_manager.html', modules=modules)
    except Exception as e:
        logger.error(f"Error in module management view: {str(e)}")
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
        logger.error(f"Error toggling module {module_name}: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

with app.app_context():
    import models
    db.create_all()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)