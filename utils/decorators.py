"""
Decorator Utilities

This module contains decorators used across commands and functionality.
"""

import functools
import discord
from typing import Callable, Optional, Any

def guild_only():
    """
    Decorator to ensure a command can only be run in a guild context
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(self, ctx, *args, **kwargs):
            if not ctx.guild:
                await ctx.respond("This command can only be used in a server.", ephemeral=True)
                return
            return await func(self, ctx, *args, **kwargs)
        return wrapper
    return decorator

def premium_tier_required(tier: int = 1):
    """
    Decorator to restrict commands based on premium tier
    
    Args:
        tier: Minimum premium tier required (0 = free, 1 = basic, 2 = premium, 3 = enterprise)
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(self, ctx, *args, **kwargs):
            from utils.premium import check_guild_tier
            
            if not ctx.guild:
                await ctx.respond("This command can only be used in a server.", ephemeral=True)
                return
            
            # For development environment, bypass premium check
            if hasattr(self.bot, 'dev_mode') and self.bot.dev_mode:
                return await func(self, ctx, *args, **kwargs)
            
            # Get guild's premium tier
            guild_tier = await check_guild_tier(self.bot.db, ctx.guild.id)
            
            # Check if guild has sufficient tier
            if guild_tier < tier:
                tier_names = ["Free", "Basic", "Premium", "Enterprise"]
                required = tier_names[tier] if tier < len(tier_names) else f"Tier {tier}"
                current = tier_names[guild_tier] if guild_tier < len(tier_names) else f"Tier {guild_tier}"
                
                await ctx.respond(
                    f"⚠️ This command requires {required} tier, but this server is on {current} tier.\n"
                    f"Use `/premium upgrade` to upgrade your server's features.",
                    ephemeral=True
                )
                return
            
            return await func(self, ctx, *args, **kwargs)
        return wrapper
    return decorator