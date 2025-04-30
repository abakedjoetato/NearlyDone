"""
Discord Bot Runner

This script runs the Discord bot in a separate process without blocking
the main application. It can be started and stopped as needed.
"""

import os
import subprocess
import time
import signal
import logging
import sys
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('logs/bot_runner.log', mode='a')
    ]
)

logger = logging.getLogger("bot_runner")

# Ensure logs directory exists
Path('logs').mkdir(exist_ok=True)

def start_bot():
    """Start the Discord bot in a separate process"""
    logger.info("Starting Discord bot...")
    
    # Check if bot process is already running
    pid_file = Path('temp/bot.pid')
    if pid_file.exists():
        with open(pid_file, 'r') as f:
            pid = int(f.read().strip())
        
        # Check if process still exists
        try:
            os.kill(pid, 0)  # Signal 0 just checks if process exists
            logger.info(f"Discord bot already running with PID {pid}")
            return pid
        except OSError:
            # Process not found, remove stale PID file
            logger.info(f"Removing stale PID file for non-existent process {pid}")
            pid_file.unlink(missing_ok=True)
    
    # Ensure temp directory exists
    Path('temp').mkdir(exist_ok=True)
    
    # Use the fixed command registration script
    bot_script = 'final_command_fix.py'
    
    # Start the bot in a separate process
    process = subprocess.Popen(
        ['python', bot_script],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )
    
    # Write PID to file
    with open(pid_file, 'w') as f:
        f.write(str(process.pid))
    
    logger.info(f"Discord bot started with PID {process.pid}")
    
    # Start a thread to read and log output
    import threading
    def log_output():
        for line in process.stdout:
            logger.info(f"BOT: {line.strip()}")
    
    threading.Thread(target=log_output, daemon=True).start()
    
    return process.pid

def stop_bot():
    """Stop the Discord bot process if running"""
    logger.info("Stopping Discord bot...")
    
    # Check if bot process is running
    pid_file = Path('temp/bot.pid')
    if not pid_file.exists():
        logger.info("No Discord bot PID file found")
        return False
    
    # Read PID from file
    with open(pid_file, 'r') as f:
        pid = int(f.read().strip())
    
    # Try to stop the process
    try:
        # First send SIGTERM for graceful shutdown
        os.kill(pid, signal.SIGTERM)
        
        # Give it some time to shut down
        time.sleep(2)
        
        # Check if it's still running
        try:
            os.kill(pid, 0)
            # Process still exists, force kill
            logger.warning(f"Bot process {pid} did not shut down gracefully, forcing kill")
            os.kill(pid, signal.SIGKILL)
        except OSError:
            # Process already terminated
            pass
        
        # Remove PID file
        pid_file.unlink(missing_ok=True)
        logger.info(f"Discord bot with PID {pid} stopped")
        return True
    except OSError as e:
        logger.error(f"Error stopping Discord bot: {e}")
        # Remove stale PID file
        pid_file.unlink(missing_ok=True)
        return False

def status_bot():
    """Check if the Discord bot is running"""
    pid_file = Path('temp/bot.pid')
    if not pid_file.exists():
        logger.info("Discord bot is not running")
        return False
    
    # Read PID from file
    with open(pid_file, 'r') as f:
        pid = int(f.read().strip())
    
    # Check if process still exists
    try:
        os.kill(pid, 0)  # Signal 0 just checks if process exists
        logger.info(f"Discord bot is running with PID {pid}")
        return True
    except OSError:
        # Process not found, remove stale PID file
        logger.info(f"Discord bot is not running (stale PID file removed)")
        pid_file.unlink(missing_ok=True)
        return False

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Discord Bot Runner")
    parser.add_argument('action', choices=['start', 'stop', 'restart', 'status'], 
                        help="Action to perform on the Discord bot")
    
    args = parser.parse_args()
    
    if args.action == 'start':
        start_bot()
    elif args.action == 'stop':
        stop_bot()
    elif args.action == 'restart':
        stop_bot()
        time.sleep(1)
        start_bot()
    elif args.action == 'status':
        status_bot()