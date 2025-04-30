#!/usr/bin/env python3
"""
Bot Launcher Script

This is a simple wrapper that ensures the Discord bot is started correctly
by using the run_discord_bot.py script to:

1. First register all commands with Discord
2. Then start the actual bot process

This is used as the entry point for starting the Discord bot.
"""

import os
import sys
import logging
import time
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('logs/bot_launcher.log')
    ]
)
logger = logging.getLogger("bot_launcher")

# Ensure required directories exist
Path('logs').mkdir(exist_ok=True)
Path('temp').mkdir(exist_ok=True)

# Main function
def main():
    """Main function to start the Discord bot"""
    logger.info("Bot launcher starting")
    
    try:
        # Import our bot runner
        logger.info("Importing run_discord_bot...")
        from run_discord_bot import start_bot, status_bot
        
        # Check if bot is already running
        if status_bot():
            logger.info("Discord bot is already running, no action needed")
            return
        
        # Start the bot which will:
        # 1. Register all commands using smart_register_commands.py
        # 2. Start the actual bot process
        logger.info("Starting Discord bot...")
        pid = start_bot()
        logger.info(f"Discord bot started with PID: {pid}")
        
        # Keep the script running to monitor the bot
        logger.info("Bot launcher will now monitor the bot process...")
        
        # Output basic info every 10 seconds so we have a log trail
        while status_bot():
            logger.info("Discord bot is running")
            time.sleep(10)
        
        logger.info("Discord bot has stopped")
        
    except Exception as e:
        logger.error(f"Error in bot launcher: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())