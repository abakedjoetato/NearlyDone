"""
Premium Tier Management

This module handles premium tier checking and feature access.
"""

import logging
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timedelta

logger = logging.getLogger('deadside_bot.premium')

# Premium tier feature map
TIER_FEATURES = {
    0: {  # Free tier
        "max_servers": 1,
        "factions_enabled": False,
        "csv_history_days": 7,
        "stats_history_days": 7,
        "customization": False,
        "background_processing": False,
        "api_access": False,
        "support_priority": "standard"
    },
    1: {  # Basic tier
        "max_servers": 3,
        "factions_enabled": True,
        "csv_history_days": 30,
        "stats_history_days": 30,
        "customization": False,
        "background_processing": True,
        "api_access": False,
        "support_priority": "standard"
    },
    2: {  # Premium tier
        "max_servers": 10,
        "factions_enabled": True,
        "csv_history_days": 90,
        "stats_history_days": 90,
        "customization": True,
        "background_processing": True,
        "api_access": True,
        "support_priority": "priority"
    },
    3: {  # Enterprise tier
        "max_servers": -1,  # Unlimited
        "factions_enabled": True,
        "csv_history_days": -1,  # Unlimited
        "stats_history_days": -1,  # Unlimited
        "customization": True,
        "background_processing": True,
        "api_access": True,
        "support_priority": "enterprise"
    }
}

async def check_guild_tier(db, guild_id: Union[str, int]) -> int:
    """
    Check the premium tier of a guild
    
    Args:
        db: Database connection
        guild_id: Discord guild ID
        
    Returns:
        int: Premium tier (0-3)
    """
    # Convert guild_id to string if it's not already
    guild_id = str(guild_id)
    
    try:
        # Check the premium_guilds collection
        premium_collection = db["premium_guilds"]
        premium_doc = await premium_collection.find_one({"guild_id": guild_id})
        
        if not premium_doc:
            # No premium entry, default to free tier
            return 0
        
        # Check if premium is expired
        expiry = premium_doc.get("expiry")
        if expiry and datetime.utcnow() > expiry:
            # Premium expired, downgrade to free tier
            await premium_collection.update_one(
                {"guild_id": guild_id},
                {"$set": {"tier": 0, "expired": True}}
            )
            logger.info(f"Premium expired for guild {guild_id}, downgraded to tier 0")
            return 0
        
        # Return active tier
        tier = premium_doc.get("tier", 0)
        return tier
    except Exception as e:
        logger.error(f"Error checking premium tier for guild {guild_id}: {e}")
        # Default to free tier on error
        return 0

async def check_feature_access(db, guild_id: Union[str, int], feature: str) -> bool:
    """
    Check if a guild has access to a specific premium feature
    
    Args:
        db: Database connection
        guild_id: Discord guild ID
        feature: Feature name to check
        
    Returns:
        bool: True if the guild has access to the feature, False otherwise
    """
    # Get the guild's tier
    tier = await check_guild_tier(db, guild_id)
    
    # Get features for this tier
    tier_features = TIER_FEATURES.get(tier, TIER_FEATURES[0])
    
    # Check if the feature exists and is enabled
    return tier_features.get(feature, False)

def get_tier_display_info(tier: int) -> Dict[str, Any]:
    """
    Get display information for a premium tier
    
    Args:
        tier: Premium tier number
        
    Returns:
        Dict containing tier display information
    """
    tier_names = ["Free", "Basic", "Premium", "Enterprise"]
    tier_colors = [0x808080, 0x00FF00, 0x0000FF, 0xFFD700]  # Gray, Green, Blue, Gold
    tier_emojis = ["🔘", "🔹", "🔷", "💎"]
    
    return {
        "name": tier_names[tier] if tier < len(tier_names) else f"Tier {tier}",
        "color": tier_colors[tier] if tier < len(tier_colors) else 0xFFFFFF,
        "emoji": tier_emojis[tier] if tier < len(tier_emojis) else "✨",
        "features": TIER_FEATURES.get(tier, {})
    }