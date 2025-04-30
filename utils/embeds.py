import discord
import logging
import datetime

logger = logging.getLogger('deadside_bot.utils.embeds')

def create_success_embed(title, description=None, fields=None):
    """
    Create a nice-looking success embed with Emerald-styled theme
    
    Args:
        title: Embed title
        description: Optional embed description
        fields: Optional list of field dicts with name, value, inline keys
        
    Returns:
        discord.Embed: Formatted embed
    """
    embed = discord.Embed(
        title=title,
        description=description,
        color=discord.Color.green()  # Emerald theme - green for success
    )
    
    if fields:
        for field in fields:
            embed.add_field(
                name=field.get("name", ""),
                value=field.get("value", ""),
                inline=field.get("inline", False)
            )
            
    return embed

def create_error_embed(title, description=None, fields=None):
    """
    Create a nice-looking error embed with Emerald-styled theme
    
    Args:
        title: Embed title
        description: Optional embed description
        fields: Optional list of field dicts with name, value, inline keys
        
    Returns:
        discord.Embed: Formatted embed
    """
    embed = discord.Embed(
        title=title,
        description=description,
        color=discord.Color.red()  # Emerald theme - red for errors
    )
    
    if fields:
        for field in fields:
            embed.add_field(
                name=field.get("name", ""),
                value=field.get("value", ""),
                inline=field.get("inline", False)
            )
            
    return embed

def create_warning_embed(title, description=None, fields=None):
    """
    Create a nice-looking warning embed with Emerald-styled theme
    
    Args:
        title: Embed title
        description: Optional embed description
        fields: Optional list of field dicts with name, value, inline keys
        
    Returns:
        discord.Embed: Formatted embed
    """
    embed = discord.Embed(
        title=title,
        description=description,
        color=discord.Color.gold()  # Emerald theme - gold for warnings
    )
    
    if fields:
        for field in fields:
            embed.add_field(
                name=field.get("name", ""),
                value=field.get("value", ""),
                inline=field.get("inline", False)
            )
            
    return embed

def create_info_embed(title, description=None, fields=None):
    """
    Create a nice-looking info embed with Emerald-styled theme
    
    Args:
        title: Embed title
        description: Optional embed description
        fields: Optional list of field dicts with name, value, inline keys
        
    Returns:
        discord.Embed: Formatted embed
    """
    embed = discord.Embed(
        title=title,
        description=description,
        color=discord.Color.blue()  # Emerald theme - blue for info
    )
    
    if fields:
        for field in fields:
            embed.add_field(
                name=field.get("name", ""),
                value=field.get("value", ""),
                inline=field.get("inline", False)
            )
            
    return embed
    
def create_mission_embed(mission, active_status=True, display_location=True):
    """
    Create a mission embed with nice formatting
    
    Args:
        mission: Mission document with mission details
        active_status: Whether this is an active mission
        display_location: Whether to display mission location
        
    Returns:
        discord.Embed: Formatted mission embed
    """
    # Set color based on mission status
    if active_status:
        color = discord.Color.green()  # Active mission
    else:
        color = discord.Color.lighter_grey()  # Completed mission
    
    # Get mission name with fallback
    mission_name = mission.get("mission_name", "Unknown Mission")
    
    # Create base embed
    embed = discord.Embed(
        title=f"Mission: {mission_name}",
        color=color,
        timestamp=datetime.datetime.now()
    )
    
    # Add mission type if available
    mission_type = mission.get("mission_type")
    if mission_type:
        embed.add_field(
            name="Type",
            value=mission_type,
            inline=True
        )
    
    # Add mission location if available and requested
    location = mission.get("location")
    if location and display_location:
        embed.add_field(
            name="Location",
            value=f"{location['x']}, {location['y']}",
            inline=True
        )
    
    # Add server information
    server_id = mission.get("server_id")
    if server_id:
        embed.add_field(
            name="Server ID",
            value=str(server_id),
            inline=True
        )
    
    # Add timing information
    start_time = mission.get("start_time")
    if start_time:
        if isinstance(start_time, str):
            # Try to parse string to datetime if needed
            try:
                start_time = datetime.datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            except:
                pass
        
        embed.add_field(
            name="Started",
            value=f"<t:{int(start_time.timestamp())}:R>",
            inline=True
        )
    
    # Add end time for completed missions
    end_time = mission.get("end_time")
    if end_time and not active_status:
        if isinstance(end_time, str):
            # Try to parse string to datetime if needed
            try:
                end_time = datetime.datetime.fromisoformat(end_time.replace('Z', '+00:00'))
            except:
                pass
                
        embed.add_field(
            name="Ended",
            value=f"<t:{int(end_time.timestamp())}:R>",
            inline=True
        )
        
        # Calculate duration
        if start_time and end_time:
            duration = end_time - start_time
            minutes = int(duration.total_seconds() / 60)
            embed.add_field(
                name="Duration",
                value=f"{minutes} minutes",
                inline=True
            )
    
    # Set footer based on status
    if active_status:
        embed.set_footer(text="🔴 Active Mission")
    else:
        embed.set_footer(text="✅ Completed Mission")
        
    return embed
    
def create_server_embed(server, status=None, uptime=None, player_count=None):
    """
    Create a server embed with nice formatting
    
    Args:
        server: Server document with server details
        status: Optional server status (online/offline)
        uptime: Optional server uptime duration
        player_count: Optional current player count
        
    Returns:
        discord.Embed: Formatted server embed
    """
    # Set color based on server status
    if status == "online":
        color = discord.Color.green()  # Online server
    elif status == "offline":
        color = discord.Color.red()  # Offline server
    else:
        color = discord.Color.blue()  # Unknown status
    
    # Get server name with fallback
    server_name = server.get("name", "Unknown Server")
    
    # Create base embed
    embed = discord.Embed(
        title=f"Server: {server_name}",
        color=color,
        timestamp=datetime.datetime.now()
    )
    
    # Add IP and port
    ip = server.get("ip", "Unknown")
    port = server.get("port", "Unknown")
    embed.add_field(
        name="Connection",
        value=f"`{ip}:{port}`",
        inline=False
    )
    
    # Add status information if provided
    if status:
        status_emoji = "🟢" if status == "online" else "🔴"
        embed.add_field(
            name="Status",
            value=f"{status_emoji} {status.title()}",
            inline=True
        )
    
    # Add uptime if provided
    if uptime:
        embed.add_field(
            name="Uptime",
            value=uptime,
            inline=True
        )
    
    # Add player count if provided
    if player_count is not None:
        embed.add_field(
            name="Players",
            value=str(player_count),
            inline=True
        )
    
    # Add access method
    access_method = server.get("access_method", "Unknown")
    embed.add_field(
        name="Access Method",
        value=access_method.title(),
        inline=True
    )
    
    # Add footer with server ID for reference
    server_id = server.get("_id", "Unknown")
    embed.set_footer(text=f"Server ID: {server_id}")
    
    return embed
    
def create_player_embed(player, additional_stats=None):
    """
    Create a player embed with nice formatting
    
    Args:
        player: Player document with player details
        additional_stats: Optional additional statistics to display
        
    Returns:
        discord.Embed: Formatted player embed
    """
    # Get player name with fallback
    player_name = player.get("player_name", "Unknown Player")
    player_id = player.get("player_id", "Unknown ID")
    
    # Create base embed with emerald (green) color for players
    embed = discord.Embed(
        title=f"Player: {player_name}",
        description=f"ID: `{player_id}`",
        color=discord.Color.green(),
        timestamp=datetime.datetime.now()
    )
    
    # Add Discord link if available
    discord_id = player.get("discord_id")
    if discord_id:
        embed.add_field(
            name="Discord",
            value=f"<@{discord_id}>",
            inline=True
        )
    
    # Add basic stats
    total_kills = player.get("total_kills", 0)
    total_deaths = player.get("total_deaths", 0)
    
    # Calculate K/D ratio
    if total_deaths > 0:
        kd_ratio = round(total_kills / total_deaths, 2)
    else:
        kd_ratio = total_kills  # If no deaths, K/D is just kills
    
    embed.add_field(
        name="Kills",
        value=str(total_kills),
        inline=True
    )
    
    embed.add_field(
        name="Deaths",
        value=str(total_deaths),
        inline=True
    )
    
    embed.add_field(
        name="K/D Ratio",
        value=str(kd_ratio),
        inline=True
    )
    
    # Add faction if available
    faction_id = player.get("faction_id")
    if faction_id:
        # TODO: Look up faction name if needed
        embed.add_field(
            name="Faction",
            value=f"ID: {faction_id}",
            inline=True
        )
    
    # Add rivalries if available
    nemesis_name = player.get("nemesis_name")
    nemesis_deaths = player.get("nemesis_deaths", 0)
    if nemesis_name and nemesis_deaths > 0:
        embed.add_field(
            name="Nemesis",
            value=f"{nemesis_name} ({nemesis_deaths} deaths)",
            inline=True
        )
    
    prey_name = player.get("prey_name")
    prey_kills = player.get("prey_kills", 0)
    if prey_name and prey_kills > 0:
        embed.add_field(
            name="Prey",
            value=f"{prey_name} ({prey_kills} kills)",
            inline=True
        )
    
    # Add any additional stats
    if additional_stats:
        for name, value in additional_stats.items():
            embed.add_field(
                name=name,
                value=str(value),
                inline=True
            )
    
    # Add timestamps
    first_seen = player.get("first_seen")
    last_seen = player.get("last_seen")
    
    if first_seen:
        if isinstance(first_seen, str):
            # Try to parse string to datetime if needed
            try:
                first_seen = datetime.datetime.fromisoformat(first_seen.replace('Z', '+00:00'))
            except:
                pass
                
        embed.add_field(
            name="First Seen",
            value=f"<t:{int(first_seen.timestamp())}:R>",
            inline=True
        )
    
    if last_seen:
        if isinstance(last_seen, str):
            # Try to parse string to datetime if needed
            try:
                last_seen = datetime.datetime.fromisoformat(last_seen.replace('Z', '+00:00'))
            except:
                pass
                
        embed.add_field(
            name="Last Seen",
            value=f"<t:{int(last_seen.timestamp())}:R>",
            inline=True
        )
    
    # Set footer with player ID for reference
    embed.set_footer(text=f"Player ID: {player_id}")
    
    return embed
    
def create_connection_embed(player_data, connection_type, server_name=None, timestamp=None, reason=None):
    """
    Create a connection event embed (connect/disconnect)
    
    Args:
        player_data: Player document or dictionary with player details
        connection_type: Type of connection event ("connect" or "disconnect")
        server_name: Optional server name
        timestamp: Optional timestamp for the event
        reason: Optional reason for disconnect
        
    Returns:
        discord.Embed: Formatted connection embed
    """
    # Get player information
    if isinstance(player_data, dict):
        player_name = player_data.get("player_name", "Unknown Player")
        player_id = player_data.get("player_id", "Unknown ID")
    else:
        player_name = getattr(player_data, "player_name", "Unknown Player")
        player_id = getattr(player_data, "player_id", "Unknown ID")
    
    # Set color and title based on connection type
    if connection_type.lower() == "connect":
        color = discord.Color.green()
        title = f"Player Connected"
        emoji = "🟢"
    else:  # disconnect
        color = discord.Color.red()
        title = f"Player Disconnected"
        emoji = "🔴"
    
    # Create the embed
    embed = discord.Embed(
        title=title,
        color=color,
        timestamp=timestamp or datetime.datetime.now()
    )
    
    # Add player information
    embed.add_field(
        name="Player",
        value=f"{emoji} **{player_name}**",
        inline=False
    )
    
    # Add server if provided
    if server_name:
        embed.add_field(
            name="Server",
            value=server_name,
            inline=True
        )
    
    # Add reason for disconnect if provided
    if reason and connection_type.lower() == "disconnect":
        embed.add_field(
            name="Reason",
            value=reason,
            inline=True
        )
    
    # Add player ID in footer
    embed.set_footer(text=f"Player ID: {player_id}")
    
    return embed

def create_leaderboard_embed(title, players, stat_name="kills", top_count=10):
    """
    Create a leaderboard embed
    
    Args:
        title: Leaderboard title
        players: List of player documents with stats
        stat_name: Name of the stat to rank by
        top_count: Number of players to show
        
    Returns:
        discord.Embed: Formatted leaderboard embed
    """
    # Create base embed with gold color for leaderboards
    embed = discord.Embed(
        title=title,
        color=discord.Color.gold(),
        timestamp=datetime.datetime.now()
    )
    
    # Ensure we have a reasonable number of players
    if not players:
        embed.description = "No players found for this leaderboard."
        return embed
    
    # Sort players by the specified stat
    sorted_players = sorted(
        players, 
        key=lambda p: p.get(stat_name, 0), 
        reverse=True
    )
    
    # Limit to top_count
    top_players = sorted_players[:min(top_count, len(sorted_players))]
    
    # Create formatted leaderboard
    leaderboard_text = ""
    for i, player in enumerate(top_players):
        # Get rank emoji
        if i == 0:
            rank_emoji = "🥇"
        elif i == 1:
            rank_emoji = "🥈"
        elif i == 2:
            rank_emoji = "🥉"
        else:
            rank_emoji = f"#{i+1}"
        
        # Get player name and stat value
        player_name = player.get("player_name", "Unknown")
        stat_value = player.get(stat_name, 0)
        
        # Add to leaderboard text
        leaderboard_text += f"{rank_emoji} **{player_name}**: {stat_value}\n"
    
    # Set the leaderboard as the description
    embed.description = leaderboard_text
    
    # Add footer with stats info
    embed.set_footer(text=f"Top {len(top_players)} players by {stat_name}")
    
    return embed