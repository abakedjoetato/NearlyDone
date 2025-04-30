"""
Direct Discord Command Registration

This script directly registers slash commands with Discord using py-cord's built-in tree sync.
"""

import os
import asyncio
import logging
import sys
import discord
from discord.ext import commands
from pathlib import Path
from dotenv import load_dotenv

# Configure logging to show everything in console
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)  # Log everything to stdout for visibility
    ]
)
logger = logging.getLogger("direct_register")

# Load environment variables
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

async def main():
    """Main function to register commands directly"""
    if not TOKEN:
        logger.error("ERROR: No DISCORD_TOKEN found in environment variables")
        return

    try:
        # Set up intents
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.guilds = True

        # Create a bot instance with our intents
        logger.info("Creating bot instance with intents")
        bot = commands.Bot(command_prefix="!", intents=intents)

        # Define our startup process
        @bot.event
        async def on_ready():
            logger.info(f"Bot connected! Logged in as {bot.user}")
            logger.info(f"Connected to {len(bot.guilds)} guilds")

            # Add our basic slash commands directly without cogs
            logger.info("Registering basic commands")
            
            # Basic ping command
            @bot.slash_command(name="ping", description="Check the bot's response time")
            async def ping(ctx):
                await ctx.respond("Pong!")
            
            # Commands menu
            @bot.slash_command(name="commands", description="Shows available commands")
            async def commands_menu(ctx):
                await ctx.respond("Command menu would go here...")
            
            # Server commands group
            server = bot.create_group("server", "Server management commands")
            
            @server.command(name="list", description="List all configured servers")
            async def server_list(ctx):
                await ctx.respond("Server list would go here...")
            
            @server.command(name="info", description="View detailed information about a server")
            async def server_info(ctx, server: discord.Option(str, "Server to get info about", required=False)):
                await ctx.respond(f"Info for server: {server or 'Default'}")
            
            @server.command(name="add", description="Add a new server to monitor")
            async def server_add(ctx, 
                               name: discord.Option(str, "A name for the server", required=True),
                               host: discord.Option(str, "Server IP address or hostname", required=True),
                               port: discord.Option(int, "SSH port (usually 22)", required=True),
                               username: discord.Option(str, "SSH/SFTP username", required=True),
                               password: discord.Option(str, "SSH/SFTP password", required=True),
                               serverid: discord.Option(str, "Unique server ID used in directory names", required=True)):
                await ctx.respond(f"Adding server: {name}")
            
            # Killfeed commands group
            killfeed = bot.create_group("killfeed", "View and analyze player kills")
            
            @killfeed.command(name="recent", description="Show recent kill events")
            async def killfeed_recent(ctx, count: discord.Option(int, "Number of events to show", required=False, default=10)):
                await ctx.respond(f"Showing {count} recent killfeed events")
            
            @killfeed.command(name="search", description="Search for specific kill events")
            async def killfeed_search(ctx, player: discord.Option(str, "Player name to search for", required=False)):
                await ctx.respond(f"Killfeed search for player: {player or 'all'}")
                
            @killfeed.command(name="weapon", description="View weapon usage and kill statistics")
            async def killfeed_weapon(ctx, weapon: discord.Option(str, "Weapon to show statistics for", required=False)):
                await ctx.respond(f"Killfeed stats for weapon: {weapon or 'all'}")
            
            # Stats commands group
            stats = bot.create_group("stats", "Player and server statistics")
            
            @stats.command(name="player", description="Show statistics for a specific player")
            async def stats_player(ctx, player: discord.Option(str, "Player name to show stats for", required=True)):
                await ctx.respond(f"Stats for player: {player}")
            
            @stats.command(name="top", description="Show top players by various metrics")
            async def stats_top(ctx, category: discord.Option(str, "Category to rank players by", required=False, default="kills")):
                await ctx.respond(f"Top players by {category}")
            
            @stats.command(name="server", description="Show overall server statistics")
            async def stats_server(ctx, server: discord.Option(str, "Server to show statistics for", required=False)):
                await ctx.respond(f"Stats for server: {server or 'all'}")
            
            # Missions commands group
            missions = bot.create_group("missions", "Server mission information")
            
            @missions.command(name="active", description="Show currently active missions")
            async def missions_active(ctx, server: discord.Option(str, "Server to show active missions for", required=False)):
                await ctx.respond(f"Active missions for server: {server or 'all'}")
            
            @missions.command(name="history", description="Show mission history")
            async def missions_history(ctx, server: discord.Option(str, "Server to show mission history for", required=False)):
                await ctx.respond(f"Mission history for server: {server or 'all'}")
            
            @missions.command(name="stats", description="Show mission statistics")
            async def missions_stats(ctx, server: discord.Option(str, "Server to show mission stats for", required=False)):
                await ctx.respond(f"Mission stats for server: {server or 'all'}")
            
            # Connections commands group
            connections = bot.create_group("connections", "Player connection information")
            
            @connections.command(name="recent", description="Show recent player connections")
            async def connections_recent(ctx, count: discord.Option(int, "Number of connections to show", required=False, default=10)):
                await ctx.respond(f"Showing {count} recent connections")
            
            @connections.command(name="search", description="Search for connections by player")
            async def connections_search(ctx, player: discord.Option(str, "Player name to search for", required=True)):
                await ctx.respond(f"Connection history for player: {player}")
            
            @connections.command(name="status", description="Show current server connection status")
            async def connections_status(ctx, server: discord.Option(str, "Server to show connection status for", required=False)):
                await ctx.respond(f"Connection status for server: {server or 'all'}")
            
            # Now sync all commands with Discord
            logger.info("Now syncing commands with Discord")
            
            for guild in bot.guilds:
                logger.info(f"Syncing commands for guild: {guild.name} (ID: {guild.id})")
                try:
                    # Sync commands to this specific guild
                    await bot.sync_commands(guild_ids=[guild.id])
                    logger.info(f"✓ Successfully synced commands to {guild.name}")
                except Exception as e:
                    logger.error(f"Failed to sync commands to {guild.name}: {e}")
            
            logger.info("Command registration complete! Exiting...")
            await bot.close()

        # Start the bot
        logger.info("Starting the bot to register commands...")
        await bot.start(TOKEN)
        
    except Exception as e:
        logger.error(f"Error in direct registration: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Script stopped by user")
    except Exception as e:
        logger.error(f"Error running script: {e}")
        import traceback
        traceback.print_exc()