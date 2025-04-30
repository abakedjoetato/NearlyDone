"""
Discord Bot Restart Utility

This script safely shuts down and restarts the Discord bot.
It will wait for the bot to gracefully shut down before starting it again.
"""

import os
import subprocess
import time
import signal
import logging
import sys
import psutil

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger("bot_restart")

def find_bot_process():
    """Find the running bot process if any"""
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = proc.info['cmdline']
            if cmdline and len(cmdline) > 1:
                if 'python' in cmdline[0].lower() and any(x in ' '.join(cmdline) for x in ['bot_run.py', 'bot_main.py']):
                    return proc
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    return None

def stop_bot():
    """Stop the running bot process if it exists"""
    bot_process = find_bot_process()
    
    if bot_process:
        logger.info(f"Found bot process: PID {bot_process.pid}")
        try:
            # Try to gracefully terminate the process
            bot_process.terminate()
            
            # Wait for up to 10 seconds for the process to terminate
            gone, alive = psutil.wait_procs([bot_process], timeout=10)
            if alive:
                # Force kill if it's still running
                logger.warning("Bot didn't terminate gracefully, killing process...")
                for p in alive:
                    p.kill()
                    
            logger.info("Bot process terminated")
            return True
        except psutil.NoSuchProcess:
            logger.info("Bot process already terminated")
            return True
        except Exception as e:
            logger.error(f"Error stopping bot: {e}")
            return False
    else:
        logger.info("No bot process found to stop")
        return True

def start_bot():
    """Start the Discord bot"""
    try:
        # Use Popen to start a detached process that will continue running
        bot_process = subprocess.Popen(
            ["python", "bot_run.py"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )
        logger.info(f"Started bot process with PID: {bot_process.pid}")
        return True
    except Exception as e:
        logger.error(f"Error starting bot: {e}")
        return False

def main():
    logger.info("Discord Bot Restart Utility")
    logger.info("===========================")
    
    # Step 1: Stop the bot if it's running
    logger.info("Step 1: Stopping bot if running...")
    if stop_bot():
        logger.info("Bot stopped successfully (or was not running)")
    else:
        logger.error("Failed to stop bot, aborting restart.")
        return
    
    # Step 2: Wait a moment before starting again
    wait_time = 5
    logger.info(f"Waiting {wait_time} seconds before starting bot...")
    time.sleep(wait_time)
    
    # Step 3: Start the bot
    logger.info("Step 3: Starting bot...")
    if start_bot():
        logger.info("Bot started successfully!")
        logger.info("Commands should be registered as part of the startup process.")
        logger.info("Check the bot logs for details.")
    else:
        logger.error("Failed to start bot.")

if __name__ == "__main__":
    main()