"""
Discord Bot Command Cleanup Utility

This script removes all registered commands for a Discord bot before new ones are registered.
It helps prevent duplicate commands from appearing in the Discord interface.
"""

import os
import asyncio
import logging
import sys
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('logs/command_cleanup.log', mode='w')
    ]
)

logger = logging.getLogger("command_cleanup")

# Load environment variables
load_dotenv()

async def main():
    logger.info("Discord Bot Command Cleanup Utility")
    logger.info("==================================")
    
    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        logger.error("ERROR: No DISCORD_TOKEN found in environment variables")
        return
    
    try:
        # Import Discord libraries
        import discord
        from discord.ext import commands
        
        # Set up intents
        intents = discord.Intents.default()
        intents.message_content = True
        
        # Create a simple bot instance
        bot = commands.Bot(command_prefix="!", intents=intents)
        
        # On ready event handler
        @bot.event
        async def on_ready():
            logger.info(f"Bot is ready! Logged in as {bot.user}")
            
            # Get all guilds
            logger.info(f"Connected to {len(bot.guilds)} guilds")
            for guild in bot.guilds:
                guild_id = guild.id
                guild_name = guild.name
                
                try:
                    # First, get all existing commands
                    existing_commands = await bot.http.get_guild_commands(bot.user.id, guild_id)
                    logger.info(f"Found {len(existing_commands)} commands in guild {guild_name}")
                    
                    # Delete each command
                    for cmd in existing_commands:
                        cmd_id = cmd['id']
                        cmd_name = cmd['name']
                        logger.info(f"Deleting command: {cmd_name} (ID: {cmd_id})")
                        
                        try:
                            await bot.http.delete_guild_command(bot.user.id, guild_id, cmd_id)
                            logger.info(f"Successfully deleted command: {cmd_name}")
                        except Exception as e:
                            logger.error(f"Error deleting command {cmd_name}: {e}")
                    
                    # Also check for global commands
                    global_commands = await bot.http.get_global_commands(bot.user.id)
                    logger.info(f"Found {len(global_commands)} global commands")
                    
                    # Delete each global command
                    for cmd in global_commands:
                        cmd_id = cmd['id']
                        cmd_name = cmd['name']
                        logger.info(f"Deleting global command: {cmd_name} (ID: {cmd_id})")
                        
                        try:
                            await bot.http.delete_global_command(bot.user.id, cmd_id)
                            logger.info(f"Successfully deleted global command: {cmd_name}")
                        except Exception as e:
                            logger.error(f"Error deleting global command {cmd_name}: {e}")
                    
                    # Force sync with empty command list to clear all commands
                    logger.info(f"Syncing empty command list to guild {guild_name}")
                    await bot.sync_commands(guild_ids=[guild_id], commands=[])
                    
                except Exception as e:
                    logger.error(f"Error cleaning up commands for guild {guild_name}: {e}")
            
            # Also sync globally with empty command list
            try:
                logger.info("Syncing empty command list globally")
                await bot.sync_commands(commands=[])
                logger.info("Global commands have been cleared")
            except Exception as e:
                logger.error(f"Error clearing global commands: {e}")
            
            logger.info("Command cleanup complete!")
            await bot.close()
        
        # Start the bot
        logger.info("Starting the bot for cleanup...")
        await bot.start(token)
        
    except Exception as e:
        logger.error(f"Error in main: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # Run the main function in the event loop
    asyncio.run(main())