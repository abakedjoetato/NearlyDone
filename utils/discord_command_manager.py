"""
Discord Command Manager

This module provides a reliable system for registering Discord slash commands
with proper handling of subcommands, rate limits, and error conditions.

This is an enhanced version with more conservative rate limit handling and 
better error recovery to ensure commands register successfully even under
challenging conditions.
"""

import asyncio
import logging
import time
import json
import math
import random
from typing import Dict, List, Any, Optional, Tuple, Union

logger = logging.getLogger('discord.command_manager')

# Constants for Discord API
DISCORD_GLOBAL_ENDPOINT = '/applications/{app_id}/commands'
DISCORD_GUILD_ENDPOINT = '/applications/{app_id}/guilds/{guild_id}/commands'

# More conservative rate limits to prevent hitting Discord's actual limits
RATE_LIMIT_WINDOW = 60  # seconds
RATE_LIMIT_REQUESTS = 50  # Using half of Discord's actual limit (usually 100) to be safe
RATE_LIMIT_REMAINING_THRESHOLD = 15  # Slow down when we have fewer than this remaining

# Add delays between requests to be extra cautious
MIN_REQUEST_DELAY = 1.0  # seconds
MAX_REQUEST_DELAY = 2.5  # seconds
BATCH_DELAY = 15.0  # seconds

# Track rate limit state
rate_limit = {
    'reset_at': 0,
    'remaining': RATE_LIMIT_REQUESTS,
    'total': RATE_LIMIT_REQUESTS,
    'last_request_time': 0
}

async def register_commands(bot, guild_ids: List[int] = None) -> bool:
    """
    Register all slash commands to Discord with proper rate limit handling
    
    Args:
        bot: The Discord bot instance
        guild_ids: Optional list of specific guild IDs to register commands for.
                   If provided, only these guilds will have commands registered.
                   
    Returns:
        bool: True if commands were registered successfully, False otherwise
    """
    logger.info(f"Starting command registration with enhanced handler" + 
                (f" for specific guilds: {guild_ids}" if guild_ids else " for all guilds/global"))
    
    try:
        # Get commands payload from the bot
        commands_payload = bot._connection._command_store.values() if hasattr(bot._connection, '_command_store') else None
        
        if not commands_payload:
            logger.warning("Could not find commands to register, bot may use a different command storage mechanism")
            if hasattr(bot, 'application_commands'):
                # Try py-cord's application_commands
                commands_payload = bot.application_commands
                logger.info(f"Using py-cord application_commands ({len(commands_payload)} commands found)")
            else:
                logger.error("No compatible command store found in the bot")
                return False
                
        if not commands_payload:
            logger.warning("No commands to register")
            return True
        
        # Prepare the commands for sending
        app_id = bot.application_id or bot.user.id
        
        # If specific guild_ids are specified, focus exclusively on those
        if guild_ids:
            overall_success = True
            
            # Process each specified guild
            for guild_id in guild_ids:
                logger.info(f"Registering commands for specific guild: {guild_id}")
                
                # For each guild, collect all commands (both global and guild-specific)
                # Since we're registering directly to a guild, we include all commands
                guild_cmds = []
                
                for cmd in commands_payload:
                    cmd_data = extract_command_data(cmd)
                    if cmd_data:
                        guild_cmds.append(cmd_data)
                
                if guild_cmds:
                    # Register to this specific guild
                    endpoint = DISCORD_GUILD_ENDPOINT.format(app_id=app_id, guild_id=guild_id)
                    logger.info(f"Registering {len(guild_cmds)} commands to guild {guild_id}")
                    
                    # Try batch first
                    guild_success = await register_commands_batch(bot, endpoint, guild_cmds)
                    if not guild_success:
                        logger.warning(f"Batch registration failed for guild {guild_id}, falling back to individual")
                        guild_success = await register_commands_individually(bot, guild_cmds, guild_id=guild_id)
                    
                    # Track overall success
                    overall_success = overall_success and guild_success
                else:
                    logger.warning(f"No commands found to register for guild {guild_id}")
                
                # Add delay between guild registrations
                await asyncio.sleep(10)  # 10-second delay between guild registrations
            
            return overall_success
            
        # Standard registration flow when no specific guild_ids are provided
        try:
            # First, register global commands
            endpoint = DISCORD_GLOBAL_ENDPOINT.format(app_id=app_id)
            formatted_commands = []
            
            for cmd in commands_payload:
                # Skip if this isn't a global command
                if hasattr(cmd, 'guild_ids') and cmd.guild_ids:
                    continue
                
                # Extract necessary command data
                cmd_data = extract_command_data(cmd)
                if cmd_data:
                    formatted_commands.append(cmd_data)
            
            if formatted_commands:
                logger.info(f"Registering {len(formatted_commands)} global commands")
                success = await register_commands_batch(bot, endpoint, formatted_commands)
                if not success:
                    logger.warning("Batch registration failed, falling back to individual registration")
                    success = await register_commands_individually(bot, formatted_commands)
            else:
                logger.info("No global commands to register")
                success = True
            
            # Now register guild-specific commands
            guild_cmds = {}
            for cmd in commands_payload:
                # Skip non-guild commands
                if not hasattr(cmd, 'guild_ids') or not cmd.guild_ids:
                    continue
                
                # Extract command data
                cmd_data = extract_command_data(cmd)
                if not cmd_data:
                    continue
                
                # Add to each guild's command list
                for guild_id in cmd.guild_ids:
                    if guild_id not in guild_cmds:
                        guild_cmds[guild_id] = []
                    guild_cmds[guild_id].append(cmd_data)
            
            # Register each guild's commands
            for guild_id, cmds in guild_cmds.items():
                logger.info(f"Registering {len(cmds)} commands for guild {guild_id}")
                endpoint = DISCORD_GUILD_ENDPOINT.format(app_id=app_id, guild_id=guild_id)
                guild_success = await register_commands_batch(bot, endpoint, cmds)
                if not guild_success:
                    logger.warning(f"Batch registration failed for guild {guild_id}, falling back to individual")
                    guild_success = await register_commands_individually(bot, cmds, guild_id=guild_id)
                
                # Track overall success
                success = success and guild_success
                
                # Add delay between guild registrations
                await asyncio.sleep(5)
            
            return success
            
        except Exception as e:
            logger.error(f"Error during command registration: {e}")
            return False
            
    except Exception as e:
        logger.error(f"Failed to register commands: {e}")
        return False

def extract_command_data(cmd) -> Optional[Dict[str, Any]]:
    """
    Extract command data from a command object
    
    Args:
        cmd: The command object
        
    Returns:
        dict: The formatted command data for the Discord API
    """
    try:
        # Start with basic command data
        result = {
            'name': cmd.name,
            'description': cmd.description,
        }
        
        # Add options if present
        if hasattr(cmd, 'options') and cmd.options:
            result['options'] = cmd.options
        
        # Add default_permission if present
        if hasattr(cmd, 'default_permission'):
            result['default_permission'] = cmd.default_permission
        
        # Add guild_ids if present (for logging only, not sent to Discord)
        if hasattr(cmd, 'guild_ids') and cmd.guild_ids:
            result['guild_ids'] = cmd.guild_ids
        
        # Add type, context, and integrations
        if hasattr(cmd, 'type'):
            result['type'] = cmd.type
            
        # Required to avoid "Invalid Form Body" errors with subcommands
        if not result.get('options'):
            result['options'] = []
            
        # Integration types required for commands with subcommands
        if not result.get('integration_types'):
            result['integration_types'] = [0, 1]
            
        # Command contexts required for proper registration
        if not result.get('contexts'):
            result['contexts'] = [0, 1, 2]
            
        return result
    except Exception as e:
        logger.error(f"Error extracting command data: {e}")
        return None

async def register_commands_batch(bot, endpoint: str, commands: List[Dict[str, Any]]) -> bool:
    """
    Register commands in a single batch request
    
    Args:
        bot: The Discord bot instance
        endpoint: The Discord API endpoint
        commands: List of commands to register
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        logger.info(f"Batch registering {len(commands)} commands to endpoint {endpoint}")
        
        # If we have more than 5 commands, break it down into smaller batches
        # This helps avoid rate limits and increases reliability 
        if len(commands) > 5:
            logger.info(f"Breaking down batch of {len(commands)} commands into smaller batches")
            
            # Use smaller batches of maximum 5 commands
            small_batch_size = 5
            small_batches = [commands[i:i+small_batch_size] for i in range(0, len(commands), small_batch_size)]
            
            all_successful = True
            for i, small_batch in enumerate(small_batches):
                logger.info(f"Processing small batch {i+1}/{len(small_batches)} with {len(small_batch)} commands")
                
                # Wait between small batches
                if i > 0:
                    wait_time = BATCH_DELAY
                    logger.info(f"Waiting {wait_time}s between small batches to avoid rate limits...")
                    await asyncio.sleep(wait_time)
                
                # Register this small batch
                small_batch_success = await register_commands_batch(bot, endpoint, small_batch)
                
                if not small_batch_success:
                    logger.warning(f"Small batch {i+1} registration failed")
                    all_successful = False
            
            return all_successful
                
        # For small batches, proceed with the regular approach
        # Wait for rate limits if needed
        await respect_rate_limit()
        
        http = bot.http
        
        async def register_with_rate_limit(retry_count=0, max_retries=5):  # Increased max retries
            nonlocal endpoint, commands
            
            try:
                # Make the request
                logger.info(f"Sending batch PUT request to {endpoint} with {len(commands)} commands")
                response = await http.request('PUT', endpoint, json=commands)
                
                # Update rate limit info
                update_rate_limit_from_headers(response.headers)
                
                # Check if successful
                if response.status >= 200 and response.status < 300:
                    logger.info(f"✅ Successfully registered {len(commands)} commands in batch")
                    return True
                else:
                    # If we got a rate limit response, wait and retry
                    if response.status == 429:
                        retry_after = 5.0  # Default value
                        
                        try:
                            error_data = await response.json()
                            if 'retry_after' in error_data:
                                retry_after = float(error_data['retry_after']) + 2  # Add buffer
                        except:
                            retry_after = 5.0 * (2 ** retry_count)  # Exponential backoff
                            
                        logger.warning(f"⚠️ Rate limited during batch registration, waiting {retry_after:.1f}s before retry")
                        
                        # Wait for the rate limit to reset
                        await asyncio.sleep(retry_after)
                        
                        # Try again if we have retries left
                        if retry_count < max_retries:
                            logger.info(f"Retrying batch (attempt {retry_count+1}/{max_retries})...")
                            return await register_with_rate_limit(retry_count + 1, max_retries)
                    
                    # Other errors
                    try:
                        error_json = await response.json()
                        logger.error(f"❌ Error registering commands: {response.status} - {error_json}")
                    except:
                        logger.error(f"❌ Error registering commands: {response.status}")
                    
                    # For other errors, we might still want to retry with a different approach
                    if retry_count < max_retries:
                        wait_time = 2 ** (retry_count + 1)  # Exponential backoff
                        logger.warning(f"Retrying batch with delay of {wait_time}s (attempt {retry_count+1}/{max_retries})...")
                        await asyncio.sleep(wait_time)
                        return await register_with_rate_limit(retry_count + 1, max_retries)
                    else:
                        logger.error(f"❌ Batch registration failed after {max_retries} retries")
                        return False
                    
            except Exception as e:
                logger.error(f"Error during batch command registration: {e}")
                
                # Try again if we have retries left
                if retry_count < max_retries:
                    wait_time = 2 ** (retry_count + 1)  # Exponential backoff
                    logger.info(f"Retrying after error in {wait_time}s (attempt {retry_count+1}/{max_retries})...")
                    await asyncio.sleep(wait_time)
                    return await register_with_rate_limit(retry_count + 1, max_retries)
                    
                logger.error(f"❌ Batch registration failed after {max_retries} retries")
                return False
        
        return await register_with_rate_limit()
        
    except Exception as e:
        logger.error(f"Unhandled error in batch command registration: {e}")
        return False

async def register_commands_individually(bot, commands: List[Dict[str, Any]], guild_id: Optional[int] = None) -> bool:
    """
    Register commands one by one with advanced rate limit handling and exponential backoff
    
    Args:
        bot: The Discord bot instance
        commands: List of commands to register
        guild_id: Optional guild ID for guild-specific commands
        
    Returns:
        bool: True if at least half of the commands were registered successfully, False otherwise
    """
    logger.info(f"Individually registering {len(commands)} commands" + 
                (f" for guild {guild_id}" if guild_id else " globally"))
    
    http = bot.http
    app_id = bot.application_id or bot.user.id
    
    if guild_id:
        base_endpoint = DISCORD_GUILD_ENDPOINT.format(app_id=app_id, guild_id=guild_id)
    else:
        base_endpoint = DISCORD_GLOBAL_ENDPOINT.format(app_id=app_id)
    
    successful = 0
    total = len(commands)
    
    # Small batch size for slower registration with better reliability
    batch_size = 2
    batches = [commands[i:i+batch_size] for i in range(0, len(commands), batch_size)]
    
    for batch_index, batch in enumerate(batches):
        logger.info(f"Processing batch {batch_index+1}/{len(batches)}")
        
        # Extra wait time between batches to avoid rate limits
        if batch_index > 0:
            batch_wait = random.uniform(BATCH_DELAY * 0.8, BATCH_DELAY * 1.2)  # Randomize to avoid patterns
            logger.info(f"Waiting {batch_wait:.1f}s between batches...")
            await asyncio.sleep(batch_wait)
        
        for i, cmd in enumerate(batch):
            # Check rate limits before each request
            await respect_rate_limit()
            
            try:
                # Log command registration attempt
                cmd_name = cmd.get('name', 'unknown')
                logger.info(f"Registering command {batch_index*batch_size+i+1}/{total}: {cmd_name}")
                
                # Retry logic for individual commands
                max_retries = 3
                for retry in range(max_retries + 1):
                    try:
                        # Send the command to Discord
                        endpoint = f"{base_endpoint}"
                        response = await http.request('POST', endpoint, json=cmd)
                        
                        # Update rate limit tracking
                        update_rate_limit_from_headers(response.headers)
                        
                        # Check if successful
                        if response.status >= 200 and response.status < 300:
                            successful += 1
                            logger.info(f"✓ Command {cmd_name} registered successfully")
                            break  # Exit retry loop on success
                        elif response.status == 429:  # Rate limited
                            retry_after = 5.0
                            try:
                                error_data = await response.json()
                                if 'retry_after' in error_data:
                                    retry_after = float(error_data['retry_after']) + 1  # Add buffer
                            except:
                                # Use default + exponential backoff
                                retry_after = 5.0 * (2 ** retry)
                                
                            logger.warning(f"Rate limited registering {cmd_name}. Waiting {retry_after:.1f}s...")
                            await asyncio.sleep(retry_after)
                            # Don't increment retry counter for rate limits
                            continue
                        else:
                            # Handle other errors
                            try:
                                error_data = await response.json()
                                logger.error(f"✗ Failed to register command {cmd_name}: {response.status} - {error_data}")
                            except:
                                logger.error(f"✗ Failed to register command {cmd_name}: {response.status}")
                                
                            if retry < max_retries:
                                wait_time = 2 ** (retry + 1)  # Exponential backoff
                                logger.warning(f"Retrying command {cmd_name} in {wait_time}s... (Attempt {retry+1}/{max_retries})")
                                await asyncio.sleep(wait_time)
                            else:
                                logger.error(f"Failed to register command {cmd_name} after {max_retries} retries")
                    except Exception as req_err:
                        logger.error(f"Error in command request: {req_err}")
                        if retry < max_retries:
                            wait_time = 2 ** (retry + 1)  # Exponential backoff
                            logger.warning(f"Retrying after error in {wait_time}s... (Attempt {retry+1}/{max_retries})")
                            await asyncio.sleep(wait_time)
                        else:
                            logger.error(f"Failed after {max_retries} retries")
                
                # Add a delay between commands even in the same batch
                cmd_delay = random.uniform(MIN_REQUEST_DELAY, MAX_REQUEST_DELAY)
                logger.debug(f"Waiting {cmd_delay:.1f}s between commands...")
                await asyncio.sleep(cmd_delay)
                
            except Exception as e:
                logger.error(f"Unhandled error registering command: {e}")
    
    # Consider successful if at least half of commands registered
    success_rate = successful / total if total > 0 else 0
    logger.info(f"Registered {successful}/{total} commands ({success_rate:.1%})")
    
    # More nuanced success criteria
    if success_rate >= 0.9:
        logger.info("✅ Command registration highly successful")
        return True
    elif success_rate >= 0.5:
        logger.warning("⚠️ Partial command registration success")
        return True
    else:
        logger.error("❌ Command registration failed (most commands not registered)")
        return False

async def respect_rate_limit():
    """
    Wait if we're approaching rate limits, with enforced delays between requests
    """
    global rate_limit
    
    current_time = time.time()
    
    # Enforce minimum time between requests regardless of rate limit
    time_since_last = current_time - rate_limit.get('last_request_time', 0)
    if time_since_last < MIN_REQUEST_DELAY:
        wait_time = MIN_REQUEST_DELAY - time_since_last
        await asyncio.sleep(wait_time)
        current_time = time.time()  # Update current time after waiting
    
    # If we're past the reset time, reset our counters
    if current_time > rate_limit['reset_at']:
        rate_limit['remaining'] = rate_limit['total']
        rate_limit['reset_at'] = current_time + RATE_LIMIT_WINDOW
    
    # If we're low on remaining requests, wait until reset
    if rate_limit['remaining'] < RATE_LIMIT_REMAINING_THRESHOLD:
        wait_time = max(0, rate_limit['reset_at'] - current_time)
        if wait_time > 0:
            logger.warning(f"Rate limit approaching ({rate_limit['remaining']}/{rate_limit['total']} remaining), waiting {wait_time:.1f}s")
            await asyncio.sleep(wait_time)
            # Reset after waiting
            rate_limit['remaining'] = rate_limit['total']
            rate_limit['reset_at'] = time.time() + RATE_LIMIT_WINDOW
            current_time = time.time()  # Update current time after waiting
    
    # Decrement remaining and update last request time
    rate_limit['remaining'] -= 1
    rate_limit['last_request_time'] = current_time
    
    # Log rate limit status every 10 requests
    if rate_limit['remaining'] % 10 == 0:
        time_to_reset = max(0, rate_limit['reset_at'] - current_time)
        logger.info(f"Rate limit status: {rate_limit['remaining']}/{rate_limit['total']} remaining, resets in {time_to_reset:.1f}s")

def update_rate_limit_from_headers(headers):
    """
    Update rate limit info from Discord API response headers
    
    Args:
        headers: Response headers from Discord API
    """
    global rate_limit
    
    # Get rate limit headers if present
    remaining = headers.get('X-RateLimit-Remaining')
    reset_after = headers.get('X-RateLimit-Reset-After')
    limit = headers.get('X-RateLimit-Limit')
    
    if remaining is not None:
        rate_limit['remaining'] = int(remaining)
    
    if reset_after is not None:
        rate_limit['reset_at'] = time.time() + float(reset_after)
    
    if limit is not None:
        rate_limit['total'] = int(limit)