import os
import logging
import json
import time
import datetime
import threading
import queue
from collections import deque

from flask import Flask, render_template, redirect, url_for, flash, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)
# create the app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key")

# configure the database
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///deadside.db")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}
# initialize the app with the extension
db.init_app(app)

# Create basic routes
@app.route('/')
def index():
    return render_template('index.html', title="Deadside Bot Dashboard")

@app.route('/servers')
def servers():
    return render_template('servers.html', title="Servers")

@app.route('/stats')
def stats():
    return render_template('stats.html', title="Statistics")

@app.route('/settings')
def settings():
    return render_template('settings.html', title="Settings")

@app.route('/console')
def console():
    return render_template('console.html', title="Bot Console")

# In-memory log buffer
log_buffer = deque(maxlen=1000)  # Store the last 1000 log entries
log_counter = 0  # Used to track log entry IDs

# Custom log handler to capture logs
class BufferLogHandler(logging.Handler):
    def emit(self, record):
        global log_counter
        log_counter += 1
        
        log_entry = {
            'id': log_counter,
            'timestamp': time.time(),
            'level': record.levelname,
            'logger': record.name,
            'message': self.format(record)
        }
        
        log_buffer.append(log_entry)

# Install the custom handler
root_logger = logging.getLogger()
buffer_handler = BufferLogHandler()
buffer_handler.setFormatter(logging.Formatter('%(message)s'))
root_logger.addHandler(buffer_handler)

# API endpoint to get console logs
@app.route('/api/console-logs')
def get_console_logs():
    since_id = request.args.get('since', 0, type=int)
    
    # Filter logs newer than the given ID
    logs = [log for log in log_buffer if log['id'] > since_id]
    
    # Limit to most recent 100 logs if there are too many
    if len(logs) > 100:
        logs = logs[-100:]
        
    return jsonify({'logs': logs})

# Create the database tables
with app.app_context():
    # Import models
    from models import User  # noqa: F401
    
    # Create tables
    db.create_all()

if __name__ == '__main__':
    logger.info("Starting Flask application")
    app.run(debug=True, host='0.0.0.0', port=5000)