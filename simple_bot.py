"""
Simple Discord Bot with Command Registration

This is a completely standalone script that creates a minimal Discord bot
with slash commands. It doesn't rely on any of the existing codebase.
"""

import os
import asyncio
import logging
import sys
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,  # Use DEBUG level to see everything
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger("simple_bot")

# Load environment variables
load_dotenv()

async def main():
    logger.info("Starting Simple Discord Bot")
    
    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        logger.error("No DISCORD_TOKEN found in environment variables")
        return
    
    try:
        # Import Discord libraries here to ensure clean environment
        import discord
        from discord.ext import commands
        
        # Set up intents
        intents = discord.Intents.default()
        intents.message_content = True
        
        # Create a simple bot instance
        bot = commands.Bot(command_prefix="!", intents=intents)
        
        # Define a simple ping command
        @bot.slash_command(name="ping", description="Checks if the bot is responding")
        async def ping(ctx):
            await ctx.respond("Pong! I'm alive!")
            
        # Define a simple command group
        test_group = bot.create_group(name="test", description="Test commands")
        
        @test_group.command(name="echo", description="Repeats your message")
        async def test_echo(ctx, message: str):
            await ctx.respond(f"You said: {message}")
            
        @test_group.command(name="random", description="Gives a random number")
        async def test_random(ctx, max_number: int = 100):
            import random
            number = random.randint(1, max_number)
            await ctx.respond(f"Your random number is: {number}")
        
        # On ready event handler
        @bot.event
        async def on_ready():
            logger.info(f"Bot is ready! Logged in as {bot.user}")
            
            # First, check what guilds we're in
            logger.info(f"Connected to {len(bot.guilds)} guilds:")
            for guild in bot.guilds:
                logger.info(f"  - {guild.name} (ID: {guild.id})")
            
            # Attempt to sync commands for each guild individually
            for guild in bot.guilds:
                logger.info(f"Syncing commands to guild: {guild.name} (ID: {guild.id})")
                try:
                    # Force guild-specific sync
                    synced = await bot.sync_commands(guild_ids=[guild.id])
                    logger.info(f"Synced {len(synced)} commands to {guild.name}")
                    
                    # Print details of synced commands
                    for cmd in synced:
                        logger.info(f"  - Synced command: {cmd.name}")
                        if hasattr(cmd, 'options') and cmd.options:
                            for option in cmd.options:
                                if hasattr(option, 'name'):
                                    logger.info(f"    - Subcommand/option: {option.name}")
                except Exception as e:
                    logger.error(f"Error syncing commands to {guild.name}: {e}")
            
            # Also sync globally as a fallback
            try:
                logger.info("Also syncing commands globally as a fallback")
                synced = await bot.sync_commands()
                logger.info(f"Synced {len(synced)} commands globally")
            except Exception as e:
                logger.error(f"Error syncing commands globally: {e}")
                
            logger.info("Command registration complete!")
            
            # Keep the bot running to maintain the commands
            logger.info("Bot will remain online. Press Ctrl+C to stop.")
        
        # Start the bot
        logger.info("Starting the bot...")
        await bot.start(token)
        
    except Exception as e:
        logger.error(f"Error in simple bot: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # Run the main function in the event loop
    asyncio.run(main())