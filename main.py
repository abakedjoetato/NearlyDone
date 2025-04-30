# Central launcher for both Flask app and Discord bot
import os
import sys
import time
import subprocess
import threading
import logging
import atexit
from pathlib import Path

# Create necessary directories
os.makedirs('logs', exist_ok=True)
os.makedirs('temp', exist_ok=True)

# Set up logging for both components
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('logs/combined.log')
    ]
)
logger = logging.getLogger('main')
logger.info("Starting Deadside Bot application")

# Import Flask app
from app import app

# Global variables to track processes
discord_bot_process = None
command_registration_process = None

def register_commands():
    """Register commands with Discord API"""
    global command_registration_process
    
    logger.info("Registering Discord commands")
    try:
        # Run command registration script directly
        command_registration_process = subprocess.Popen(
            [sys.executable, 'smart_register_commands.py'],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )
        
        # Read and log the output
        for line in command_registration_process.stdout:
            logger.info(f"CMD_REG: {line.strip()}")
            
        # Wait for the process to complete
        command_registration_process.wait()
        logger.info(f"Command registration completed with exit code: {command_registration_process.returncode}")
        return command_registration_process.returncode == 0
        
    except Exception as e:
        logger.error(f"Error during command registration: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def start_discord_bot():
    """Start the Discord bot as a subprocess"""
    global discord_bot_process
    
    logger.info("Starting Discord bot")
    try:
        # First make sure we register commands
        register_result = register_commands()
        if not register_result:
            logger.warning("Command registration did not complete successfully, but continuing with bot startup")
        
        # Give Discord API a moment to process the command registrations
        time.sleep(2)
        
        # Start the actual bot process
        discord_bot_process = subprocess.Popen(
            [sys.executable, 'bot_main.py'],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )
        
        # Save PID to file for management
        bot_pid = discord_bot_process.pid
        with open('temp/bot.pid', 'w') as f:
            f.write(str(bot_pid))
        
        logger.info(f"Discord bot started with PID: {bot_pid}")
        
        # Start a thread to monitor and log bot output
        def monitor_bot_output():
            for line in discord_bot_process.stdout:
                logger.info(f"BOT: {line.strip()}")
            
            # If we get here, the bot process has ended
            exit_code = discord_bot_process.wait()
            logger.info(f"Discord bot process exited with code: {exit_code}")
        
        threading.Thread(target=monitor_bot_output, daemon=True).start()
        return True
        
    except Exception as e:
        logger.error(f"Error starting Discord bot: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def cleanup_processes():
    """Clean up processes when the application exits"""
    logger.info("Cleaning up processes before shutdown")
    
    if discord_bot_process:
        logger.info(f"Terminating Discord bot process (PID: {discord_bot_process.pid})")
        try:
            discord_bot_process.terminate()
            discord_bot_process.wait(timeout=5)
        except:
            logger.warning("Failed to gracefully terminate bot, forcing kill")
            try:
                discord_bot_process.kill()
            except:
                pass

# Register cleanup function
atexit.register(cleanup_processes)

# Import the Flask app here to avoid circular imports
from app import app

# This is the entrypoint for gunicorn - it imports this file and uses the 'app' variable
logger.info("Flask app imported and ready")

# Main entry point when run directly
if __name__ == "__main__":
    # Start Discord bot
    start_discord_bot()
    
    # Start Flask app - this will block until the app is stopped
    logger.info("Starting Flask web server")
    app.run(host="0.0.0.0", port=5000)