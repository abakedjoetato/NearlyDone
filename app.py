import os
import logging
import json
import time
import datetime
import threading
import subprocess
import random
import psutil
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

@app.route('/bot_console')
def bot_console():
    return render_template('bot_console.html', title="Bot Live Console")

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

# Buffer for bot-specific logs
bot_log_buffer = deque(maxlen=2000)  # Store the last 2000 bot log entries
bot_log_counter = 0  # Track bot log entry IDs

# Bot status tracking
bot_process = None
bot_status = {
    'running': False,
    'status': 'Offline',
    'start_time': None,
    'pid': None
}

# Bot log handler - captures logs specifically from the bot process
class BotBufferLogHandler(logging.Handler):
    def emit(self, record):
        global bot_log_counter
        bot_log_counter += 1
        
        log_entry = {
            'id': bot_log_counter,
            'timestamp': time.time(),
            'level': record.levelname,
            'logger': record.name,
            'message': self.format(record)
        }
        
        bot_log_buffer.append(log_entry)

# Install the bot log handler
bot_logger = logging.getLogger('deadside_bot')
bot_handler = BotBufferLogHandler()
bot_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
bot_logger.addHandler(bot_handler)

# API endpoint to get bot logs
@app.route('/api/bot/logs')
def get_bot_logs():
    since_id = request.args.get('since', 0, type=int)
    
    # Filter logs newer than the given ID
    logs = [log for log in bot_log_buffer if log['id'] > since_id]
    
    # Limit to most recent 200 logs if there are too many
    if len(logs) > 200:
        logs = logs[-200:]
        
    return jsonify({'logs': logs})

# API endpoint to get bot status
@app.route('/api/bot/status')
def get_bot_status():
    global bot_process, bot_status
    
    # Update status if process exists but status is outdated
    if bot_process is not None:
        if bot_process.poll() is None:  # Process is running
            if not bot_status['running']:
                bot_status['running'] = True
                bot_status['status'] = 'Running'
        else:  # Process has exited
            if bot_status['running']:
                bot_status['running'] = False
                bot_status['status'] = f'Exited with code {bot_process.returncode}'
                bot_status['pid'] = None
    
    return jsonify(bot_status)

# API endpoint to start the bot
@app.route('/api/bot/start', methods=['POST'])
def start_bot():
    global bot_process, bot_status
    
    # Check if bot is already running
    if bot_process is not None and bot_process.poll() is None:
        return jsonify({
            'success': False,
            'error': 'Bot is already running'
        })
    
    try:
        # Start the bot process
        bot_process = subprocess.Popen(
            ['python', 'bot_main.py'],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        # Update status
        bot_status['running'] = True
        bot_status['status'] = 'Starting'
        bot_status['start_time'] = time.time()
        bot_status['pid'] = bot_process.pid
        
        # Start a thread to read output
        def read_output():
            while bot_process.poll() is None:
                line = bot_process.stdout.readline()
                if line:
                    bot_logger.info(f"BOT: {line.strip()}")
            
            # Process ended
            bot_status['running'] = False
            bot_status['status'] = f'Exited with code {bot_process.returncode}'
            bot_status['pid'] = None
        
        threading.Thread(target=read_output, daemon=True).start()
        
        return jsonify({
            'success': True,
            'pid': bot_process.pid
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

# API endpoint to stop the bot
@app.route('/api/bot/stop', methods=['POST'])
def stop_bot():
    global bot_process, bot_status
    
    # Check if bot is running
    if bot_process is None or bot_process.poll() is not None:
        return jsonify({
            'success': False,
            'error': 'Bot is not running'
        })
    
    try:
        # Try to terminate gracefully first
        bot_process.terminate()
        
        # Wait up to 5 seconds for process to end
        for _ in range(50):
            if bot_process.poll() is not None:
                break
            time.sleep(0.1)
        
        # If still running, kill it
        if bot_process.poll() is None:
            bot_process.kill()
        
        # Update status
        bot_status['running'] = False
        bot_status['status'] = f'Stopped manually'
        bot_status['pid'] = None
        
        return jsonify({
            'success': True
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

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
def start_periodic_logging():
    log_system_info()
    # Schedule the next run in 5 seconds
    threading.Timer(5.0, start_periodic_logging).start()

start_periodic_logging()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)