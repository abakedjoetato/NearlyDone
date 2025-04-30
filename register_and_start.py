"""
Discord Bot Command Registration and Launcher

This script handles both command registration and bot startup in one coherent process,
ensuring commands are properly registered and available in Discord.
"""

import os
import asyncio
import logging
import sys
import json
import time
import traceback
from dotenv import load_dotenv
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('logs/bot_startup.log')
    ]
)
logger = logging.getLogger('bot_startup')

# Ensure necessary directories exist
os.makedirs('logs', exist_ok=True)
os.makedirs('temp', exist_ok=True)

# Load environment variables
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

async def main():
    """Main function to handle command registration and bot startup"""
    if not DISCORD_TOKEN:
        logger.error("DISCORD_TOKEN not set. Please set it in .env file or environment variables.")
        return
        
    logger.info("Starting bot initialization process")
    
    try:
        # First, import Discord libraries and set up a temporary bot for registration
        import discord
        from discord.ext import commands
        
        # Set up intents
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.guilds = True
        
        # Create a temporary bot to register commands
        logger.info("Creating temporary bot instance for command registration")
        temp_bot = commands.Bot(
            command_prefix="!",
            intents=intents,
            sync_commands=False
        )
        
        # Define registration process
        @temp_bot.event
        async def on_ready():
            logger.info(f"Registration bot ready. Logged in as {temp_bot.user}")
            
            # Load cogs to register commands properly
            for cog_file in Path("cogs").glob("*_refactored.py"):
                cog_name = f"cogs.{cog_file.stem}"
                try:
                    await temp_bot.load_extension(cog_name)
                    logger.info(f"Loaded cog for registration: {cog_name}")
                except Exception as e:
                    logger.error(f"Failed to load cog {cog_name}: {e}")
            
            # Also load admin_commands
            try:
                await temp_bot.load_extension("cogs.admin_commands")
                logger.info("Loaded admin_commands cog")
            except Exception as e:
                logger.error(f"Failed to load admin_commands: {e}")
            
            # Register the simple commands (ping, commands_menu)
            # These are usually defined in bot_main.py
            
            @temp_bot.slash_command(name="ping", description="Check the bot's response time")
            async def ping(ctx):
                """Check the bot's response time"""
                await ctx.respond("Pong!")
                
            @temp_bot.slash_command(name="commands", description="Shows all available commands")
            async def commands_menu(ctx):
                """Shows available commands and help information"""
                await ctx.respond("Command menu would go here...")
            
            # Now sync commands with Discord for each guild
            guilds = temp_bot.guilds
            logger.info(f"Syncing commands for {len(guilds)} guilds")
            
            for guild in guilds:
                try:
                    logger.info(f"Syncing commands for guild: {guild.name}")
                    await temp_bot.sync_commands(guild_ids=[guild.id])
                    logger.info(f"✅ Commands synced for guild: {guild.name}")
                except Exception as e:
                    logger.error(f"Failed to sync commands for guild {guild.name}: {e}")
            
            logger.info("Command registration complete, disconnecting registration bot")
            await temp_bot.close()
            
        # Connect the temporary bot for command registration
        logger.info("Connecting registration bot to Discord...")
        
        try:
            await temp_bot.start(DISCORD_TOKEN)
        except Exception as e:
            logger.error(f"Error during registration bot startup: {e}")
            if str(e).startswith("429"):
                logger.error("Discord rate limit hit during command registration!")
        
        # Now start the actual bot
        logger.info("Starting the main bot process...")
        
        # Save a marker file to indicate successful registration
        with open('temp/commands_registered.txt', 'w') as f:
            f.write(f"Commands registered at {time.ctime()}")
        
        # Use subprocess to start the main bot as a separate process
        import subprocess
        import sys
        
        # Start bot_main.py as a separate process
        bot_process = subprocess.Popen(
            [sys.executable, 'bot_main.py'],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )
        
        # Log the bot's output in real-time
        for line in bot_process.stdout:
            logger.info(f"BOT: {line.strip()}")
        
        # Check the exit status
        bot_process.wait()
        if bot_process.returncode != 0:
            logger.error(f"Bot process exited with code {bot_process.returncode}")
        else:
            logger.info("Bot process finished successfully")
    
    except Exception as e:
        logger.error(f"Unexpected error in initialization: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Process interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        traceback.print_exc()