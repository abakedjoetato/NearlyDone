"""
Simplified command registration for Discord bots

This module provides a minimal approach to command registration
that focuses only on essential commands and uses conservative rate limit handling.
"""

import asyncio
import logging
import json
import os
import random
from datetime import datetime, timedelta

logger = logging.getLogger('deadside_bot.minimal_command_sync')

# Essential commands that should always be registered
ESSENTIAL_COMMANDS = [
    "ping",  # Basic ping command
    "commands",  # Help command
    "server",  # Core server functionality
    "killfeed",  # Killfeed notifications
    "stats",  # Player statistics
    "missions"  # Mission tracking
]

async def register_minimal_commands(bot):
    """
    Register only essential commands with heavy rate limit handling.
    
    Args:
        bot: The Discord bot instance
        
    Returns:
        bool: True if at least some essential commands were registered
    """
    logger.info(f"Starting minimal command registration with {len(ESSENTIAL_COMMANDS)} essential commands")
    
    # Track success rate
    success_count = 0
    
    # Simple helper to wait between operations with jitter
    async def wait_with_jitter(base_seconds):
        jitter = random.uniform(0.5, 1.5)
        wait_time = base_seconds * jitter
        logger.info(f"Waiting {wait_time:.2f}s before next operation...")
        await asyncio.sleep(wait_time)
    
    # Helper for direct API calls with retry
    async def api_call(method, endpoint, payload=None, max_retries=3):
        for retry in range(max_retries):
            try:
                if retry > 0:
                    logger.info(f"Retry attempt {retry+1}/{max_retries}...")
                    # Add exponential backoff
                    await wait_with_jitter(5 * (2 ** retry))
                
                response = await bot.http.request(method, endpoint, json=payload)
                return response, True
            except Exception as e:
                if "rate limited" in str(e).lower():
                    # Try to parse retry_after if available
                    retry_after = 5  # default
                    try:
                        error_data = str(e)
                        if "retry_after" in error_data:
                            # Try to extract the retry_after value
                            start = error_data.find("retry_after") + len("retry_after") + 1
                            end = error_data.find(",", start)
                            if end == -1:
                                end = error_data.find("}", start)
                            retry_after = float(error_data[start:end].strip('": '))
                            
                            # Add buffer time
                            retry_after += 1
                    except:
                        # Use default + exponential backoff
                        retry_after = 5 * (2 ** retry)
                    
                    logger.warning(f"Rate limited. Waiting {retry_after}s before retry...")
                    await asyncio.sleep(retry_after)
                    continue
                elif retry < max_retries - 1:
                    logger.error(f"Error in API call: {e}. Retrying...")
                    await wait_with_jitter(5)
                    continue
                else:
                    logger.error(f"Failed after {max_retries} retries: {e}")
                    return None, False
        
        return None, False
    
    # Collect command payloads for essential commands
    command_payloads = []
    
    # Find existing application commands
    for cmd in bot.application_commands:
        if cmd.name in ESSENTIAL_COMMANDS:
            try:
                if hasattr(cmd, 'to_dict'):
                    cmd_dict = cmd.to_dict()
                    command_payloads.append(cmd_dict)
                    logger.info(f"Found command: {cmd.name}")
            except Exception as e:
                logger.error(f"Error serializing {cmd.name}: {e}")
    
    # Add stub commands for any essential commands not found
    for cmd_name in ESSENTIAL_COMMANDS:
        if not any(cmd.get('name') == cmd_name for cmd in command_payloads):
            logger.info(f"Adding stub for {cmd_name}")
            command_payloads.append({
                "name": cmd_name,
                "description": f"{cmd_name.capitalize()} functionality",
                "type": 1  # CHAT_INPUT type
            })
    
    # If we have no commands, exit
    if not command_payloads:
        logger.error("No commands found to register")
        return False
    
    # Try batched approach first with extremely conservative batch size
    batch_size = 1  # Register just one command at a time to avoid rate limits
    logger.info(f"Using batch size of {batch_size}")
    
    # Divide into small batches
    batches = [command_payloads[i:i+batch_size] for i in range(0, len(command_payloads), batch_size)]
    
    # Register each batch
    for i, batch in enumerate(batches):
        logger.info(f"Processing batch {i+1}/{len(batches)}")
        
        # Start with PUT method - this is usually more reliable
        endpoint = f"/applications/{bot.application_id}/commands"
        
        try:
            response, success = await api_call("PUT", endpoint, batch)
            
            if success:
                logger.info(f"Successfully registered batch {i+1}")
                success_count += len(batch)
            else:
                # If PUT failed, try POST for each command individually
                logger.warning(f"Batch registration failed, trying individual commands")
                for cmd in batch:
                    cmd_name = cmd.get('name', 'unknown')
                    logger.info(f"Attempting to register {cmd_name} individually")
                    
                    response, success = await api_call("POST", endpoint, cmd)
                    
                    if success:
                        logger.info(f"Successfully registered {cmd_name}")
                        success_count += 1
                    else:
                        logger.error(f"Failed to register {cmd_name}")
            
            # Always wait between batches with a very conservative delay
            if i < len(batches) - 1:
                await wait_with_jitter(8)
        
        except Exception as e:
            logger.error(f"Error processing batch {i+1}: {e}")
            # Wait longer after an error
            await wait_with_jitter(10)
    
    # Report results
    if success_count == len(command_payloads):
        logger.info(f"✅ Successfully registered all {success_count} essential commands")
        return True
    elif success_count > 0:
        logger.warning(f"⚠️ Registered {success_count}/{len(command_payloads)} essential commands")
        return True
    else:
        logger.error("❌ Failed to register any commands")
        return False

# Function to be called from main.py
async def sync_minimal_commands(bot):
    """
    Public function to sync essential commands
    
    Args:
        bot: The Discord bot instance
        
    Returns:
        bool: Success status
    """
    try:
        result = await register_minimal_commands(bot)
        return result
    except Exception as e:
        logger.error(f"Error in minimal command sync: {e}")
        return False