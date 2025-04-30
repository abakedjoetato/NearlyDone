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
import json
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

# Function to print command details
def print_command(cmd, indent=""):
    cmd_type = cmd.get("type", 1)
    cmd_type_name = "SLASH" if cmd_type == 1 else "USER" if cmd_type == 2 else "MESSAGE" if cmd_type == 3 else "UNKNOWN"
    
    logger.info(f"{indent}Command: {cmd.get('name')} ({cmd_type_name})")
    logger.info(f"{indent}  Description: {cmd.get('description', 'No description')}")
    
    # Print options/subcommands if any
    options = cmd.get("options", [])
    if options:
        for option in options:
            if option.get("type") == 1:  # Subcommand
                logger.info(f"{indent}  SubCommand: {option.get('name')}")
                logger.info(f"{indent}    Description: {option.get('description', 'No description')}")
                
                sub_options = option.get("options", [])
                if sub_options:
                    for sub_opt in sub_options:
                        logger.info(f"{indent}    Option: {sub_opt.get('name')} ({sub_opt.get('type')})")
                        logger.info(f"{indent}      Description: {sub_opt.get('description', 'No description')}")
            elif option.get("type") == 2:  # Subcommand Group
                logger.info(f"{indent}  SubCommand Group: {option.get('name')}")
                logger.info(f"{indent}    Description: {option.get('description', 'No description')}")
                
                for sub_cmd in option.get("options", []):
                    logger.info(f"{indent}    SubCommand: {sub_cmd.get('name')}")
                    logger.info(f"{indent}      Description: {sub_cmd.get('description', 'No description')}")
                    
                    for sub_opt in sub_cmd.get("options", []):
                        logger.info(f"{indent}      Option: {sub_opt.get('name')} ({sub_opt.get('type')})")
                        logger.info(f"{indent}        Description: {sub_opt.get('description', 'No description')}")
            else:  # Regular option
                logger.info(f"{indent}  Option: {option.get('name')} ({option.get('type')})")
                logger.info(f"{indent}    Description: {option.get('description', 'No description')}")
    else:
        logger.info(f"{indent}  No options/subcommands")

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
        
        try:
            # For py-cord, we can directly access the commands through the bot
            app_commands = []
            if hasattr(bot, 'application_commands'):
                app_commands = bot.application_commands
                logger.info(f"Found {len(app_commands)} application commands in the bot")
                
                for cmd in app_commands:
                    logger.info(f"Command: {cmd.name}")
                    logger.info(f"  Description: {cmd.description}")
                    
                    # If it has subcommands, list them
                    if hasattr(cmd, 'options') and cmd.options:
                        for option in cmd.options:
                            if hasattr(option, 'name'):
                                logger.info(f"  Subcommand: {option.name}")
                                if hasattr(option, 'description'):
                                    logger.info(f"    Description: {option.description}")
            else:
                logger.warning("No application_commands found in bot object")
            
            # Check via sync_commands
            logger.info("Attempting to sync commands to verify registration...")
            try:
                # Small sync to test if commands are working
                await bot.sync_commands(guild_ids=[guild.id for guild in bot.guilds])
                logger.info("✅ Command sync successful, commands should be visible in Discord")
            except Exception as sync_err:
                logger.error(f"Command sync failed: {sync_err}")
                
            # List connected guilds
            logger.info(f"Connected to {len(bot.guilds)} guilds:")
            for guild in bot.guilds:
                logger.info(f"  Guild: {guild.name} (ID: {guild.id})")
                # Check app commands count per guild
                guild_commands = [cmd for cmd in app_commands if hasattr(cmd, 'guild_ids') and guild.id in cmd.guild_ids]
                logger.info(f"  Guild-specific commands: {len(guild_commands)}")
                
                # List all command names for this guild
                for cmd in guild_commands:
                    logger.info(f"    Command: {cmd.name}")
                    
                    
                    logger.info(f"\nGuild: {guild_name} ({guild_id})")
                    logger.info(f"Found {len(guild_commands)} guild-specific commands:")
                    
                    if guild_commands:
                        for cmd in guild_commands:
                            print_command(cmd, indent="  ")
                    else:
                        logger.warning(f"  No commands found for guild {guild_name}")
                        
                except Exception as e:
                    logger.error(f"Error checking commands for guild {guild_name}: {e}")
        except Exception as e:
            logger.error(f"Error checking registered commands: {e}")
        
        # Exit after command check
        logger.info("Command verification complete! Logging out...")
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