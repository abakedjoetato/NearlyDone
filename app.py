import os
import logging
import json
import time
import datetime
import threading
from collections import deque

from flask import Flask, render_template, redirect, url_for, flash, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase

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

# Generate some test logs
logging.info("Console test: Application started successfully")
logging.warning("Console test: This is a sample warning log")
logging.error("Console test: This is a sample error log")
logging.debug("Console test: This is a debug message")

# Set up periodic logging
def log_system_info():
    """Periodically log system info to provide an active log stream"""
    import psutil
    import random
    
    # Log system metrics
    logging.info(f"System monitoring: CPU: {psutil.cpu_percent()}% | RAM: {psutil.virtual_memory().percent}%")
    
    # Log bot-related metrics
    bot_events = [
        "Processed server update for Guild #12345",
        "Player stats updated for 'DeadsidePlayer123'",
        "CSV parser: Downloaded new killfeed data",
        "Processed 15 player connections in last 5 minutes",
        "Mission tracker detected new mission: Supply Drop",
        "Killfeed event: Player1 killed Player2 with AK47 at 150m",
        "Server #2 reported 32/50 active players",
        "Player 'Sniper42' achieved new record: 12 kills",
        "Server uptime: 3 days, 7 hours, 42 minutes"
    ]
    
    # Occasionally log a random bot event
    if random.random() > 0.5:
        logging.info(f"Bot event: {random.choice(bot_events)}")
    
    # Occasionally log a bot warning
    if random.random() > 0.8:
        warnings = [
            "High server lag detected on Server #3",
            "Failed to download CSV file (retrying in 2 minutes)",
            "Rate limit warning from Discord API (90% of limit)",
            "Parser memory usage high (82%)",
            "Connection attempt failed (timeout)"
        ]
        logging.warning(f"Bot warning: {random.choice(warnings)}")

# Start periodic logging in a background thread
import threading
def start_periodic_logging():
    log_system_info()
    # Schedule the next run in 5 seconds
    threading.Timer(5.0, start_periodic_logging).start()

start_periodic_logging()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)