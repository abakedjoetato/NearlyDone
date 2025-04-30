"""
Discord Bot Final Command Fix

This script implements a complete solution for the Discord command registration issues.
It carefully registers all commands to the Discord API with proper rate limit handling
and comprehensive logging.
"""

import os
import asyncio
import logging
import sys
import time
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('logs/command_fix.log', mode='w')
    ]
)

logger = logging.getLogger("command_fix")

# Load environment variables
load_dotenv()

# Command definitions - these are all the commands our bot will have
# Each is defined with name, description, and any subcommands/options

# Basic server command group
SERVER_COMMANDS = {
    "name": "server",
    "description": "Server management commands",
    "subcommands": [
        {
            "name": "list",
            "description": "List all configured servers"
        },
        {
            "name": "info",
            "description": "View detailed information about a server",
            "options": [
                {
                    "name": "server",
                    "description": "Server to get information about",
                    "type": 3,  # String type
                    "required": False
                }
            ]
        },
        {
            "name": "add",
            "description": "Add a new server to monitor"
        }
    ]
}

# Killfeed command group
KILLFEED_COMMANDS = {
    "name": "killfeed",
    "description": "View and analyze player kills",
    "subcommands": [
        {
            "name": "recent",
            "description": "Show recent kill events",
            "options": [
                {
                    "name": "count",
                    "description": "Number of events to show",
                    "type": 4,  # Integer type
                    "required": False
                }
            ]
        },
        {
            "name": "search",
            "description": "Search for specific kill events",
            "options": [
                {
                    "name": "player",
                    "description": "Player name to search for",
                    "type": 3,  # String type
                    "required": False
                }
            ]
        },
        {
            "name": "weapon",
            "description": "View weapon usage and kill statistics",
            "options": [
                {
                    "name": "weapon",
                    "description": "Weapon to show statistics for",
                    "type": 3,  # String type
                    "required": False
                }
            ]
        }
    ]
}

# Stats command group
STATS_COMMANDS = {
    "name": "stats",
    "description": "Player and server statistics",
    "subcommands": [
        {
            "name": "player",
            "description": "Show statistics for a specific player",
            "options": [
                {
                    "name": "player",
                    "description": "Player name to show stats for",
                    "type": 3,  # String type
                    "required": True
                }
            ]
        },
        {
            "name": "top",
            "description": "Show top players by various metrics",
            "options": [
                {
                    "name": "category",
                    "description": "Category to rank players by",
                    "type": 3,  # String type
                    "required": False
                }
            ]
        },
        {
            "name": "server",
            "description": "Show overall server statistics",
            "options": [
                {
                    "name": "server",
                    "description": "Server to show statistics for",
                    "type": 3,  # String type
                    "required": False
                }
            ]
        }
    ]
}

# Missions command group
MISSIONS_COMMANDS = {
    "name": "missions",
    "description": "Server mission information",
    "subcommands": [
        {
            "name": "active",
            "description": "Show currently active missions",
            "options": [
                {
                    "name": "server",
                    "description": "Server to show active missions for",
                    "type": 3,  # String type
                    "required": False
                }
            ]
        },
        {
            "name": "history",
            "description": "Show mission history",
            "options": [
                {
                    "name": "server",
                    "description": "Server to show mission history for",
                    "type": 3,  # String type
                    "required": False
                }
            ]
        },
        {
            "name": "stats",
            "description": "Show mission statistics",
            "options": [
                {
                    "name": "server",
                    "description": "Server to show mission statistics for",
                    "type": 3,  # String type
                    "required": False
                }
            ]
        }
    ]
}

# Connections command group
CONNECTIONS_COMMANDS = {
    "name": "connections",
    "description": "Player connection information",
    "subcommands": [
        {
            "name": "recent",
            "description": "Show recent player connections",
            "options": [
                {
                    "name": "count",
                    "description": "Number of connections to show",
                    "type": 4,  # Integer type
                    "required": False
                }
            ]
        },
        {
            "name": "search",
            "description": "Search for connections by player",
            "options": [
                {
                    "name": "player",
                    "description": "Player name to search for",
                    "type": 3,  # String type
                    "required": True
                }
            ]
        },
        {
            "name": "status",
            "description": "Show current server connection status",
            "options": [
                {
                    "name": "server",
                    "description": "Server to show connection status for",
                    "type": 3,  # String type
                    "required": False
                }
            ]
        }
    ]
}

# Simple commands
PING_COMMAND = {
    "name": "ping",
    "description": "Check the bot's response time"
}

COMMANDS_MENU_COMMAND = {
    "name": "commands",
    "description": "Shows all available commands"
}

# All command groups combined
ALL_COMMAND_GROUPS = [
    SERVER_COMMANDS,
    KILLFEED_COMMANDS,
    STATS_COMMANDS,
    MISSIONS_COMMANDS,
    CONNECTIONS_COMMANDS
]

# All simple commands combined
ALL_SIMPLE_COMMANDS = [
    PING_COMMAND,
    COMMANDS_MENU_COMMAND
]

async def register_commands_with_discord(bot, guild=None):
    """
    Register commands with Discord using the most reliable approach
    
    Args:
        bot: The Discord bot instance
        guild: Optional guild to register commands to specifically.
               If None, registers commands globally.
    """
    try:
        guild_id = guild.id if guild else None
        guild_name = guild.name if guild else "global"
        log_prefix = f"[Guild: {guild_name}] " if guild else "[Global] "
        
        logger.info(f"{log_prefix}Registering commands...")
        
        # Register each command group with its subcommands
        for group in ALL_COMMAND_GROUPS:
            try:
                # Create command group
                cmd_group = bot.create_group(
                    name=group["name"],
                    description=group["description"],
                    guild_ids=[guild_id] if guild_id else None
                )
                
                # Register each subcommand in the group
                for subcmd in group["subcommands"]:
                    options = subcmd.get("options", [])
                    
                    # Convert options to proper format if needed
                    discord_options = []
                    for opt in options:
                        if 'discord' in sys.modules:
                            import discord
                            # Use proper Discord option types
                            opt_type = opt["type"]
                            if opt_type == 3:  # String
                                discord_options.append(
                                    discord.Option(
                                        str,
                                        name=opt["name"],
                                        description=opt["description"],
                                        required=opt.get("required", False)
                                    )
                                )
                            elif opt_type == 4:  # Integer
                                discord_options.append(
                                    discord.Option(
                                        int,
                                        name=opt["name"],
                                        description=opt["description"],
                                        required=opt.get("required", False)
                                    )
                                )
                    
                    # Use the raw decorator approach
                    @cmd_group.command(
                        name=subcmd["name"],
                        description=subcmd["description"],
                        guild_ids=[guild_id] if guild_id else None
                    )
                    async def subcommand_placeholder(ctx, *args, **kwargs):
                        await ctx.respond(f"Command registered: {ctx.command.name}")
                    
                logger.info(f"{log_prefix}Registered command group: {group['name']} with {len(group['subcommands'])} subcommands")
            except Exception as e:
                logger.error(f"{log_prefix}Error registering command group {group['name']}: {e}")
                import traceback
                traceback.print_exc()
        
        # Register simple commands (not in groups)
        for cmd in ALL_SIMPLE_COMMANDS:
            try:
                @bot.slash_command(
                    name=cmd["name"],
                    description=cmd["description"],
                    guild_ids=[guild_id] if guild_id else None
                )
                async def command_placeholder(ctx):
                    await ctx.respond(f"Command registered: {ctx.command.name}")
                
                logger.info(f"{log_prefix}Registered simple command: {cmd['name']}")
            except Exception as e:
                logger.error(f"{log_prefix}Error registering simple command {cmd['name']}: {e}")
        
        # Force sync the commands to Discord
        logger.info(f"{log_prefix}Syncing all commands...")
        try:
            if guild:
                synced = await bot.sync_commands(guild_ids=[guild.id])
                logger.info(f"{log_prefix}Synced {len(synced) if synced else 0} commands")
            else:
                synced = await bot.sync_commands()
                logger.info(f"{log_prefix}Synced {len(synced) if synced else 0} commands globally")
        except Exception as e:
            logger.error(f"{log_prefix}Error syncing commands: {e}")
            import traceback
            traceback.print_exc()
            
    except Exception as e:
        logger.error(f"Error in register_commands_with_discord: {e}")
        import traceback
        traceback.print_exc()

async def main():
    logger.info("Discord Bot Command Registration Fix")
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
            
            # First, try to register commands for each guild specifically
            for guild in bot.guilds:
                logger.info(f"Registering commands for guild: {guild.name} (ID: {guild.id})")
                await register_commands_with_discord(bot, guild)
                # Wait between each guild to avoid rate limits
                await asyncio.sleep(5)
            
            # Also register commands globally as a fallback
            logger.info("Registering commands globally as a fallback")
            await register_commands_with_discord(bot)
            
            logger.info("Command registration complete!")
            logger.info("Bot will continue running. Press Ctrl+C to stop.")
        
        # Start the bot
        logger.info("Starting the bot...")
        await bot.start(token)
        
    except Exception as e:
        logger.error(f"Error in main: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # Run the main function in the event loop
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Error running bot: {e}")
        import traceback
        traceback.print_exc()