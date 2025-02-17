import os
from flask import Flask, render_template, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from modules import ModuleManager, PriceMonitorModule, PatternAnalysisModule, MLPredictionModule

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET")

# Set the server name for external URLs
app.config["SERVER_NAME"] = "1a8446b3-198e-4458-9e5f-60fa0a94ff1f-00-1nh6gkpmzmrcg.janeway.replit.dev"
app.config["PREFERRED_URL_SCHEME"] = "https"

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

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/modules')
def module_manager_view():
    modules = module_manager.get_all_modules()
    return render_template('module_manager.html', modules=modules)

@app.route('/api/modules/<module_name>', methods=['POST'])
def toggle_module(module_name):
    action = request.json.get('action')
    if module_name == 'price_monitor':
        return jsonify({
            'success': False,
            'message': 'Price monitor module cannot be disabled as it is required.'
        }), 400

    if action == 'enable':
        success = module_manager.enable_module(module_name)
    else:
        success = module_manager.disable_module(module_name)

    return jsonify({
        'success': success,
        'message': f"Module {module_name} {'enabled' if action == 'enable' else 'disabled'} successfully" if success else "Operation failed"
    })

with app.app_context():
    import models
    db.create_all()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)