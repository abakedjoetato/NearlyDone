"""
Discord Bot Command Registration Script

This script defines and registers all the commands normally defined in the cogs,
but in a direct and simplified way, to avoid any issues with command registration.
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
        logging.FileHandler('logs/command_registration.log', mode='w')
    ]
)

logger = logging.getLogger("command_registration")

# Load environment variables
load_dotenv()

async def main():
    logger.info("Discord Bot Command Registration")
    logger.info("==============================")
    
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        logger.error("ERROR: No DISCORD_TOKEN found in environment variables")
        return
    
    # Import Discord libraries
    try:
        import discord
        from discord.ext import commands
    except ImportError:
        logger.error("ERROR: Failed to import Discord libraries")
        return
    
    # Create an instance of the bot with minimal configuration
    bot = commands.Bot(command_prefix="!", intents=discord.Intents.default())
    
    # Define all commands directly here
    
    # Simple ping command to test connectivity
    @bot.slash_command(name="ping", description="Check the bot's response time")
    async def ping(ctx):
        await ctx.respond("🏓 Pong! Bot is online.")
    
    # Server commands
    server_commands = bot.create_group(name="server", description="Server management commands")
    
    @server_commands.command(name="list", description="List all configured servers")
    async def server_list(ctx):
        await ctx.respond("Command registered: server list")
    
    @server_commands.command(name="info", description="View detailed information about a server")
    async def server_info(ctx, server: str = None):
        await ctx.respond(f"Command registered: server info {server or 'default'}")
        
    @server_commands.command(name="add", description="Add a new server to monitor")
    async def server_add(ctx):
        await ctx.respond("Command registered: server add")
    
    # Killfeed commands
    killfeed_commands = bot.create_group(name="killfeed", description="View and analyze player kills")
    
    @killfeed_commands.command(name="recent", description="Show recent kill events")
    async def killfeed_recent(ctx, count: int = 10):
        await ctx.respond(f"Command registered: killfeed recent {count}")
    
    @killfeed_commands.command(name="search", description="Search for specific kill events")
    async def killfeed_search(ctx, player: str = None):
        await ctx.respond(f"Command registered: killfeed search {player or 'any'}")
    
    @killfeed_commands.command(name="weapon", description="View weapon usage and kill statistics")
    async def killfeed_weapon(ctx, weapon: str = None):
        await ctx.respond(f"Command registered: killfeed weapon {weapon or 'all'}")
    
    # Stats commands
    stats_commands = bot.create_group(name="stats", description="Player and server statistics")
    
    @stats_commands.command(name="player", description="Show statistics for a specific player")
    async def stats_player(ctx, player: str):
        await ctx.respond(f"Command registered: stats player {player}")
    
    @stats_commands.command(name="top", description="Show top players by various metrics")
    async def stats_top(ctx, category: str = "kills"):
        await ctx.respond(f"Command registered: stats top {category}")
    
    @stats_commands.command(name="server", description="Show overall server statistics")
    async def stats_server(ctx, server: str = None):
        await ctx.respond(f"Command registered: stats server {server or 'default'}")
    
    # Mission commands
    mission_commands = bot.create_group(name="missions", description="Server mission information")
    
    @mission_commands.command(name="active", description="Show currently active missions")
    async def missions_active(ctx, server: str = None):
        await ctx.respond(f"Command registered: missions active {server or 'default'}")
    
    @mission_commands.command(name="history", description="Show mission history")
    async def missions_history(ctx, server: str = None):
        await ctx.respond(f"Command registered: missions history {server or 'default'}")
    
    @mission_commands.command(name="stats", description="Show mission statistics")
    async def missions_stats(ctx, server: str = None):
        await ctx.respond(f"Command registered: missions stats {server or 'default'}")
    
    # Connection commands
    connection_commands = bot.create_group(name="connections", description="Player connection information")
    
    @connection_commands.command(name="recent", description="Show recent player connections")
    async def connections_recent(ctx, count: int = 10):
        await ctx.respond(f"Command registered: connections recent {count}")
    
    @connection_commands.command(name="search", description="Search for connections by player")
    async def connections_search(ctx, player: str):
        await ctx.respond(f"Command registered: connections search {player}")
    
    @connection_commands.command(name="status", description="Show current server connection status")
    async def connections_status(ctx, server: str = None):
        await ctx.respond(f"Command registered: connections status {server or 'default'}")
    
    # Commands menu command
    @bot.slash_command(name="commands", description="Shows all available commands")
    async def commands_menu(ctx):
        await ctx.respond("Command registered: commands")
    
    @bot.event
    async def on_ready():
        logger.info(f"Bot is ready! Logged in as {bot.user}")
        
        # Now that all commands are defined, sync them to Discord
        try:
            logger.info("Syncing commands to all guilds...")
            # Sync to all guilds the bot is in
            for guild in bot.guilds:
                logger.info(f"Syncing commands to guild: {guild.name} ({guild.id})")
                await bot.sync_commands(guild_ids=[guild.id])
                logger.info(f"✅ Commands synced to guild: {guild.name}")
                await asyncio.sleep(10)  # Add delay between guild syncs
            
            logger.info("✅ Command registration complete!")
        except Exception as e:
            logger.error(f"Error during command sync: {e}")
        
        # Wait a moment before shutting down
        await asyncio.sleep(5)
        await bot.close()
    
    # Run the bot
    try:
        await bot.start(token)
    except Exception as e:
        logger.error(f"Error starting bot: {e}")
    finally:
        if not bot.is_closed():
            await bot.close()

if __name__ == "__main__":
    asyncio.run(main())