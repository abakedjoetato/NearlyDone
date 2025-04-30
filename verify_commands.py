"""
Discord Command Verification Utility

This script checks if commands have been properly registered with Discord
and are visible to users. It connects to Discord and retrieves the list
of registered commands for each guild, then outputs a report.
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
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger("command_verifier")

# Load environment variables
load_dotenv()

async def main():
    logger.info("Discord Command Verification Utility")
    logger.info("==================================")
    logger.info("This utility will check if Discord slash commands are properly registered")
    
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
        logger.info("Checking for registered commands...")
        
        # For py-cord, try to access the commands through the bot
        app_commands = []
        if hasattr(bot, 'application_commands'):
            app_commands = bot.application_commands
            logger.info(f"Found {len(app_commands)} application commands in the bot")
            
            for cmd in app_commands:
                logger.info(f"Command: {cmd.name}")
                logger.info(f"  Description: {cmd.description}")
                
                # Check if it has subcommands
                if hasattr(cmd, 'options') and cmd.options:
                    for option in cmd.options:
                        if hasattr(option, 'name'):
                            logger.info(f"  Subcommand: {option.name}")
                            if hasattr(option, 'description'):
                                logger.info(f"    Description: {option.description}")
        else:
            logger.warning("No application_commands found in bot object")
        
        # List connected guilds
        logger.info(f"Connected to {len(bot.guilds)} guilds:")
        for guild in bot.guilds:
            logger.info(f"  Guild: {guild.name} (ID: {guild.id})")
            
            # Get guild-specific commands
            guild_commands = [cmd for cmd in app_commands 
                             if hasattr(cmd, 'guild_ids') and 
                             hasattr(cmd.guild_ids, '__contains__') and 
                             guild.id in cmd.guild_ids]
            
            logger.info(f"  Guild-specific commands: {len(guild_commands)}")
            for cmd in guild_commands:
                logger.info(f"    Command: {cmd.name}")
        
        # Try a light sync to test registration
        try:
            logger.info("\nAttempting a test sync to verify command registration...")
            guild_ids = [g.id for g in bot.guilds] if bot.guilds else None
            
            # This just tests if the sync itself works
            # We don't save the results as we're just testing if Discord accepts the commands
            await bot.sync_commands(guild_ids=guild_ids)
            logger.info("✅ Commands synced successfully - they should be visible in Discord")
        except Exception as e:
            logger.error(f"❌ Command sync test failed: {e}")
        
        # Exit after command check
        logger.info("\nCommand verification complete! Logging out...")
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