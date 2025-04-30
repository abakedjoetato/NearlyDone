"""
Embed Utilities

This module contains utility functions for creating consistent Discord embeds
across different commands and features.
"""

import discord
from datetime import datetime
from typing import Dict, Any, List, Optional, Union

def create_faction_embed(faction, guild, stats: Dict[str, Any]) -> discord.Embed:
    """
    Create a standardized faction information embed
    
    Args:
        faction: The faction object
        guild: The Discord guild object
        stats: Dictionary containing faction statistics
        
    Returns:
        discord.Embed: The formatted embed
    """
    # Create embed with faction details
    embed = discord.Embed(
        title=f"Faction: {faction.name} [{faction.abbreviation}]",
        description=f"Created {format_date(faction.created_at)}",
        color=discord.Color.green()
    )
    
    # Add leader information
    leader_id = faction.leader_id
    embed.add_field(
        name="Leader",
        value=f"<@{leader_id}>",
        inline=True
    )
    
    # Add member count
    embed.add_field(
        name="Members",
        value=str(len(faction.members)),
        inline=True
    )
    
    # Add stats fields
    if stats:
        # Basic stats
        embed.add_field(
            name="Stats",
            value=(
                f"Kills: {stats.get('kills', 0)}\n"
                f"Deaths: {stats.get('deaths', 0)}\n"
                f"K/D Ratio: {calculate_kd(stats.get('kills', 0), stats.get('deaths', 0))}"
            ),
            inline=True
        )
        
        # Longest shot
        longest_shot = stats.get('longest_shot', 0)
        if longest_shot > 0:
            embed.add_field(
                name="Longest Shot",
                value=f"{longest_shot}m",
                inline=True
            )
        
        # Top weapon
        weapon_counts = stats.get('weapon_counts', {})
        if weapon_counts:
            top_weapons = sorted(weapon_counts.items(), key=lambda x: x[1], reverse=True)[:3]
            weapons_text = "\n".join([f"{weapon}: {count}" for weapon, count in top_weapons])
            embed.add_field(
                name="Top Weapons",
                value=weapons_text if weapons_text else "None",
                inline=True
            )
    
    # Add members list (limits to first 10)
    members_list = []
    for i, member_id in enumerate(faction.members[:10]):
        members_list.append(f"<@{member_id}>")
    
    # If there are more members than shown
    if len(faction.members) > 10:
        members_list.append(f"...and {len(faction.members) - 10} more")
    
    if members_list:
        embed.add_field(
            name="Members",
            value="\n".join(members_list),
            inline=False
        )
    
    # Set footer with faction ID
    embed.set_footer(text=f"Faction ID: {faction._id} | Guild: {guild.name}")
    
    return embed

def calculate_kd(kills: int, deaths: int) -> str:
    """Calculate K/D ratio with proper formatting"""
    if deaths == 0:
        if kills == 0:
            return "0.00"
        else:
            return f"{kills}.00"  # Infinite K/D displayed as just the kill count
    
    ratio = kills / deaths
    return f"{ratio:.2f}"

def format_date(date_obj: Optional[datetime]) -> str:
    """Format a datetime object consistently"""
    if not date_obj:
        return "Unknown date"
    
    return date_obj.strftime("%Y-%m-%d %H:%M UTC")