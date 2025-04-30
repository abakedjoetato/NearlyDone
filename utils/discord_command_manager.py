"""
Discord Command Manager

This module provides a reliable system for registering Discord slash commands
with proper handling of subcommands, rate limits, and error conditions.

It replaces the previous command sync helpers with a cleaner implementation
that properly handles the Discord API requirements for command registration.
"""

import asyncio
import logging
import time
import json
import math
from typing import Dict, List, Any, Optional, Tuple, Union

logger = logging.getLogger('discord.command_manager')

# Constants for Discord API
DISCORD_GLOBAL_ENDPOINT = '/applications/{app_id}/commands'
DISCORD_GUILD_ENDPOINT = '/applications/{app_id}/guilds/{guild_id}/commands'
RATE_LIMIT_WINDOW = 60  # seconds
RATE_LIMIT_REQUESTS = 100  # max requests per minute for slash commands
RATE_LIMIT_REMAINING_THRESHOLD = 10  # Slow down when we have fewer than this remaining

# Track rate limit state
rate_limit = {
    'reset_at': 0,
    'remaining': RATE_LIMIT_REQUESTS,
    'total': RATE_LIMIT_REQUESTS
}

async def register_commands(bot) -> bool:
    """
    Register all slash commands to Discord with proper rate limit handling
    
    Args:
        bot: The Discord bot instance
        
    Returns:
        bool: True if commands were registered successfully, False otherwise
    """
    logger.info("Starting command registration with enhanced handler")
    
    try:
        # Get commands payload from the bot
        commands_payload = bot._connection._command_store.values()
        if not commands_payload:
            logger.warning("No commands to register")
            return True
        
        # Prepare the commands for sending
        app_id = bot.application_id or bot.user.id
        
        # First, try the batch approach (recommended)
        try:
            endpoint = DISCORD_GLOBAL_ENDPOINT.format(app_id=app_id)
            # Convert commands to proper format for Discord
            formatted_commands = []
            
            for cmd in commands_payload:
                # Skip if this isn't a global command
                if not hasattr(cmd, 'guild_ids') or cmd.guild_ids:
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
        
        # Wait for rate limits if needed
        await respect_rate_limit()
        
        http = bot.http
        
        async def register_with_rate_limit(retry_count=0, max_retries=3):
            nonlocal endpoint, commands
            
            try:
                # Make the request
                response = await http.request('PUT', endpoint, json=commands)
                
                # Update rate limit info
                update_rate_limit_from_headers(response.headers)
                
                # Check if successful
                if response.status >= 200 and response.status < 300:
                    logger.info(f"Successfully registered {len(commands)} commands")
                    return True
                else:
                    # If we got a rate limit response, wait and retry
                    if response.status == 429:
                        retry_after = response.headers.get('Retry-After', 5)
                        retry_after = float(retry_after)
                        logger.warning(f"Rate limited, waiting {retry_after}s before retry")
                        
                        # Wait for the rate limit to reset
                        await asyncio.sleep(retry_after)
                        
                        # Try again if we have retries left
                        if retry_count < max_retries:
                            return await register_with_rate_limit(retry_count + 1, max_retries)
                    
                    # Other errors
                    error_json = await response.json()
                    logger.error(f"Error registering commands: {response.status} - {error_json}")
                    return False
                    
            except Exception as e:
                logger.error(f"Error during batch command registration: {e}")
                
                # Try again if we have retries left
                if retry_count < max_retries:
                    wait_time = 2 ** retry_count  # Exponential backoff
                    logger.info(f"Retrying after {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    return await register_with_rate_limit(retry_count + 1, max_retries)
                    
                return False
        
        return await register_with_rate_limit()
        
    except Exception as e:
        logger.error(f"Error in batch command registration: {e}")
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
    
    for i, cmd in enumerate(commands):
        # Check rate limits before each request
        await respect_rate_limit()
        
        try:
            # Log command registration attempt
            cmd_name = cmd.get('name', 'unknown')
            logger.info(f"Registering command {i+1}/{total}: {cmd_name}")
            
            # Send the command to Discord
            endpoint = f"{base_endpoint}"
            response = await http.request('POST', endpoint, json=cmd)
            
            # Update rate limit tracking
            update_rate_limit_from_headers(response.headers)
            
            # Check if successful
            if response.status >= 200 and response.status < 300:
                successful += 1
                logger.info(f"✓ Command {cmd_name} registered successfully")
            else:
                # Handle errors
                try:
                    error_data = await response.json()
                    logger.error(f"✗ Failed to register command {cmd_name}: {response.status} - {error_data}")
                except:
                    logger.error(f"✗ Failed to register command {cmd_name}: {response.status}")
            
            # Add a small delay to avoid overwhelming the API
            await asyncio.sleep(0.5)
            
        except Exception as e:
            logger.error(f"Error registering command: {e}")
    
    # Consider successful if at least half of commands registered
    success_rate = successful / total if total > 0 else 0
    logger.info(f"Registered {successful}/{total} commands ({success_rate:.1%})")
    return success_rate >= 0.5

async def respect_rate_limit():
    """
    Wait if we're approaching rate limits
    """
    global rate_limit
    
    current_time = time.time()
    
    # If we're past the reset time, reset our counters
    if current_time > rate_limit['reset_at']:
        rate_limit['remaining'] = rate_limit['total']
        rate_limit['reset_at'] = current_time + RATE_LIMIT_WINDOW
    
    # If we're low on remaining requests, wait until reset
    if rate_limit['remaining'] < RATE_LIMIT_REMAINING_THRESHOLD:
        wait_time = max(0, rate_limit['reset_at'] - current_time)
        if wait_time > 0:
            logger.warning(f"Rate limit approaching, waiting {wait_time:.1f}s")
            await asyncio.sleep(wait_time)
            # Reset after waiting
            rate_limit['remaining'] = rate_limit['total']
            rate_limit['reset_at'] = time.time() + RATE_LIMIT_WINDOW
    
    # Decrement remaining
    rate_limit['remaining'] -= 1

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