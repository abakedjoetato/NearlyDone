"""
Discord Command Registration Manager

A complete rewrite of the command registration system with a clean,
reliable approach focused on properly handling rate limits and 
ensuring all commands and subcommands are registered correctly.
"""

import asyncio
import logging
import time
import random
from typing import List, Dict, Any, Optional, Union

logger = logging.getLogger('deadside_bot.commands')

class DiscordCommandManager:
    """
    Manages the registration of commands to Discord's API with proper
    rate limit handling and command structure verification.
    """
    
    def __init__(self, bot):
        """
        Initialize the command manager.
        
        Args:
            bot: The Discord bot instance
        """
        self.bot = bot
        self.application_id = bot.application_id
        self.http = bot.http
        self.rate_limit_remaining = 5  # Conservative default
        self.rate_limit_reset = 0
        self.essential_commands = [
            "ping",
            "commands",
            "server",
            "stats",
            "killfeed",
            "missions"
        ]
        
    async def register_all_commands(self) -> bool:
        """
        Main method to register all commands to Discord.
        
        Returns:
            bool: True if registration was successful, False otherwise
        """
        logger.info("Starting Discord command registration process")
        
        # Collect all commands in the proper format
        commands_payload = self._collect_commands()
        
        if not commands_payload:
            logger.error("No commands to register")
            return False
        
        logger.info(f"Collected {len(commands_payload)} commands to register")
        
        # First try batch registration with PUT method (overwrites all commands)
        try:
            logger.info("Attempting batch registration with PUT method")
            await self._api_request('PUT', f'/applications/{self.application_id}/commands', 
                                  json=commands_payload)
            logger.info("✅ Successfully registered all commands in batch")
            return True
        except Exception as e:
            logger.error(f"Batch registration failed: {e}")
            logger.warning("Falling back to individual command registration")
        
        # Fallback to individual command registration
        return await self._register_commands_individually(commands_payload)
    
    def _collect_commands(self) -> List[Dict[str, Any]]:
        """
        Collect all commands from cogs and format them properly for Discord's API.
        
        Returns:
            List[Dict[str, Any]]: List of command payloads
        """
        commands = []
        
        # Process each cog
        for cog_name, cog in self.bot.cogs.items():
            logger.info(f"Processing commands from cog: {cog_name}")
            
            if not hasattr(cog, "get_commands") or not callable(cog.get_commands):
                continue
                
            try:
                # Get all commands from this cog
                cog_commands = cog.get_commands()
                
                for cmd in cog_commands:
                    try:
                        # Check if this is a command group with subcommands
                        if hasattr(cmd, 'children') and cmd.children:
                            payload = self._create_command_group_payload(cmd)
                            commands.append(payload)
                            logger.info(f"Added command group: {cmd.name} with {len(cmd.children)} subcommands")
                        # Regular command
                        elif hasattr(cmd, 'to_dict'):
                            payload = cmd.to_dict()
                            commands.append(payload)
                            logger.info(f"Added command: {cmd.name}")
                    except Exception as cmd_err:
                        logger.error(f"Error processing command {getattr(cmd, 'name', 'unknown')}: {cmd_err}")
            except Exception as cog_err:
                logger.error(f"Error processing cog {cog_name}: {cog_err}")
        
        # Add essential commands if not already included
        self._add_essential_commands(commands)
        
        return commands
    
    def _create_command_group_payload(self, cmd) -> Dict[str, Any]:
        """
        Create a properly formatted payload for a command group with subcommands.
        
        Args:
            cmd: Command object
            
        Returns:
            Dict[str, Any]: Command payload for Discord's API
        """
        # Start with basic command information
        if hasattr(cmd, 'to_dict'):
            payload = cmd.to_dict()
        else:
            payload = {
                'name': cmd.name,
                'description': getattr(cmd, 'description', f'{cmd.name} commands'),
                'type': 1  # CHAT_INPUT type
            }
        
        # Ensure options array exists for subcommands
        if 'options' not in payload:
            payload['options'] = []
        
        # Add all subcommands as options
        if hasattr(cmd, 'children') and cmd.children:
            for sub_name, sub_cmd in cmd.children.items():
                # Create subcommand option
                sub_option = {
                    'name': sub_name,
                    'description': getattr(sub_cmd, 'description', f'Subcommand {sub_name}'),
                    'type': 1  # Subcommand type
                }
                
                # Add parameters to subcommand
                if hasattr(sub_cmd, 'to_dict'):
                    sub_dict = sub_cmd.to_dict()
                    if 'options' in sub_dict:
                        sub_option['options'] = sub_dict['options']
                
                # Add to parent command's options
                payload['options'].append(sub_option)
        
        return payload
    
    def _add_essential_commands(self, commands: List[Dict[str, Any]]) -> None:
        """
        Add essential commands if they're not already in the list.
        
        Args:
            commands: List of command payloads
        """
        # Get all command names already in the list
        command_names = {cmd.get('name', '') for cmd in commands}
        
        # Add missing essential commands
        for cmd_name in self.essential_commands:
            if cmd_name not in command_names:
                commands.append({
                    'name': cmd_name,
                    'description': f'{cmd_name.capitalize()} functionality',
                    'type': 1  # CHAT_INPUT type
                })
                logger.info(f"Added missing essential command: {cmd_name}")
    
    async def _register_commands_individually(self, commands: List[Dict[str, Any]]) -> bool:
        """
        Register commands individually with proper rate limit handling.
        
        Args:
            commands: List of command payloads
            
        Returns:
            bool: True if at least some commands were registered, False otherwise
        """
        logger.info(f"Registering {len(commands)} commands individually")
        
        success_count = 0
        essential_success = 0
        
        # Sort commands to prioritize essential ones
        sorted_commands = sorted(
            commands, 
            key=lambda cmd: cmd.get('name', '') in self.essential_commands, 
            reverse=True
        )
        
        # Register each command
        for i, cmd in enumerate(sorted_commands):
            cmd_name = cmd.get('name', f'Command {i}')
            is_essential = cmd_name in self.essential_commands
            
            try:
                # Wait for rate limits if needed
                await self._handle_rate_limits()
                
                # Register this command
                logger.info(f"Registering command: {cmd_name}")
                await self._api_request('POST', f'/applications/{self.application_id}/commands', json=cmd)
                
                success_count += 1
                if is_essential:
                    essential_success += 1
                
                logger.info(f"✅ Successfully registered command: {cmd_name}")
                
                # Add delay between commands to avoid rate limits
                delay = 1 + random.random()
                logger.info(f"Waiting {delay:.1f}s before next command...")
                await asyncio.sleep(delay)
            except Exception as e:
                logger.error(f"Failed to register command {cmd_name}: {e}")
                
                # For essential commands, retry once with exponential backoff
                if is_essential:
                    try:
                        backoff = 5 + random.random() * 3
                        logger.info(f"Retrying essential command {cmd_name} after {backoff:.1f}s...")
                        await asyncio.sleep(backoff)
                        
                        await self._handle_rate_limits()
                        await self._api_request('POST', f'/applications/{self.application_id}/commands', json=cmd)
                        
                        success_count += 1
                        essential_success += 1
                        logger.info(f"✅ Successfully registered essential command on retry: {cmd_name}")
                    except Exception as retry_err:
                        logger.error(f"Retry failed for essential command {cmd_name}: {retry_err}")
            
            # Add a longer pause every 3 commands
            if (i + 1) % 3 == 0:
                pause = 5 + random.random() * 2
                logger.info(f"Taking a longer {pause:.1f}s pause...")
                await asyncio.sleep(pause)
        
        # Determine overall success
        total_essential = len(self.essential_commands)
        essential_ratio = essential_success / total_essential if total_essential > 0 else 0
        
        logger.info(f"Registration results: {success_count}/{len(commands)} commands registered")
        logger.info(f"Essential commands: {essential_success}/{total_essential} ({essential_ratio:.0%})")
        
        # Success if at least half of all commands or 90% of essential commands registered
        return success_count >= len(commands) / 2 or essential_ratio >= 0.9
    
    async def _handle_rate_limits(self) -> None:
        """
        Check and handle Discord API rate limits.
        Waits if we're close to or at rate limits.
        """
        current_time = time.time()
        
        # If rate limit reset time is in the future, wait until it's past
        if self.rate_limit_reset > current_time:
            wait_time = self.rate_limit_reset - current_time + 1  # Add 1s buffer
            logger.info(f"Rate limit active, waiting {wait_time:.1f}s for reset...")
            await asyncio.sleep(wait_time)
        
        # If we're close to the rate limit, add a small delay
        if self.rate_limit_remaining <= 2:
            delay = 2 + random.random() * 3
            logger.info(f"Close to rate limit, adding {delay:.1f}s delay...")
            await asyncio.sleep(delay)
    
    async def _api_request(self, method: str, endpoint: str, **kwargs) -> Any:
        """
        Make an API request to Discord with rate limit handling.
        
        Args:
            method: HTTP method (GET, POST, PUT, etc.)
            endpoint: API endpoint
            **kwargs: Additional arguments for the request
            
        Returns:
            Any: API response
            
        Raises:
            Exception: If the request fails
        """
        try:
            # Make the request
            response = await self.http.request(method, endpoint, **kwargs)
            
            # Update rate limit information if available in headers
            if hasattr(self.http, '_headers'):
                headers = getattr(self.http, '_headers', {})
                
                if 'X-RateLimit-Remaining' in headers:
                    self.rate_limit_remaining = int(headers['X-RateLimit-Remaining'])
                
                if 'X-RateLimit-Reset' in headers:
                    self.rate_limit_reset = float(headers['X-RateLimit-Reset'])
            
            return response
        except Exception as e:
            if "rate limited" in str(e).lower():
                # Try to extract retry_after if available
                retry_after = 5  # Default
                if hasattr(e, 'retry_after'):
                    retry_after = float(getattr(e, 'retry_after', 5))
                
                # Update rate limit information
                self.rate_limit_remaining = 0
                self.rate_limit_reset = time.time() + retry_after
                
                logger.warning(f"Rate limited, setting reset to {retry_after:.1f}s from now")
            
            # Re-raise the exception for the caller to handle
            raise

# Helper function to use the command manager
async def register_commands(bot) -> bool:
    """
    Register all commands to Discord using the DiscordCommandManager.
    
    Args:
        bot: The Discord bot instance
        
    Returns:
        bool: True if registration was successful, False otherwise
    """
    try:
        manager = DiscordCommandManager(bot)
        return await manager.register_all_commands()
    except Exception as e:
        logger.error(f"Command registration failed: {e}")
        
        # Last resort - try the built-in sync_commands()
        try:
            logger.warning("Attempting built-in bot.sync_commands() as last resort")
            await bot.sync_commands()
            logger.info("Built-in sync_commands() succeeded")
            return True
        except Exception as sync_err:
            logger.error(f"Built-in sync_commands() also failed: {sync_err}")
            return False