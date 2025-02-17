from app import app
from flask import redirect, url_for
import routes  # Import routes to register them with Flask

@app.route('/')
def index():
    """Root route handler"""
    return redirect(url_for('analytics_dashboard', chat_id="-4684354099"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)