"""
Discord Bot Runner

This script starts only the Discord bot component of the application,
without starting the web server. This allows for easier debugging
and running the bot separately.
"""

import logging
import sys
from bot_main import main as bot_main

def run_bot():
    """Run the Discord bot"""
    print("="*60)
    print("Starting Discord Bot")
    print("="*60)
    
    try:
        # Setup console logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(sys.stdout),
                logging.FileHandler('logs/bot.log')
            ]
        )
        
        # Run the bot
        bot_main()
        
    except Exception as e:
        print(f"ERROR: Failed to start the bot: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_bot()