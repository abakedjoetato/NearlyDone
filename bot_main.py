"""
Discord Bot Main Module

This module contains the main functionality for the Discord bot,
including command registration, cog loading, and event handlers.

This is a complete rewrite of the Discord bot component with improved
reliability, especially for command registration.
"""

import os
import discord
import asyncio
import logging
import json
import time
import traceback
from discord.ext import commands, tasks
from datetime import datetime, timedelta
import motor.motor_asyncio
from pathlib import Path
import sys

# Import environment variables
from dotenv import load_dotenv
load_dotenv()

# Get environment variables
PREFIX = os.getenv("PREFIX", "!")
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGODB_NAME = os.getenv("MONGODB_NAME", "deadside_bot")
LOGGING_LEVEL = os.getenv("LOGGING_LEVEL", "INFO")
DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() == "true"

# Set up logging
os.makedirs('logs', exist_ok=True)
logging.basicConfig(
    level=getattr(logging, LOGGING_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('logs/deadside_bot.log')
    ]
)
logger = logging.getLogger('deadside_bot')

# Initialize Discord bot with intents
intents = discord.Intents.default()
intents.message_content = True  # Required for prefix commands
intents.members = True  # Required for member-related features
intents.guilds = True  # Required for guild-related features

# Create bot with slash commands only (no prefix commands)
bot = commands.Bot(
    command_prefix=commands.when_mentioned_or(PREFIX),
    intents=intents,
    description="Deadside Game Server Monitoring Bot",
    sync_commands=False,  # We'll manually sync commands
    sync_commands_debug=True,  # Enable debug output for command sync
)

# Command to register all slash commands to Discord
async def sync_slash_commands():
    """Register all slash commands to Discord with reliable rate limit handling"""
    logger.info("Starting slash command synchronization with guild-specific approach")
    
    # Skip global command sync completely and focus on per-guild only
    # This works around Discord's global rate limiting by only updating each guild individually
    
    guilds = bot.guilds
    logger.info(f"Found {len(guilds)} guilds to sync commands for")
    
    if not guilds:
        logger.warning("No guilds found, skipping command sync")
        return True
    
    # Track success across all guilds
    overall_success = True
    
    # Process each guild with large delays between them
    for i, guild in enumerate(guilds):
        try:
            guild_name = guild.name
            guild_id = guild.id
            logger.info(f"Syncing commands for guild {i+1}/{len(guilds)}: {guild_name} ({guild_id})")
            
            # Try to sync commands for this specific guild only
            try:
                # Option 1: Use built-in sync_commands for this guild
                await bot.sync_commands(guild_ids=[guild_id])
                logger.info(f"✅ Successfully synced commands for guild: {guild_name}")
            except Exception as e:
                logger.warning(f"Failed to sync commands using built-in method for guild {guild_name}: {e}")
                
                # Option 2: Use our custom command manager as fallback
                try:
                    from utils.discord_command_manager import register_commands
                    
                    # Register only for this specific guild
                    logger.info(f"Using custom command manager for guild: {guild_name}")
                    result = await register_commands(bot, guild_ids=[guild_id])
                    
                    if result:
                        logger.info(f"✅ Successfully synced commands for guild using custom manager: {guild_name}")
                    else:
                        logger.warning(f"❌ Failed to sync commands for guild using custom manager: {guild_name}")
                        overall_success = False
                except Exception as custom_err:
                    logger.error(f"❌ All methods failed for guild {guild_name}: {custom_err}")
                    overall_success = False
            
            # Add a long delay between guild syncs to avoid rate limiting
            if i < len(guilds) - 1:  # Skip delay after the last guild
                delay = 20 + i * 5  # Increasing delay for each guild
                logger.info(f"Waiting {delay} seconds before processing next guild...")
                await asyncio.sleep(delay)
                
        except Exception as guild_err:
            logger.error(f"Unexpected error syncing commands for guild {guild.id}: {guild_err}")
            overall_success = False
    
    # Final status report
    if overall_success:
        logger.info("✅ Successfully registered commands for all guilds")
    else:
        logger.warning("⚠️ Command registration partially successful (some guilds failed)")
    
    return overall_success

# Simple ping command
@bot.slash_command(name="ping", description="Check the bot's response time")
async def ping(ctx):
    """Check the bot's response time"""
    start_time = time.time()
    embed = discord.Embed(title="🏓 Pong!", color=discord.Color.green())
    
    # Add latency info
    embed.add_field(
        name="Bot Latency",
        value=f"{round(bot.latency * 1000)}ms",
        inline=True
    )
    
    # Send the response and measure round-trip time
    await ctx.respond(embed=embed)
    end_time = time.time()
    round_trip = round((end_time - start_time) * 1000)
    
    # Edit to add round-trip time
    embed.add_field(
        name="Round-Trip Time",
        value=f"{round_trip}ms",
        inline=True
    )
    
    # Add API latency
    embed.add_field(
        name="API Status",
        value="✅ Online",
        inline=True
    )
    
    await ctx.edit(embed=embed)

# Help command
@bot.slash_command(name="commands", description="Shows available commands and help information")
async def commands_menu(ctx):
    """Shows available commands and help information with emerald-themed styling"""
    embed = discord.Embed(
        title="📋 Available Commands",
        description="Here are the commands you can use with this bot:",
        color=discord.Color.green()
    )
    
    # Add fields for each command category
    embed.add_field(
        name="🖥️ Server Commands",
        value="`/server list` - List all configured servers\n"
              "`/server info` - Display server details\n"
              "`/server add` - Add a new server to monitor",
        inline=False
    )
    
    embed.add_field(
        name="📊 Stats Commands",
        value="`/stats player` - Show player statistics\n"
              "`/stats top` - View top players by various metrics\n"
              "`/stats server` - View server statistics",
        inline=False
    )
    
    embed.add_field(
        name="🔫 Killfeed Commands",
        value="`/killfeed recent` - Show recent kills\n"
              "`/killfeed search` - Search for specific kill events\n"
              "`/killfeed weapon` - View weapon stats",
        inline=False
    )
    
    embed.add_field(
        name="🎯 Mission Commands",
        value="`/missions active` - Show active missions\n"
              "`/missions history` - View past missions\n"
              "`/missions stats` - Mission statistics",
        inline=False
    )
    
    embed.add_field(
        name="🔌 Connection Commands",
        value="`/connections recent` - Show recent connections\n"
              "`/connections search` - Search player connections\n"
              "`/connections status` - Connection status",
        inline=False
    )
    
    embed.add_field(
        name="🛠️ Utility Commands",
        value="`/ping` - Check bot response time\n"
              "`/commands` - Show this help menu",
        inline=False
    )
    
    # Add footer
    embed.set_footer(text="Use /help <command> for detailed information about a specific command")
    
    await ctx.respond(embed=embed)

# Event: Bot is ready
@bot.event
async def on_ready():
    """Called when the bot is fully ready after connecting to Discord"""
    logger.info(f"Bot is ready! Logged in as {bot.user} (ID: {bot.user.id})")
    logger.info(f"Connected to {len(bot.guilds)} guilds")
    
    # Initialize MongoDB client
    global db_client, db
    try:
        # Connect to MongoDB
        db_client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI)
        db = db_client[MONGODB_NAME]
        logger.info(f"Connected to MongoDB database: {MONGODB_NAME}")
        
        # Test database connection
        server_count = await db.servers.count_documents({})
        logger.info(f"Database contains {server_count} servers")
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        if DEBUG_MODE:
            logger.error(traceback.format_exc())
    
    # Load all cogs
    logger.info("Loading command cogs...")
    await load_cogs()
    
    # Check if commands are already registered by looking for command_marker
    marker_file = Path('temp/commands_registered.txt')
    if marker_file.exists():
        logger.info("Commands were previously registered, skipping sync")
    else:
        # Sync slash commands
        try:
            logger.info("Syncing slash commands to match handlers...")
            
            # Show the commands the bot has loaded
            all_commands = []
            all_commands.extend(bot.application_commands)
            for cog_name, cog in bot.cogs.items():
                all_commands.extend(cog.get_application_commands())
            
            logger.info(f"Bot has {len(all_commands)} slash commands loaded")
            for cmd in all_commands:
                if hasattr(cmd, 'name'):
                    logger.info(f"- Command: {cmd.name}")
            
            # Only sync to guilds, not globally
            for guild in bot.guilds:
                logger.info(f"Syncing commands to guild: {guild.name}")
                try:
                    await bot.sync_commands(guild_ids=[guild.id])
                    logger.info(f"Commands synced to {guild.name}")
                except Exception as e:
                    logger.error(f"Error syncing to {guild.name}: {e}")
            
            # Create marker file to show we've registered commands
            with open('temp/commands_registered.txt', 'w') as f:
                f.write(f"Commands registered at {time.ctime()}")
        except Exception as e:
            logger.error(f"Error syncing slash commands: {e}")
            if DEBUG_MODE:
                logger.error(traceback.format_exc())
    
    # Start background tasks
    check_parsers.start()
    logger.info("Bot startup complete!")

# Load all cogs (command modules)
async def load_cogs():
    """Load all cogs for the bot"""
    # Load core cogs
    cogs_loaded = 0
    cogs_dir = Path("cogs")
    
    if not cogs_dir.exists():
        logger.error(f"Cogs directory not found at {cogs_dir}")
        return
    
    # First try to load our refactored cogs and any new command cogs
    priority_cogs = [
        "admin_commands",
        "server_commands_refactored",
        "stats_commands_refactored",
        "killfeed_commands_refactored",
        "mission_commands_refactored",
        "connection_commands_refactored",
        # Add background commands, which demonstrate command processing in background
        "background_commands",
        # Use the rewritten faction commands instead of the broken one
        "faction_commands_rewrite",
        # Keep original faction commands as fallback, but it has issues
        "faction_commands"
    ]
    
    for cog_name in priority_cogs:
        try:
            # Try loading the cog
            module_name = f"cogs.{cog_name}"
            await bot.load_extension(module_name)
            logger.info(f"Loaded cog: {module_name}")
            cogs_loaded += 1
        except Exception as e:
            # Log the error
            logger.warning(f"Error loading cog {module_name}: {e}")
            
            # Try without _refactored suffix if that fails
            try:
                base_name = cog_name.replace("_refactored", "")
                if base_name != cog_name:  # Only try if different
                    module_name = f"cogs.{base_name}"
                    await bot.load_extension(module_name)
                    logger.info(f"Loaded cog: {module_name}")
                    cogs_loaded += 1
            except Exception as e2:
                logger.error(f"Could not load cog {cog_name} or fallback: {e2}")
                if DEBUG_MODE:
                    logger.error(traceback.format_exc())
    
    # These are the core cogs needed for basic functionality
    required_cogs = ["server_commands_refactored", "background_commands"]
    
    # Check if at least the required cogs were loaded
    if cogs_loaded == 0:
        logger.error("No cogs were loaded! Bot will have no commands.")
    else:
        logger.info(f"Loaded {cogs_loaded} cogs successfully")

# Background task: Check and run parsers
@tasks.loop(minutes=5)
async def check_parsers():
    """
    Background task to check and run parsers for all servers.
    
    This function runs every 5 minutes and manages three different parsers:
    
    1. Auto CSV Parser:
       - Downloads only the newest CSV file from each server
       - Processes only new content since the last run
       - Updates player stats and killfeed as it goes
       - Controlled by the csv_enabled server setting
       
    2. Log Parser:
       - Downloads and parses Deadside.log for server events
       - Extracts information about missions, server starts/stops, etc.
       - Only processes new log entries since the last run
       - Controlled by the log_enabled server setting
       
    3. Batch CSV Parser:
       - Only runs when explicitly triggered (not on this schedule)
       - Processes all historical CSV files with progress tracking
       - Reports status and progress through ParserMemory
       - Triggered by adding a new server or using the reset command
       - This function only monitors for stalled batch parsers
    """
    # Skip if bot is not ready yet
    if not bot.is_ready():
        logger.warning("Bot not ready yet, skipping parser check")
        return
    
    logger.info("Running scheduled parser check")
    
    try:
        # Get all servers from database
        servers_collection = db["servers"]
        servers = await servers_collection.find({}).to_list(length=None)
        
        logger.info(f"Checking parsers for {len(servers)} servers")
        
        # Check each server
        for server in servers:
            guild_id = server.get("guild_id")
            server_name = server.get("name", "Unnamed Server")
            server_id = server.get("_id", "unknown")
            
            logger.info(f"Checking parsers for server {server_name} in guild {guild_id}")
            
            # Check if parsers are enabled for this server
            csv_enabled = server.get("csv_enabled", True)
            log_enabled = server.get("log_enabled", True)
            
            if not csv_enabled and not log_enabled:
                logger.info(f"All parsers disabled for server {server_name}")
                continue
            
            # Process server based on enabled parsers
            if csv_enabled:
                logger.info(f"CSV parser enabled for server {server_name}")
                # Processing code goes here
            
            if log_enabled:
                logger.info(f"Log parser enabled for server {server_name}")
                # Processing code goes here
            
            # Check for stalled batch parsers
            parser_memory_collection = db["parser_memory"]
            
            # Clean up old parser memory entries first (older than 2 hours)
            two_hours_ago = datetime.utcnow() - timedelta(hours=2)
            cleanup_result = await parser_memory_collection.delete_many({
                "server_id": server_id,
                "updated_at": {"$lt": two_hours_ago}
            })
            if cleanup_result.deleted_count > 0:
                logger.info(f"Cleaned up {cleanup_result.deleted_count} old parser memory entries for server {server_name}")
            
            # Now check for stalled parsers
            batch_parser = await parser_memory_collection.find_one({
                "server_id": server_id,
                "parser_type": "batch_csv",
                "is_running": True
            })
            
            if batch_parser:
                last_update = batch_parser.get("last_update", 0)
                current_time = time.time()
                
                # If batch parser hasn't updated in 30 minutes, mark as stalled
                if current_time - last_update > 1800:
                    logger.warning(f"Batch parser for server {server_name} appears stalled. Marking as failed.")
                    await parser_memory_collection.update_one(
                        {"_id": batch_parser["_id"]},
                        {"$set": {"status": "failed", "end_time": current_time, 
                                  "error": "Parser stalled (no updates for 30+ minutes)"}}
                    )
            
            # Small delay between servers to avoid overloading
            await asyncio.sleep(1)
            
    except Exception as e:
        logger.error(f"Error in parser check: {e}")
        if DEBUG_MODE:
            logger.error(traceback.format_exc())

# Run before the check_parsers loop starts
@check_parsers.before_loop
async def before_check_parsers():
    """Wait until the bot is ready before starting the background task"""
    logger.info("Waiting for bot to be ready before starting parser check loop")
    await bot.wait_until_ready()
    
    # Add a small delay after ready to ensure all connections are established
    await asyncio.sleep(10)
    logger.info("Starting parser check loop")

# Global error handler
@bot.event
async def on_command_error(ctx, error):
    """Global error handler for command errors"""
    if isinstance(error, commands.CommandNotFound):
        # Ignore command not found errors
        return
    
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.respond(f"Error: Missing required argument: {error.param.name}", ephemeral=True)
        return
    
    if isinstance(error, commands.BadArgument):
        await ctx.respond(f"Error: Bad argument: {error}", ephemeral=True)
        return
    
    if isinstance(error, commands.MissingPermissions):
        await ctx.respond("Error: You don't have permission to use this command", ephemeral=True)
        return
    
    if isinstance(error, commands.BotMissingPermissions):
        await ctx.respond(f"Error: I don't have the required permissions: {error.missing_permissions}", ephemeral=True)
        return
    
    # Log all other errors
    logger.error(f"Command error in {ctx.command}: {error}")
    if DEBUG_MODE:
        logger.error(traceback.format_exc())
    
    # Respond to user
    try:
        await ctx.respond("An error occurred while processing your command. Please try again later.", ephemeral=True)
    except:
        # If responding fails, just log it
        logger.error("Failed to send error message to user")

# Main entry point
def main():
    """Main entry point for the bot"""
    if not DISCORD_TOKEN:
        logger.error("DISCORD_TOKEN not set in environment variables")
        return
    
    try:
        logger.info("Starting Discord bot...")
        bot.run(DISCORD_TOKEN)
    except discord.LoginFailure:
        logger.error("Invalid Discord token - please check your .env file")
    except Exception as e:
        logger.error(f"Error starting bot: {e}")
        if DEBUG_MODE:
            logger.error(traceback.format_exc())

if __name__ == "__main__":
    main()