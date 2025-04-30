import discord
from discord.ext import commands, tasks
import logging
import asyncio
from datetime import datetime, timedelta
from database.connection import Database
from database.models import Server, GuildConfig, ServerEvent
from utils.embeds import create_mission_embed
from utils.guild_isolation import get_guild_servers, get_server_by_name
from utils.premium import check_feature_access

logger = logging.getLogger('deadside_bot.cogs.mission')

# Create slash command group for mission commands
mission_group = discord.SlashCommandGroup(
    name="missions",
    description="Commands for managing mission and server event notifications",
    default_member_permissions=discord.Permissions(manage_channels=True)
)

class MissionCommands(commands.Cog):
    """Commands for managing mission and server event notifications"""
    
    def __init__(self, bot):
        self.bot = bot
        self.db = getattr(bot, 'db', None)  # Get db from bot if available
        # We'll store active tracking settings here
        self.tracking_enabled = {}  # guild_id -> enabled boolean
        self.mission_channels = {}  # guild_id -> channel_id
        self.tracking_tasks = {}    # guild_id -> asyncio task
        self.mission_group = mission_group
        
    async def cog_load(self):
        """Called when the cog is loaded"""
        logger.info("Mission commands cog loaded")
        # Ensure db is set before attempting any database operations
        if not self.db and hasattr(self.bot, 'db'):
            self.db = self.bot.db
        
        # Load existing mission tracking settings
        await self.load_tracking_settings()
        
        # Start tracking tasks
        await self.bot.wait_until_ready()
        await self.start_tracking_tasks()
    
    # This function is needed to expose the commands to the bot
    def get_commands(self):
        """Return all commands this cog provides"""
        return [mission_group]
        
    async def start_tracking_tasks(self):
        """Start mission tracking tasks for all enabled guilds"""
        if not self.db:
            logger.error("Database not available for starting mission tracking tasks")
            return
            
        try:
            # Start tracking for each enabled guild
            for guild_id, enabled in self.tracking_enabled.items():
                if not enabled:
                    continue
                    
                # Skip if task already exists
                if guild_id in self.tracking_tasks and not self.tracking_tasks[guild_id].done():
                    continue
                    
                # Get the channel ID
                channel_id = self.mission_channels.get(guild_id)
                if not channel_id:
                    continue
                    
                # Start a new tracking task
                task = self.bot.loop.create_task(
                    self.track_mission_events(guild_id, channel_id),
                    name=f"mission_tracker_{guild_id}"
                )
                self.tracking_tasks[guild_id] = task
                
            logger.info(f"Started mission tracking for {len(self.tracking_tasks)} guilds")
        except Exception as e:
            logger.error(f"Error starting mission tracking tasks: {e}")
    
    async def load_tracking_settings(self):
        """Load mission tracking settings from the database"""
        if not self.db:
            logger.error("Database not available for loading mission settings")
            return
            
        try:
            # Get all guild configs
            guild_configs = await self.db.get_collection("guild_configs")
            cursor = guild_configs.find({})
            configs = await cursor.to_list(None)
            
            # Process each config
            for config in configs:
                guild_id = config.get("guild_id")
                if not guild_id:
                    continue
                    
                # Get mission settings
                mission_channel = config.get("mission_channel")
                mission_enabled = config.get("mission_notifications", False)
                
                # Store in memory for quick access
                if mission_enabled is not None:
                    self.tracking_enabled[guild_id] = mission_enabled
                    
                if mission_channel:
                    self.mission_channels[guild_id] = mission_channel
                    
            logger.info(f"Loaded mission settings for {len(self.tracking_enabled)} guilds")
        except Exception as e:
            logger.error(f"Error loading mission settings: {e}")
    
    @mission_group.command(
        name="channel",
        description="Set a channel for mission notifications", 
        contexts=[discord.InteractionContextType.guild], 
        integration_types=[discord.IntegrationType.guild_install]
    )
    async def mission_channel(
        self, 
        ctx,
        channel: discord.Option(discord.TextChannel, "Channel to send notifications to", required=True)
    ):
        """Set the channel for mission and event notifications"""
        await ctx.defer()
        
        if not self.db:
            await ctx.respond("❌ Database not initialized")
            return
        
        try:
            guild_id = str(ctx.guild.id) if ctx.guild else None
            if not guild_id:
                await ctx.respond("❌ This command must be run in a server")
                return
                
            # Verify that the bot has permissions to send messages in the channel
            bot_member = ctx.guild.get_member(self.bot.user.id)
            if not channel.permissions_for(bot_member).send_messages:
                await ctx.respond(f"❌ I don't have permission to send messages in {channel.mention}")
                return
                
            # Update the guild config
            guild_configs = await self.db.get_collection("guild_configs")
            result = await guild_configs.update_one(
                {"guild_id": guild_id},
                {"$set": {"mission_channel": str(channel.id)}},
                upsert=True
            )
            
            # Update the in-memory cache
            self.mission_channels[guild_id] = str(channel.id)
            
            # Enable notifications if they weren't already
            if guild_id not in self.tracking_enabled or not self.tracking_enabled[guild_id]:
                await guild_configs.update_one(
                    {"guild_id": guild_id},
                    {"$set": {"mission_notifications": True}},
                    upsert=True
                )
                self.tracking_enabled[guild_id] = True
            
            # Create success embed
            embed = discord.Embed(
                title="✅ Mission Channel Set",
                description=f"Mission notifications will be sent to {channel.mention}",
                color=discord.Color.green()
            )
            
            # Add note about enabling if needed
            if result.upserted_id:
                embed.add_field(
                    name="Notifications Enabled",
                    value="Mission notifications have been automatically enabled",
                    inline=False
                )
            
            # Add command help
            embed.add_field(
                name="📝 Related Commands",
                value="`/missions toggle` - Enable/disable notifications\n"
                      "`/missions status` - Check notification settings",
                inline=False
            )
            
            await ctx.respond(embed=embed)
        except Exception as e:
            logger.error(f"Error checking mission status: {e}")
            await ctx.respond(f"❌ Error checking mission status: {str(e)}", ephemeral=True)
            
    @mission_group.command(
        name="toggle",
        description="Enable or disable mission notifications"
    )
    async def mission_toggle(
        self,
        ctx,
        enabled: discord.Option(bool, "Enable or disable notifications", required=True)
    ):
        """Enable or disable mission notifications"""
        await ctx.defer()
        
        if not self.db:
            await ctx.respond("❌ Database not initialized")
            return
        
        try:
            guild_id = str(ctx.guild.id) if ctx.guild else None
            if not guild_id:
                await ctx.respond("❌ This command must be run in a server")
                return
                
            # Check if mission channel is set
            if enabled and guild_id not in self.mission_channels:
                embed = discord.Embed(
                    title="⚠️ No Mission Channel Set",
                    description="You need to set a mission channel first",
                    color=discord.Color.orange()
                )
                
                embed.add_field(
                    name="Set a Channel",
                    value="Use `/missions channel #channel` to set a notification channel first",
                    inline=False
                )
                
                await ctx.respond(embed=embed)
                return
                
            # Update the guild config
            guild_configs = await self.db.get_collection("guild_configs")
            await guild_configs.update_one(
                {"guild_id": guild_id},
                {"$set": {"mission_notifications": enabled}},
                upsert=True
            )
            
            # Update the in-memory cache
            self.tracking_enabled[guild_id] = enabled
            
            # Create response embed
            if enabled:
                embed = discord.Embed(
                    title="✅ Mission Notifications Enabled",
                    description="You will now receive notifications for missions and events",
                    color=discord.Color.green()
                )
                
                # Add channel information if available
                if guild_id in self.mission_channels:
                    channel_id = self.mission_channels[guild_id]
                    try:
                        channel = ctx.guild.get_channel(int(channel_id))
                        if channel:
                            embed.add_field(
                                name="Notification Channel",
                                value=f"Notifications will be sent to {channel.mention}",
                                inline=False
                            )
                    except:
                        pass
            else:
                embed = discord.Embed(
                    title="❌ Mission Notifications Disabled",
                    description="You will no longer receive notifications for missions and events",
                    color=discord.Color.red()
                )
            
            await ctx.respond(embed=embed)
        except Exception as e:
            logger.error(f"Error toggling mission notifications: {e}")
            await ctx.respond(f"❌ Error toggling mission notifications: {str(e)}", ephemeral=True)
            
    @mission_group.command(
        name="status",
        description="Check mission notification settings"
    )
    async def mission_status(self, ctx):
        """Check the current mission notification settings"""
        await ctx.defer()
        
        if not self.db:
            await ctx.respond("❌ Database not initialized")
            return
        
        try:
            guild_id = str(ctx.guild.id) if ctx.guild else None
            if not guild_id:
                await ctx.respond("❌ This command must be run in a server")
                return
                
            # Check if premium feature
            is_premium = await check_feature_access(self.db, guild_id, "mission_alerts")
                
            # Get current settings
            enabled = self.tracking_enabled.get(guild_id, False)
            channel_id = self.mission_channels.get(guild_id)
            
            # Create status embed
            if enabled:
                embed = discord.Embed(
                    title="Mission Notification Status",
                    description="✅ Notifications are **enabled**",
                    color=discord.Color.green()
                )
            else:
                embed = discord.Embed(
                    title="Mission Notification Status",
                    description="❌ Notifications are **disabled**",
                    color=discord.Color.red()
                )
            
            # Add channel information if available
            if channel_id:
                try:
                    channel = ctx.guild.get_channel(int(channel_id))
                    if channel:
                        embed.add_field(
                            name="Notification Channel",
                            value=f"Notifications will be sent to {channel.mention}",
                            inline=False
                        )
                    else:
                        embed.add_field(
                            name="⚠️ Channel Not Found",
                            value="The configured channel no longer exists. Please set a new one.",
                            inline=False
                        )
                except:
                    embed.add_field(
                        name="⚠️ Channel Error",
                        value="Could not verify the channel. Please set a new one.",
                        inline=False
                    )
            else:
                embed.add_field(
                    name="No Channel Set",
                    value="Use `/missions channel #channel` to set a notification channel",
                    inline=False
                )
            
            # Get recent missions if any
            if enabled and channel_id:
                try:
                    # Get servers for this guild
                    servers = await get_guild_servers(self.db, guild_id)
                    server_ids = [str(server["_id"]) for server in servers]
                    
                    if server_ids:
                        # Get recent mission events
                        events_collection = await self.db.get_collection("server_events")
                        recent_query = {
                            "server_id": {"$in": server_ids},
                            "timestamp": {"$gte": datetime.utcnow() - timedelta(hours=24)}
                        }
                        recent_cursor = events_collection.find(recent_query).sort("timestamp", -1).limit(5)
                        recent_events = await recent_cursor.to_list(None)
                        
                        if recent_events:
                            events_text = []
                            for event in recent_events:
                                server_id = event.get("server_id")
                                server_name = "Unknown"
                                
                                # Find server name
                                for server in servers:
                                    if str(server["_id"]) == server_id:
                                        server_name = server.get("name", "Unknown")
                                        break
                                
                                # Format timestamp
                                timestamp = event.get("timestamp")
                                if timestamp and isinstance(timestamp, datetime):
                                    time_str = timestamp.strftime("%H:%M:%S")
                                else:
                                    time_str = "Unknown time"
                                
                                event_type = event.get("event_type", "event").capitalize()
                                events_text.append(f"• {event_type} on {server_name} at {time_str}")
                            
                            # Add to embed
                            embed.add_field(
                                name="Recent Events (24h)",
                                value="\n".join(events_text)[:1024],  # Limit to 1024 chars
                                inline=False
                            )
                except Exception as events_error:
                    logger.error(f"Error getting recent events: {events_error}")
                    # Continue without recent events
            
            # Add premium status
            if not is_premium:
                embed.add_field(
                    name="💎 Premium Feature",
                    value="Limited mission alerts are available on the free tier. " 
                          "Upgrade to Warlord tier for more advanced mission tracking.",
                    inline=False
                )
            
            await ctx.respond(embed=embed)
        except Exception as e:
            logger.error(f"Error checking mission status: {e}")
            await ctx.respond(f"❌ Error checking mission status: {str(e)}", ephemeral=True)
            
    async def track_mission_events(self, guild_id, channel_id):
        """
        Background task to track mission events for a guild and send notifications
        
        Args:
            guild_id: Guild ID as string
            channel_id: Discord channel ID to send notifications to
        """
        # Set task name for identification
        task_name = f"mission_tracker_{guild_id}"
        asyncio.current_task().set_name(task_name)
        
        logger.info(f"Started mission tracker for guild {guild_id} to channel {channel_id}")
        
        # Track the last event we've seen
        last_event_time = datetime.utcnow() - timedelta(minutes=5)  # Start with events from last 5 minutes
        
        try:
            while True:
                try:
                    # Check if tracking is still enabled for this guild
                    if guild_id not in self.tracking_enabled or not self.tracking_enabled[guild_id]:
                        logger.debug(f"Mission tracking disabled for guild {guild_id}, stopping tracker")
                        return
                        
                    # Check if channel ID has changed
                    current_channel_id = self.mission_channels.get(guild_id)
                    if current_channel_id != channel_id:
                        if current_channel_id:
                            # Channel changed, restart with new channel
                            logger.debug(f"Mission channel changed for guild {guild_id}, restarting tracker")
                            self.bot.loop.create_task(
                                self.track_mission_events(guild_id, current_channel_id),
                                name=task_name
                            )
                            return
                        else:
                            # Channel removed, stop tracking
                            logger.debug(f"Mission channel removed for guild {guild_id}, stopping tracker")
                            return
                    
                    # Get the channel
                    channel = self.bot.get_channel(int(channel_id))
                    if not channel:
                        logger.warning(f"Could not find channel {channel_id} for guild {guild_id}")
                        await asyncio.sleep(60)  # Longer sleep on error
                        continue
                    
                    # Get servers for this guild
                    servers = await get_guild_servers(self.db, guild_id)
                    
                    if not servers:
                        logger.debug(f"No servers found for guild {guild_id}")
                        await asyncio.sleep(60)
                        continue
                        
                    server_ids = [str(server["_id"]) for server in servers]
                    
                    # Query for new mission events
                    collection = await self.db.get_collection("server_events")
                    events_query = {
                        "server_id": {"$in": server_ids},
                        "timestamp": {"$gt": last_event_time},
                        "event_type": {"$in": ["mission", "mission_complete", "airdrop", "helicrash", "trader"]}
                    }
                    
                    cursor = collection.find(events_query).sort("timestamp", 1)
                    events = await cursor.to_list(None)
                    
                    # Process each new event
                    for event in events:
                        # Update the last event time
                        event_time = event.get("timestamp")
                        if event_time and event_time > last_event_time:
                            last_event_time = event_time
                            
                        # Get server info
                        server_id = event.get("server_id")
                        server = next((s for s in servers if str(s["_id"]) == server_id), None)
                        
                        if not server:
                            continue
                            
                        server_name = server.get("name", "Unknown Server")
                        
                        # Check if this is a mission event
                        event_type = event.get("event_type")
                        
                        # Create appropriate embed based on event type
                        if event_type in ["mission", "mission_complete"]:
                            # This is a mission event
                            embed = create_mission_embed(
                                event, 
                                active_status=(event_type == "mission"),
                                display_location=True
                            )
                        else:
                            # This is another type of event (airdrop, helicrash, etc.)
                            title = event_type.replace("_", " ").title()
                            description = f"New {title} event on {server_name}"
                            
                            embed = discord.Embed(
                                title=f"{title} Event",
                                description=description,
                                color=discord.Color.gold(),
                                timestamp=event_time
                            )
                            
                            # Add location if available
                            location = event.get("location")
                            if location:
                                embed.add_field(
                                    name="Location",
                                    value=f"Coordinates: {location.get('x')}, {location.get('y')}",
                                    inline=True
                                )
                                
                            embed.add_field(
                                name="Server",
                                value=server_name,
                                inline=True
                            )
                            
                            # Add footer
                            embed.set_footer(text=f"Event ID: {event.get('_id')}")
                        
                        # Send the embed to the channel
                        await channel.send(embed=embed)
                        
                    # Log how many events we processed
                    if events:
                        logger.debug(f"Processed {len(events)} new mission events for guild {guild_id}")
                    
                    # Sleep before next check
                    await asyncio.sleep(30)
                    
                except Exception as e:
                    logger.error(f"Error in mission tracker for guild {guild_id}: {e}")
                    await asyncio.sleep(60)  # Longer sleep on error
                    
        except asyncio.CancelledError:
            logger.info(f"Mission tracker for guild {guild_id} was cancelled")
            return
        except Exception as e:
            logger.error(f"Fatal error in mission tracker for guild {guild_id}: {e}")
            
    @mission_group.command(
        name="test",
        description="Send a test mission notification"
    )
    async def mission_test(
        self,
        ctx,
        event_type: discord.Option(
            str,
            "Type of event to test",
            choices=["mission", "airdrop", "helicrash", "trader"],
            required=True
        )
    ):
        """Send a test mission notification to verify setup"""
        await ctx.defer()
        
        if not self.db:
            await ctx.respond("❌ Database not initialized")
            return
        
        try:
            guild_id = str(ctx.guild.id) if ctx.guild else None
            if not guild_id:
                await ctx.respond("❌ This command must be run in a server")
                return
                
            # Check if notifications are enabled
            enabled = self.tracking_enabled.get(guild_id, False)
            if not enabled:
                await ctx.respond("❌ Mission notifications are disabled. Enable them with `/missions toggle true`")
                return
                
            # Check if channel is set
            channel_id = self.mission_channels.get(guild_id)
            if not channel_id:
                await ctx.respond("❌ No mission channel set. Set one with `/missions channel #channel`")
                return
                
            # Get the channel
            try:
                channel = ctx.guild.get_channel(int(channel_id))
                if not channel:
                    await ctx.respond(f"❌ Could not find channel with ID {channel_id}")
                    return
            except:
                await ctx.respond("❌ Invalid channel ID. Please reset the channel with `/missions channel #channel`")
                return
                
            # Create test event
            event_details = {}
            server_name = "Test Server"
            
            if event_type == "mission":
                event_details = {
                    "description": "A group of AI mercenaries has set up a base camp",
                    "location": "Military Base",
                    "difficulty": "Hard",
                    "rewards": "High-tier weapons, ammunition, and supplies",
                    "duration": "30 minutes"
                }
            elif event_type == "airdrop":
                event_details = {
                    "description": "Supply crate incoming - contains valuable loot",
                    "location": "Forest Clearing",
                    "rewards": "Medical supplies, food, and ammunition"
                }
            elif event_type == "helicrash":
                event_details = {
                    "description": "A helicopter has crashed in the zone",
                    "location": "Northern Hills",
                    "rewards": "Military equipment and rare items"
                }
            elif event_type == "trader":
                event_details = {
                    "description": "A traveling trader has set up shop",
                    "location": "Urban Area",
                    "duration": "60 minutes",
                    "rewards": "Special items available for trade"
                }
            
            # Create test mission event
            test_event = {
                "timestamp": datetime.utcnow(),
                "event_type": event_type,
                "server_id": "test_server_id",
                "details": event_details
            }
            
            # Create the mission embed
            embed = await create_mission_embed(test_event, server_name)
            
            # Add test notification
            embed.add_field(
                name="Test Notification",
                value="This is a test notification sent by an admin. " 
                      "Verify that the formatting looks correct and is in the right channel.",
                inline=False
            )
            
            # Set footer with admin info
            embed.set_footer(text=f"Test requested by {ctx.author.name} | Actual events will not show this footer")
            
            # Send the test notification
            await channel.send(embed=embed)
            
            # Send confirmation to the command user
            confirm_embed = discord.Embed(
                title="✅ Test Notification Sent",
                description=f"Test {event_type} notification sent to {channel.mention}",
                color=discord.Color.green()
            )
            
            await ctx.respond(embed=confirm_embed)
            
        except Exception as e:
            logger.error(f"Error sending test notification: {e}")
            await ctx.respond(f"❌ Error sending test notification: {e}")
    
    async def notify_event(self, event, server):
        """
        Send a notification for a server event
        
        Args:
            event: ServerEvent document
            server: Server document
        """
        if not self.db:
            logger.error("Database not available for event notification")
            return
            
        try:
            guild_id = server.get("guild_id")
            if not guild_id:
                logger.error(f"Server {server.get('name')} has no guild_id")
                return
                
            # Check if notifications are enabled for this guild
            enabled = self.tracking_enabled.get(guild_id, False)
            if not enabled:
                return
                
            # Check if channel is set
            channel_id = self.mission_channels.get(guild_id)
            if not channel_id:
                return
                
            # Get the channel
            try:
                guild = self.bot.get_guild(int(guild_id))
                if not guild:
                    logger.error(f"Could not find guild with ID {guild_id}")
                    return
                    
                channel = guild.get_channel(int(channel_id))
                if not channel:
                    logger.error(f"Could not find channel with ID {channel_id}")
                    return
            except Exception as channel_err:
                logger.error(f"Error getting notification channel: {channel_err}")
                return
                
            # Create the mission embed
            embed = await create_mission_embed(event, server.get("name", "Unknown Server"))
            
            # Send the notification
            await channel.send(embed=embed)
            logger.info(f"Sent {event.get('event_type')} notification to guild {guild_id}")
            
        except Exception as e:
            logger.error(f"Error sending event notification: {e}")
    
    # Management methods
    async def update_tracking_settings(self, guild_id, enabled=None, channel_id=None):
        """Update mission tracking settings for a guild"""
        if not self.db:
            logger.error("Database not available for updating tracking settings")
            return False
            
        try:
            update_data = {}
            
            if enabled is not None:
                update_data["mission_notifications"] = enabled
                self.tracking_enabled[guild_id] = enabled
                
            if channel_id is not None:
                update_data["mission_channel"] = channel_id
                self.mission_channels[guild_id] = channel_id
                
            if update_data:
                guild_configs = await self.db.get_collection("guild_configs")
                await guild_configs.update_one(
                    {"guild_id": guild_id},
                    {"$set": update_data},
                    upsert=True
                )
                
                return True
                
        except Exception as e:
            logger.error(f"Error updating tracking settings: {e}")
            
        return False