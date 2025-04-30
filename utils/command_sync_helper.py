"""
Command Synchronization Helper

This module provides various approaches to Discord command registration
with effective rate limit handling.
"""

import asyncio
import logging
import random
import json
import os
from datetime import datetime, timedelta

logger = logging.getLogger('deadside_bot.command_sync')

# Essential commands that should always be registered
ESSENTIAL_COMMANDS = [
    "ping",  # Basic ping command
    "commands",  # Help command
    "server",  # Core server functionality
    "killfeed",  # Killfeed notifications
    "stats",  # Player statistics
    "missions"  # Mission tracking
]

async def sync_essential_commands(bot):
    """
    Register only essential commands with basic rate limit handling.
    
    Args:
        bot: The Discord bot instance
        
    Returns:
        bool: True if at least some commands were registered, False otherwise
    """
    logger.info(f"Starting essential command registration")
    success_count = 0
    
    # Try to register each essential command
    for cmd_name in ESSENTIAL_COMMANDS:
        try:
            # Create a simple command definition
            simple_cmd = {
                "name": cmd_name,
                "description": f"{cmd_name.capitalize()} functionality",
                "type": 1  # CHAT_INPUT type
            }
            
            # Try to register the command
            await bot.http.request(
                'POST',
                f"/applications/{bot.application_id}/commands",
                json=simple_cmd
            )
            logger.info(f"✅ Registered essential command: {cmd_name}")
            success_count += 1
            
            # Wait between commands to avoid rate limits
            await asyncio.sleep(3)  # Conservative delay
        except Exception as e:
            logger.error(f"Failed to register essential command {cmd_name}: {e}")
    
    # Return success if we registered at least some commands
    if success_count > 0:
        logger.info(f"✅ Registered {success_count}/{len(ESSENTIAL_COMMANDS)} essential commands")
        return True
    else:
        logger.error("❌ Failed to register any essential commands")
        return False

async def sync_all_commands(bot):
    """
    Attempt to register all commands using batched approach.
    
    Args:
        bot: The Discord bot instance
        
    Returns:
        bool: True if at least some commands were registered, False otherwise
    """
    logger.info("Starting batch command registration")
    
    # Collect all commands
    commands_payload = []
    
    # Process each cog to collect commands
    for cog_name, cog in bot.cogs.items():
        if hasattr(cog, "get_commands") and callable(cog.get_commands):
            try:
                cog_commands = cog.get_commands()
                if cog_commands:
                    for cmd in cog_commands:
                        if hasattr(cmd, 'to_dict'):
                            cmd_payload = cmd.to_dict()
                            commands_payload.append(cmd_payload)
                            logger.info(f"Added command: {cmd.name}")
            except Exception as cog_err:
                logger.error(f"Error processing commands from cog {cog_name}: {cog_err}")
    
    # Add base commands (ping, commands)
    for cmd_name in ESSENTIAL_COMMANDS:
        if not any(cmd.get('name') == cmd_name for cmd in commands_payload):
            simple_cmd = {
                "name": cmd_name,
                "description": f"{cmd_name.capitalize()} functionality",
                "type": 1  # CHAT_INPUT type
            }
            commands_payload.append(simple_cmd)
            logger.info(f"Added essential command: {cmd_name}")
    
    # If we have no commands, exit
    if not commands_payload:
        logger.error("No commands found to register")
        return False
    
    # Use a very small batch size to avoid rate limits
    batch_size = 2
    logger.info(f"Using conservative batch size of {batch_size}")
    
    # Create batches
    batches = [commands_payload[i:i+batch_size] for i in range(0, len(commands_payload), batch_size)]
    
    # Register batches
    success_count = 0
    for i, batch in enumerate(batches):
        try:
            logger.info(f"Registering batch {i+1}/{len(batches)} with {len(batch)} commands")
            
            # Use PUT for first batch, POST for subsequent batches
            if i == 0:
                method = "PUT"
            else:
                method = "POST"
                
            # Make the request
            await bot.http.request(
                method,
                f"/applications/{bot.application_id}/commands",
                json=batch
            )
            
            success_count += len(batch)
            logger.info(f"✅ Batch {i+1} successful ({success_count}/{len(commands_payload)} commands registered)")
            
            # Wait between batches with a conservative delay
            if i < len(batches) - 1:
                delay = 5 + random.uniform(1, 3)  # 5-8 seconds
                logger.info(f"Waiting {delay:.1f}s before next batch")
                await asyncio.sleep(delay)
        except Exception as e:
            logger.error(f"❌ Error in batch {i+1}: {e}")
            
            # Try individual registration as fallback
            logger.warning(f"Trying individual registration for failed batch")
            for cmd in batch:
                try:
                    cmd_name = cmd.get('name', 'unknown')
                    await bot.http.request(
                        "POST",
                        f"/applications/{bot.application_id}/commands",
                        json=cmd
                    )
                    success_count += 1
                    logger.info(f"✅ Individually registered command: {cmd_name}")
                    
                    # Wait between individual commands
                    await asyncio.sleep(3)
                except Exception as cmd_err:
                    logger.error(f"❌ Failed to register command {cmd_name}: {cmd_err}")
            
            # Wait longer after a failed batch
            await asyncio.sleep(10)
    
    # Report results
    if success_count > 0:
        if success_count == len(commands_payload):
            logger.info(f"✅ Successfully registered all {success_count} commands")
        else:
            logger.warning(f"⚠️ Registered {success_count}/{len(commands_payload)} commands")
        return True
    else:
        logger.error("❌ Failed to register any commands")
        return False

async def sync_commands(bot):
    """
    Main entry point for command synchronization.
    Tries multiple approaches in order of reliability.
    
    Args:
        bot: The Discord bot instance
        
    Returns:
        bool: True if any commands were successfully registered
    """
    logger.info("Starting command synchronization process")
    
    # Try the minimal essential commands approach first
    try:
        logger.info("Attempting minimal essential command registration")
        result = await sync_essential_commands(bot)
        if result:
            logger.info("Essential command registration successful")
            return True
        else:
            logger.warning("Essential command registration failed, trying full registration")
    except Exception as e:
        logger.error(f"Error in essential command registration: {e}")
    
    # Try the full batch registration approach
    try:
        logger.info("Attempting full batch command registration")
        result = await sync_all_commands(bot)
        if result:
            logger.info("Full batch command registration successful")
            return True
        else:
            logger.warning("Full batch command registration failed")
    except Exception as e:
        logger.error(f"Error in full batch command registration: {e}")
    
    # Last resort - try the built-in sync mechanism
    try:
        logger.info("Attempting built-in command synchronization")
        await bot.sync_commands()
        logger.info("Built-in command synchronization successful")
        return True
    except Exception as e:
        logger.error(f"Error in built-in command synchronization: {e}")
    
    logger.error("All command synchronization approaches failed")
    return False