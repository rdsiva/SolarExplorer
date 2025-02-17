from app import app
import routes  # Import routes to register them with Flask

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)