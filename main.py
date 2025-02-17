from app import app
from flask import redirect, url_for
import routes  # Import routes to register them with Flask
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.route('/')
def index():
    """Root route handler"""
    return redirect(url_for('analytics_dashboard', chat_id="-4684354099"))

if __name__ == "__main__":
    # Ensure the server is accessible externally
    logger.info("Starting Flask server on port 5000...")
    app.run(host="0.0.0.0", port=5000, debug=True)