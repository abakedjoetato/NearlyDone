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

# API endpoint to start the bot using subprocess
@app.route('/api/bot/start', methods=['POST'])
def start_bot_api():
    import subprocess
    import sys
    import os
    
    # Check if bot is already running
    try:
        pid_file = os.path.join('temp', 'bot.pid')
        if os.path.exists(pid_file):
            with open(pid_file, 'r') as f:
                pid = int(f.read().strip())
            
            # Check if process is actually running
            try:
                os.kill(pid, 0)  # Signal 0 just tests if process exists
                return jsonify({
                    'success': False,
                    'error': f'Bot is already running with PID {pid}'
                })
            except OSError:
                # Process doesn't exist
                pass
    except Exception:
        pass
    
    try:
        # Direct approach - register commands then start bot
        # First run the command registration
        subprocess.run([sys.executable, 'smart_register_commands.py'], check=True)
        
        # Then start the actual bot in a background process
        process = subprocess.Popen(
            [sys.executable, 'bot_main.py'],
            stdout=open(os.path.join('logs', 'bot_output.log'), 'a'),
            stderr=subprocess.STDOUT,
            start_new_session=True  # Detach from parent process
        )
        
        # Save PID
        pid = process.pid
        with open(os.path.join('temp', 'bot.pid'), 'w') as f:
            f.write(str(pid))
        
        # Update status in our global bot status
        bot_status['running'] = True
        bot_status['status'] = 'Starting'
        bot_status['start_time'] = time.time()
        bot_status['pid'] = pid
        
        return jsonify({
            'success': True,
            'pid': pid
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

# API endpoint to stop the bot
@app.route('/api/bot/stop', methods=['POST'])
def stop_bot_api():
    import os
    import signal
    
    # Check if bot is running
    pid_file = os.path.join('temp', 'bot.pid')
    if not os.path.exists(pid_file):
        return jsonify({
            'success': False,
            'error': 'Bot is not running'
        })
    
    try:
        # Read PID
        with open(pid_file, 'r') as f:
            pid = int(f.read().strip())
        
        # Try to terminate the process
        try:
            os.kill(pid, signal.SIGTERM)
            
            # Update status
            bot_status['running'] = False
            bot_status['status'] = 'Stopped manually'
            bot_status['pid'] = None
            
            # Remove PID file
            os.unlink(pid_file)
            
            return jsonify({
                'success': True
            })
        except OSError as e:
            return jsonify({
                'success': False,
                'error': f'Failed to stop bot: {e}'
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

# Start Discord bot in a background thread using direct approach
def start_discord_bot():
    """Start the Discord bot in a separate thread"""
    import time
    import subprocess
    import sys
    import os
    
    logging.info("Starting Discord bot thread")
    try:
        # Small delay to ensure Flask is fully initialized
        time.sleep(2)
        
        # Check if bot is already running
        pid_file = os.path.join('temp', 'bot.pid')
        if os.path.exists(pid_file):
            try:
                with open(pid_file, 'r') as f:
                    pid = int(f.read().strip())
                
                # Check if process exists
                try:
                    os.kill(pid, 0)  # Signal 0 just tests if process exists
                    logging.info(f"Discord bot already running with PID: {pid}")
                    return
                except OSError:
                    # Process doesn't exist, remove stale PID file
                    os.unlink(pid_file)
            except Exception as e:
                logging.warning(f"Error checking existing bot PID: {e}")
        
        # First register commands
        logging.info("Registering Discord commands...")
        try:
            # Run in a separate process and capture output
            registration = subprocess.run(
                [sys.executable, 'smart_register_commands.py'],
                capture_output=True,
                text=True,
                check=True
            )
            for line in registration.stdout.splitlines():
                logging.info(f"CMD_REG: {line}")
            logging.info("Command registration completed successfully")
        except subprocess.CalledProcessError as e:
            logging.error(f"Command registration failed with code {e.returncode}")
            for line in e.output.splitlines():
                logging.error(f"CMD_REG_ERROR: {line}")
            # Continue anyway as we still want to start the bot
        
        # Then start the actual bot process
        logging.info("Starting bot process...")
        log_file = os.path.join('logs', 'bot_output.log')
        
        # Ensure the logs directory exists
        os.makedirs('logs', exist_ok=True)
        
        # Start the process
        bot_process = subprocess.Popen(
            [sys.executable, 'bot_main.py'],
            stdout=open(log_file, 'a'),
            stderr=subprocess.STDOUT,
            start_new_session=True  # Detach from parent process
        )
        
        # Save PID
        bot_pid = bot_process.pid
        with open(pid_file, 'w') as f:
            f.write(str(bot_pid))
        
        logging.info(f"Started Discord bot with PID: {bot_pid}")
    except Exception as e:
        logging.error(f"Error starting Discord bot: {e}")
        import traceback
        logging.error(traceback.format_exc())

# Start the bot in a separate thread
try:
    bot_thread = threading.Thread(target=start_discord_bot, daemon=True)
    bot_thread.start()
    logging.info(f"Discord bot thread started (thread ID: {bot_thread.ident})")
except Exception as e:
    logging.error(f"Failed to start bot thread: {e}")

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