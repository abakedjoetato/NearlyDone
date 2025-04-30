import discord
from discord.ext import commands, tasks
import logging
import asyncio
from datetime import datetime
from database.models import Server, GuildConfig, ConnectionEvent
from utils.embeds import create_connection_embed
from utils.guild_isolation import get_guild_servers, get_server_by_name

logger = logging.getLogger('deadside_bot.cogs.connection')

# Create slash command group
connection_group = discord.SlashCommandGroup(
    name="connections",
    description="Commands for managing player connection notifications",
    default_member_permissions=discord.Permissions(manage_channels=True),
    contexts=[discord.InteractionContextType.guild],  # Guild command only
    integration_types=[discord.IntegrationType.guild_install]
)

class ConnectionCommands(commands.Cog):
    """Commands for managing player connection notifications"""
    
    def __init__(self, bot):
        self.bot = bot
        self.db = getattr(bot, 'db', None)  # Get db from bot if available
        self.server_trackers = {}
        self.connection_group = connection_group
        self.trackers_initialized = False
        
    async def cog_load(self):
        """Called when the cog is loaded. Safe to use async code here."""
        logger.info("Connection commands cog loaded")
        # Ensure db is set before attempting any database operations
        if not self.db and hasattr(self.bot, 'db'):
            self.db = self.bot.db
            
        # Start tracking after a short delay to ensure everything is ready
        self.bot.loop.create_task(self.initialize_connection_trackers())
        
    # This function is needed to expose the commands to the bot
    def get_commands(self):
        """Return all commands this cog provides"""
        return [connection_group]
    
    async def initialize_connection_trackers(self):
        """Initialize connection trackers for all configured servers"""
        if self.trackers_initialized:
            logger.debug("Connection trackers already initialized, skipping")
            return
            
        await self.bot.wait_until_ready()
        
        try:
            # Ensure we have a database instance
            if not self.db:
                logger.error("Database instance not available in initialize_connection_trackers")
                return
                
            # Get all guild configs with connection channels
            collection = await self.db.get_collection("guild_configs")
            cursor = collection.find({})
            configs = await cursor.to_list(None)
            
            # Filter configs with a connection channel
            configs = [config for config in configs if config.get("connection_channel") is not None]
            
            if not configs:
                logger.info("No guilds with connection tracking configured")
                return
                
            # Initialize trackers for each guild
            for config in configs:
                guild_id = config["guild_id"]
                channel_id = config["connection_channel"]
                
                # Get servers for this guild
                servers = await get_guild_servers(self.db, guild_id)
                
                for server in servers:
                    server_id = str(server["_id"])
                    self.server_trackers[server_id] = {
                        "guild_id": guild_id,
                        "channel_id": channel_id,
                        "last_connection_id": None
                    }
                    
                    # Start the tracker
                    tracker_name = f"connection_tracker_{server_id}"
                    existing_tasks = [t for t in asyncio.all_tasks() if t.get_name() == tracker_name]
                    
                    if not existing_tasks:
                        task = self.bot.loop.create_task(
                            self.track_server_connections(server_id, channel_id),
                            name=tracker_name
                        )
                        logger.debug(f"Started connection tracker for server {server_id}")
            
            logger.info(f"Initialized connection trackers for {len(self.server_trackers)} servers")
            self.trackers_initialized = True
                
        except Exception as e:
            logger.error(f"Error initializing connection trackers: {e}")
    
    @connection_group.command(
        name="channel",
        description="Set the channel for player connection notifications",
        contexts=[discord.InteractionContextType.guild],
        integration_types=[discord.IntegrationType.guild_install]
    )
    async def set_channel(self, ctx, 
                         channel: discord.Option(discord.TextChannel, "Channel to send notifications to", required=False) = None):
        """
        Set the channel for player connection notifications
        
        If no channel is provided, the current channel will be used.
        """
        # Defer response for potentially slow DB operations
        await ctx.defer()
        
        try:
            # Ensure we have a database instance
            if not self.db:
                logger.error("Database instance not available in set_channel command")
                await ctx.respond("⚠️ Database connection not available. Please try again later.")
                return
                
            # Use current channel if none specified
            if not channel:
                channel = ctx.channel
            
            # Verify permissions
            bot_member = ctx.guild.get_member(self.bot.user.id)
            if not channel.permissions_for(bot_member).send_messages:
                await ctx.respond(f"❌ I don't have permission to send messages in {channel.mention}")
                return
            
            # Update guild config
            guild_id = str(ctx.guild.id)
            guild_configs = await self.db.get_collection("guild_configs")
            
            result = await guild_configs.update_one(
                {"guild_id": guild_id},
                {"$set": {"connection_channel": str(channel.id)}},
                upsert=True
            )
            
            # Update trackers for all servers in this guild
            servers = await get_guild_servers(self.db, guild_id)
            
            for server in servers:
                server_id = str(server["_id"])
                
                # Update tracker info
                self.server_trackers[server_id] = {
                    "guild_id": guild_id,
                    "channel_id": str(channel.id),
                    "last_connection_id": None
                }
                
                # Start the tracker if not already running
                tracker_name = f"connection_tracker_{server_id}"
                if not any(task.get_name() == tracker_name for task in asyncio.all_tasks()):
                    self.bot.loop.create_task(
                        self.track_server_connections(server_id, str(channel.id)),
                        name=tracker_name
                    )
            
            # Create success embed
            embed = discord.Embed(
                title="✅ Connection Channel Set",
                description=f"Player connection notifications will now be sent to {channel.mention}",
                color=discord.Color.green()
            )
            
            # Add related commands
            embed.add_field(
                name="📝 Related Commands",
                value="`/connections disable` - Turn off connection notifications\n"
                      "`/connections list` - View recent player connections",
                inline=False
            )
            
            await ctx.respond(embed=embed)
                
        except Exception as e:
            logger.error(f"Error setting connection channel: {e}")
            await ctx.respond(f"❌ Error setting connection channel: {e}")
            
    @connection_group.command(
        name="disable", 
        description="Disable connection notifications for this server", 
        contexts=[discord.InteractionContextType.guild],
        integration_types=[discord.IntegrationType.guild_install]
    )
    async def disable_connections(self, ctx):
        """Disable connection notifications for this guild"""
        await ctx.defer()
        
        try:
            # Ensure we have a database instance
            if not self.db:
                logger.error("Database instance not available in disable_connections command")
                await ctx.respond("⚠️ Database connection not available. Please try again later.")
                return
                
            # Update guild config
            guild_id = str(ctx.guild.id)
            guild_configs = await self.db.get_collection("guild_configs")
            
            await guild_configs.update_one(
                {"guild_id": guild_id},
                {"$set": {"connection_channel": None}},
                upsert=True
            )
            
            # Remove trackers for all servers in this guild
            servers = await get_guild_servers(self.db, guild_id)
            removed_count = 0
            
            for server in servers:
                server_id = str(server["_id"])
                if server_id in self.server_trackers:
                    del self.server_trackers[server_id]
                    removed_count += 1
            
            # Create response embed
            embed = discord.Embed(
                title="❌ Connection Notifications Disabled",
                description="Player connection notifications have been turned off",
                color=discord.Color.red()
            )
            
            embed.add_field(
                name="Details",
                value=f"Disabled tracking for {removed_count} servers",
                inline=False
            )
            
            embed.add_field(
                name="📝 Re-enable",
                value="Use `/connections channel #channel` to turn notifications back on",
                inline=False
            )
            
            await ctx.respond(embed=embed)
                
        except Exception as e:
            logger.error(f"Error disabling connections: {e}")
            await ctx.respond(f"❌ Error disabling connections: {e}")
            
    @connection_group.command(
        name="list", 
        description="List recent player connections for a server", 
        contexts=[discord.InteractionContextType.guild],
        integration_types=[discord.IntegrationType.guild_install]
    )
    async def list_connections(self, ctx, 
                               server_name: discord.Option(str, "Server name to show connections for", required=False) = None,
                               limit: discord.Option(int, "Number of connections to show (max: 20)", min_value=1, max_value=20, required=False) = 10):
        """
        List recent player connections for a server
        
        If no server name is provided, connections for all servers will be shown.
        Default limit is 10, max limit is 20.
        """
        await ctx.defer()
        
        try:
            # Ensure we have a database instance
            if not self.db:
                logger.error("Database instance not available in list_connections command")
                await ctx.respond("⚠️ Database connection not available. Please try again later.")
                return
                
            # Enforce limit
            if limit > 20:
                limit = 20
            
            guild_id = str(ctx.guild.id)
            
            if server_name:
                # Get connections for specific server
                server = await get_server_by_name(self.db, guild_id, server_name)
                
                if not server:
                    await ctx.respond(f"⚠️ Server '{server_name}' not found. Use `/server list` to see all configured servers.")
                    return
                
                server_id = str(server["_id"])
                
                # Get recent connections
                collection = await self.db.get_collection("connection_events")
                cursor = collection.find({"server_id": server_id}).sort("timestamp", -1).limit(limit)
                connections = await cursor.to_list(None)
                
                # Create embed
                embed = discord.Embed(
                    title=f"Recent Connections for {server['name']}",
                    description=f"Last {len(connections)} connection events",
                    color=discord.Color.blue(),
                    timestamp=datetime.utcnow()
                )
                
                if not connections:
                    embed.add_field(
                        name="No Data",
                        value="No connection events found for this server",
                        inline=False
                    )
                else:
                    for conn in connections:
                        event_type = conn.get("event_type", "unknown").capitalize()
                        timestamp = conn.get("timestamp")
                        if timestamp:
                            time_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
                            rel_time = f"<t:{int(timestamp.timestamp())}:R>"
                        else:
                            time_str = "Unknown"
                            rel_time = "Unknown"
                            
                        player_name = conn.get("player_name", "Unknown Player")
                        
                        if event_type.lower() == "kick":
                            embed.add_field(
                                name=f"{event_type}: {player_name}",
                                value=f"Time: {time_str} ({rel_time})\nReason: {conn.get('reason', 'Unknown')}",
                                inline=False
                            )
                        else:
                            emoji = "🟢" if event_type.lower() == "connect" else "🔴"
                            embed.add_field(
                                name=f"{emoji} {event_type}: {player_name}",
                                value=f"Time: {time_str} ({rel_time})",
                                inline=True
                            )
                
                await ctx.respond(embed=embed)
            else:
                # Get connections for all servers
                servers = await get_guild_servers(self.db, guild_id)
                
                if not servers:
                    await ctx.respond("No servers have been configured yet. Use `/server add` to add a server.")
                    return
                
                # Create a combined embed for all servers
                combined_embed = discord.Embed(
                    title="Recent Connections for All Servers",
                    description=f"Last {limit} connection events per server",
                    color=discord.Color.blue(),
                    timestamp=datetime.utcnow()
                )
                
                # Track if we found any connections at all
                any_connections = False
                
                # Get recent connections for each server
                for server in servers:
                    server_id = str(server["_id"])
                    server_name = server.get("name", "Unknown Server")
                    
                    collection = await self.db.get_collection("connection_events")
                    cursor = collection.find({"server_id": server_id}).sort("timestamp", -1).limit(limit)
                    connections = await cursor.to_list(None)
                    
                    if connections:
                        any_connections = True
                        combined_embed.add_field(
                            name=f"📊 {server_name} ({len(connections)} events)",
                            value="Server connection events",
                            inline=False
                        )
                        
                        for conn in connections:
                            event_type = conn.get("event_type", "unknown").capitalize()
                            timestamp = conn.get("timestamp")
                            if timestamp:
                                time_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
                                rel_time = f"<t:{int(timestamp.timestamp())}:R>"
                            else:
                                time_str = "Unknown"
                                rel_time = "Unknown"
                                
                            player_name = conn.get("player_name", "Unknown Player")
                            
                            if event_type.lower() == "kick":
                                field_value = f"Time: {time_str} ({rel_time})\nReason: {conn.get('reason', 'Unknown')}"
                            else:
                                emoji = "🟢" if event_type.lower() == "connect" else "🔴"
                                field_value = f"Time: {time_str} ({rel_time})"
                                
                            combined_embed.add_field(
                                name=f"{emoji if event_type.lower() != 'kick' else '❌'} {event_type}: {player_name}",
                                value=field_value,
                                inline=True
                            )
                
                if not any_connections:
                    combined_embed.add_field(
                        name="No Data",
                        value="No connection events found for any servers",
                        inline=False
                    )
                
                await ctx.respond(embed=combined_embed)
                
        except Exception as e:
            logger.error(f"Error listing connections: {e}")
            await ctx.respond(f"❌ An error occurred: {e}")
    
    async def track_server_connections(self, server_id, channel_id):
        """
        Background task to track new connections for a server and send to channel
        
        Args:
            server_id: MongoDB ObjectId of the server (as string)
            channel_id: Discord channel ID to send connection messages (as string)
        """
        # Set task name for identification
        task_name = f"connection_tracker_{server_id}"
        asyncio.current_task().set_name(task_name)
        
        # Log start
        logger.info(f"Started connection tracker for server {server_id} to channel {channel_id}")
        
        try:
            # Ensure we have a database instance
            if not self.db:
                logger.error(f"Database instance not available in track_server_connections for server {server_id}")
                return
            
            # Get initial last connection ID
            if server_id in self.server_trackers and self.server_trackers[server_id].get("last_connection_id"):
                last_connection_id = self.server_trackers[server_id]["last_connection_id"]
            else:
                # Get the most recent connection for this server
                collection = await self.db.get_collection("connection_events")
                cursor = collection.find({"server_id": server_id}).sort("timestamp", -1).limit(1)
                latest_connection = await cursor.to_list(None)
                
                if latest_connection:
                    # Use either _id or id field depending on what's available
                    last_connection_id = latest_connection[0].get("_id") or latest_connection[0].get("id")
                else:
                    last_connection_id = None
                
                # Update tracker
                if server_id in self.server_trackers:
                    self.server_trackers[server_id]["last_connection_id"] = last_connection_id
            
            while True:
                try:
                    # Check if tracker still exists (could be removed if disabled)
                    if server_id not in self.server_trackers:
                        logger.debug(f"Connection tracker for server {server_id} was disabled")
                        return
                    
                    # Get channel
                    channel = self.bot.get_channel(int(channel_id))
                    if not channel:
                        logger.warning(f"Could not find channel {channel_id} for connections")
                        await asyncio.sleep(60)  # Long sleep if channel is missing
                        continue
                    
                    # Get new connections
                    collection = await self.db.get_collection("connection_events")
                    cursor = collection.find({"server_id": server_id}).sort("timestamp", -1).limit(100)
                    all_connections = await cursor.to_list(None)
                    
                    # Filter connections that are newer than last_connection_id
                    if last_connection_id:
                        new_connections = []
                        for conn in all_connections:
                            conn_id = conn.get("_id") or conn.get("id")
                            # If we can't determine which is newer, we need to compare timestamps
                            if conn_id != last_connection_id:
                                # For simplicity, we just check if it's not the last one we processed
                                # A more robust solution would track timestamps and IDs
                                new_connections.append(conn)
                    else:
                        # If no last connection ID, just take the most recent one
                        new_connections = all_connections[:1] if all_connections else []
                    
                    # Process each new connection and send an embed
                    for conn in new_connections:
                        # Get server info for the embed
                        server = await get_server_by_name(self.db, self.server_trackers[server_id]["guild_id"], None, server_id)
                        server_name = server.get("name", "Unknown Server") if server else "Unknown Server"
                        
                        # Create event data for the embed
                        event_type = conn.get("event_type", "unknown")
                        timestamp = conn.get("timestamp")
                        player_name = conn.get("player_name", "Unknown Player")
                        reason = conn.get("reason")
                        
                        # Create embed based on event type
                        embed = create_connection_embed(
                            player_data={
                                "player_name": player_name,
                                "player_id": conn.get("player_id", "Unknown")
                            },
                            connection_type=event_type,
                            server_name=server_name,
                            timestamp=timestamp,
                            reason=reason
                        )
                        
                        # Send the embed
                        await channel.send(embed=embed)
                        
                        # Update last connection ID
                        last_connection_id = conn.get("_id") or conn.get("id")
                        if server_id in self.server_trackers:
                            self.server_trackers[server_id]["last_connection_id"] = last_connection_id
                    
                    # Log the number of connections processed
                    if new_connections:
                        logger.debug(f"Processed {len(new_connections)} new connections for server {server_id}")
                    
                    # Sleep before next check
                    await asyncio.sleep(15)
                
                except Exception as e:
                    logger.error(f"Error in connection tracker for server {server_id}: {e}")
                    await asyncio.sleep(60)  # Longer sleep on error
        
        except asyncio.CancelledError:
            logger.info(f"Connection tracker for server {server_id} was cancelled")
            return
        except Exception as e:
            logger.error(f"Fatal error in connection tracker for server {server_id}: {e}")

def setup(bot):
    """Add the cog to the bot directly when loaded via extension"""
    bot.add_cog(ConnectionCommands(bot))