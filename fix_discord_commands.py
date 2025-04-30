"""
Discord Command Fixer Utility

This script forces a complete re-registration of all Discord slash commands
with a very conservative approach to rate limiting to ensure the commands
get properly registered even with Discord's rate limits.

Running this script when Discord commands aren't showing up should fix the issue.
"""

import os
import asyncio
import logging
import sys
import random
import time
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger("command_fixer")

# Load environment variables
load_dotenv()

async def main():
    logger.info("Discord Command Fixer Utility")
    logger.info("============================")
    logger.info("This utility will attempt to fix Discord slash commands by forcing re-registration")
    logger.info("with a more conservative approach to rate limiting.")
    
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        logger.error("ERROR: No DISCORD_TOKEN found in environment variables.")
        logger.error("Please ensure you have a .env file with DISCORD_TOKEN set.")
        return
    
    logger.info("✅ Found Discord token")
    
    # Import Discord libraries
    try:
        import discord
        from discord.ext import commands
        logger.info("✅ Successfully imported Discord libraries")
    except ImportError:
        logger.error("ERROR: Failed to import Discord libraries. Please ensure discord.py or py-cord is installed.")
        return
    
    # Create a bot instance
    intents = discord.Intents.default()
    intents.message_content = True
    
    bot = commands.Bot(command_prefix="!", intents=intents)
    
    @bot.event
    async def on_ready():
        logger.info(f"✅ Bot logged in as {bot.user.name} ({bot.user.id})")
        logger.info("Starting command re-registration process...")
        
        # We'll use our improved discord_command_manager
        try:
            from utils.discord_command_manager import register_commands
            logger.info("Using enhanced command manager for registration")
            
            # Wait a bit to ensure bot is fully ready
            await asyncio.sleep(5)
            
            # Force a complete command sync with very conservative rate limiting
            try:
                logger.info("Starting command re-registration with enhanced rate limiting...")
                result = await register_commands(bot)
                
                if result:
                    logger.info("✅ Successfully re-registered all commands!")
                    logger.info("Discord should display the commands after a short delay (may take up to an hour to fully propagate)")
                else:
                    logger.error("❌ Command re-registration partially failed")
                    logger.info("Some commands may have been registered but not all")
            except Exception as e:
                logger.error(f"ERROR during command registration: {e}")
                
            # Fallback to direct method if enhanced method fails
            if not result:
                logger.warning("Trying fallback approach with direct Discord.py sync...")
                try:
                    await bot.sync_commands()
                    logger.info("✅ Fallback sync completed")
                except Exception as e:
                    logger.error(f"ERROR during fallback sync: {e}")
                    
        except ImportError:
            logger.warning("Could not find enhanced command manager, using standard sync")
            
            # Use standard sync as fallback
            try:
                await bot.sync_commands()
                logger.info("✅ Standard sync completed")
            except Exception as e:
                logger.error(f"ERROR during standard sync: {e}")
        
        # Exit after command registration
        logger.info("Command re-registration complete! Logging out...")
        await bot.close()
    
    try:
        logger.info("Logging in to Discord...")
        await bot.start(token)
    except Exception as e:
        logger.error(f"ERROR: Failed to log in to Discord: {e}")
    finally:
        # Ensure we close the bot connection
        if not bot.is_closed():
            await bot.close()

if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())