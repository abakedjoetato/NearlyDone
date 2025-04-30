import os
import logging

from flask import Flask, render_template

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Create the app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key")

# Create basic routes
@app.route('/')
def index():
    return render_template('index.html', title="Deadside Bot Dashboard")

@app.route('/health')
def health():
    return {"status": "ok", "version": "1.0"}

if __name__ == '__main__':
    logger.info("Starting minimal Flask application")
    app.run(debug=True, host='0.0.0.0', port=5000)