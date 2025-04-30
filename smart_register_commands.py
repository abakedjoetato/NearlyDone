"""
Smart Discord Bot Command Registration

This script efficiently registers Discord commands by:
1. Checking existing commands
2. Only registering new commands or updating changed ones
3. Removing commands that are no longer needed
4. Avoiding unnecessary API calls to stay within rate limits
"""

import os
import asyncio
import logging
import sys
import json
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('logs/smart_register.log', mode='w')
    ]
)

logger = logging.getLogger("smart_register")

# Load environment variables
load_dotenv()

# Command definitions - same as in final_command_fix.py
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
            "description": "Add a new server to monitor",
            "options": [
                {
                    "name": "name",
                    "description": "A name for the server",
                    "type": 3,  # String type
                    "required": True
                },
                {
                    "name": "host",
                    "description": "Server IP address or hostname",
                    "type": 3,  # String type
                    "required": True
                },
                {
                    "name": "port",
                    "description": "SSH port (usually 22)",
                    "type": 4,  # Integer type
                    "required": True
                },
                {
                    "name": "username",
                    "description": "SSH/SFTP username",
                    "type": 3,  # String type
                    "required": True
                },
                {
                    "name": "password",
                    "description": "SSH/SFTP password",
                    "type": 3,  # String type
                    "required": True
                },
                {
                    "name": "serverid",
                    "description": "Unique server ID used in directory names",
                    "type": 3,  # String type
                    "required": True
                }
            ]
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

def command_to_dict(command):
    """Convert a command definition to a dict format matching Discord's API response"""
    if "subcommands" in command:
        # This is a command group
        options = []
        for subcmd in command["subcommands"]:
            subcmd_option = {
                "type": 1,  # Subcommand type
                "name": subcmd["name"],
                "description": subcmd["description"]
            }
            
            # Add options if any
            if "options" in subcmd:
                subcmd_option["options"] = []
                for opt in subcmd["options"]:
                    subcmd_option["options"].append({
                        "type": opt["type"],
                        "name": opt["name"],
                        "description": opt["description"],
                        "required": opt.get("required", False)
                    })
            
            options.append(subcmd_option)
        
        return {
            "name": command["name"],
            "description": command["description"],
            "options": options
        }
    else:
        # This is a simple command
        return {
            "name": command["name"],
            "description": command["description"],
        }

def commands_are_equivalent(cmd1, cmd2):
    """
    Compare two commands to see if they're functionally equivalent.
    Returns True if the commands are the same (no update needed),
    False if they differ (update needed).
    """
    # Basic command properties check
    if cmd1["name"] != cmd2["name"] or cmd1["description"] != cmd2["description"]:
        return False
    
    # Check options/subcommands
    if "options" in cmd1 and "options" in cmd2:
        # If number of options differs, commands are different
        if len(cmd1["options"]) != len(cmd2["options"]):
            return False
        
        # Sort options by name to ensure consistent comparison
        cmd1_options = sorted(cmd1["options"], key=lambda x: x["name"])
        cmd2_options = sorted(cmd2["options"], key=lambda x: x["name"])
        
        # Compare each option
        for opt1, opt2 in zip(cmd1_options, cmd2_options):
            # Check if option types differ
            if opt1.get("type") != opt2.get("type"):
                return False
            
            # Check basic option properties
            if (opt1["name"] != opt2["name"] or 
                opt1["description"] != opt2["description"] or
                opt1.get("required", False) != opt2.get("required", False)):
                return False
            
            # For subcommands, recursively check their options
            if opt1.get("type") == 1 and "options" in opt1 and "options" in opt2:
                # Convert to dict format for comparison
                subcmd1 = {"name": opt1["name"], "description": opt1["description"], "options": opt1["options"]}
                subcmd2 = {"name": opt2["name"], "description": opt2["description"], "options": opt2["options"]}
                if not commands_are_equivalent(subcmd1, subcmd2):
                    return False
    
    # If we got here, commands are equivalent
    return True

async def smart_register_commands(bot, guild=None):
    """
    Smart command registration system that only updates commands that have changed
    """
    try:
        # Get bot_id, guild_id and guild_name for logging
        bot_id = bot.user.id
        guild_id = guild.id if guild else None
        guild_name = guild.name if guild else "global"
        log_prefix = f"[Guild: {guild_name}] " if guild else "[Global] "
        
        logger.info(f"{log_prefix}Starting smart command registration...")
        
        # Get existing commands
        existing_commands = []
        if guild:
            existing_commands = await bot.http.get_guild_commands(bot_id, guild_id)
        else:
            existing_commands = await bot.http.get_global_commands(bot_id)
        
        logger.info(f"{log_prefix}Found {len(existing_commands)} existing commands")
        
        # Create a dict of desired commands (what we want to have)
        desired_commands = {}
        
        # Add all command groups
        for group in ALL_COMMAND_GROUPS:
            desired_commands[group["name"]] = command_to_dict(group)
        
        # Add all simple commands
        for cmd in ALL_SIMPLE_COMMANDS:
            desired_commands[cmd["name"]] = command_to_dict(cmd)
        
        # Create a dict of existing commands for lookup
        existing_command_dict = {cmd["name"]: cmd for cmd in existing_commands}
        
        # Track changes
        commands_to_update = []
        command_ids_to_delete = []
        
        # First, find commands to update or create
        for cmd_name, cmd_data in desired_commands.items():
            if cmd_name in existing_command_dict:
                # Command exists, check if it needs updating
                if not commands_are_equivalent(cmd_data, existing_command_dict[cmd_name]):
                    logger.info(f"{log_prefix}Command '{cmd_name}' has changed, will update")
                    commands_to_update.append(cmd_data)
                else:
                    logger.info(f"{log_prefix}Command '{cmd_name}' is unchanged, skipping")
            else:
                # New command, needs to be created
                logger.info(f"{log_prefix}Command '{cmd_name}' is new, will create")
                commands_to_update.append(cmd_data)
        
        # Next, find commands to delete (existing but not in our desired list)
        for cmd_name, cmd_data in existing_command_dict.items():
            if cmd_name not in desired_commands:
                logger.info(f"{log_prefix}Command '{cmd_name}' is no longer needed, will delete")
                command_ids_to_delete.append(cmd_data["id"])
        
        # Delete commands that are no longer needed
        for cmd_id in command_ids_to_delete:
            try:
                if guild:
                    await bot.http.delete_guild_command(bot_id, guild_id, cmd_id)
                else:
                    await bot.http.delete_global_command(bot_id, cmd_id)
                logger.info(f"{log_prefix}Deleted command ID: {cmd_id}")
                # Rate limit prevention
                await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"{log_prefix}Error deleting command: {e}")
        
        # Now register/update commands in batches to avoid rate limits
        if commands_to_update:
            logger.info(f"{log_prefix}Updating {len(commands_to_update)} commands...")
            
            # Convert to JSON format
            commands_json = json.dumps(commands_to_update)
            
            try:
                # Update/create all commands in one batch
                if guild:
                    result = await bot.http.bulk_upsert_guild_commands(bot_id, guild_id, commands_to_update)
                else:
                    result = await bot.http.bulk_upsert_global_commands(bot_id, commands_to_update)
                
                logger.info(f"{log_prefix}Successfully updated {len(result)} commands")
            except Exception as e:
                logger.error(f"{log_prefix}Error updating commands: {e}")
        else:
            logger.info(f"{log_prefix}No commands need updating")
        
        logger.info(f"{log_prefix}Command registration complete")
        
    except Exception as e:
        logger.error(f"Error in smart_register_commands: {e}")
        import traceback
        traceback.print_exc()

async def main():
    logger.info("Smart Discord Bot Command Registration")
    logger.info("====================================")
    
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
            
            # First, register commands for each guild specifically
            for guild in bot.guilds:
                logger.info(f"Registering commands for guild: {guild.name} (ID: {guild.id})")
                await smart_register_commands(bot, guild)
                # Wait between guilds to avoid rate limits
                await asyncio.sleep(2)
            
            # Also register commands globally (if needed)
            logger.info("Finished registering guild-specific commands")
            
            logger.info("Command registration complete! Disconnecting...")
            await bot.close()
        
        # Start the bot
        logger.info("Starting the bot...")
        await bot.start(token)
        
    except Exception as e:
        logger.error(f"Error in main: {e}")
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