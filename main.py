# Import Flask app for Gunicorn
import os
import threading
import logging
from app import app

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

def start_discord_bot():
    """Start the Discord bot in a separate thread"""
    logger.info("Starting Discord bot thread")
    try:
        # Import the bot runner to properly start the bot with all registration steps
        import run_discord_bot
        
        # Start the bot using the runner
        run_discord_bot.start_bot()
        logger.info("Discord bot started using run_discord_bot")
    except Exception as e:
        logger.error(f"Error starting Discord bot: {e}")
        import traceback
        logger.error(traceback.format_exc())

# Main entry point
if __name__ == "__main__":
    # Start Discord bot in a separate thread
    try:
        bot_thread = threading.Thread(target=start_discord_bot, daemon=True)
        bot_thread.start()
        logger.info(f"Discord bot thread started (thread ID: {bot_thread.ident})")
    except Exception as e:
        logger.error(f"Failed to start bot thread: {e}")
    
    # Start Flask app
    logger.info("Starting web server")
    app.run(host="0.0.0.0", port=5000)