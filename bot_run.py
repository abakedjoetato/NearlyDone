"""
Discord Bot Runner

This script starts only the Discord bot component of the application,
without starting the web server. This allows for easier debugging
and running the bot separately.
"""

import os
import logging
import asyncio
from dotenv import load_dotenv
import traceback

# Create the log directory if it doesn't exist
os.makedirs('logs', exist_ok=True)

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging_level = os.getenv("LOGGING_LEVEL", "INFO").upper()
numeric_level = getattr(logging, logging_level, logging.INFO)
logging.basicConfig(
    level=numeric_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # Log to console
        logging.FileHandler('logs/bot.log', mode='a')  # Log to file
    ]
)

logger = logging.getLogger('deadside_bot')
logger.info("Starting Discord bot...")

def run_bot():
    """Run the Discord bot"""
    try:
        # Import here to avoid circular imports
        from main import main
        logger.info("Bot main function imported")
        
        # The main function is not async, it calls bot.run() which blocks
        main()
    except Exception as e:
        logger.error(f"Error starting bot: {e}")
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    run_bot()