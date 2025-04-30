import discord
from discord.ext import commands
import logging
import datetime
import traceback
from typing import Dict, List, Optional, Union

from database.models import KillfeedSettings, Server
from utils.embeds import create_success_embed, create_error_embed, create_warning_embed

logger = logging.getLogger('deadside_bot.cogs.killfeed')

# Create killfeed command group
killfeed_group = discord.SlashCommandGroup(
    name="killfeed",
    description="Commands for managing killfeed notifications"
)

class KillfeedCommands(commands.Cog):
    """Commands for managing killfeed notifications"""
    
    def __init__(self, bot):
        self.bot = bot
        self.db = getattr(bot, 'db', None)  # Get db from bot if available
        self.killfeed_settings = {}  # Cache settings by guild_id
        
    async def cog_load(self):
        """Called when the cog is loaded"""
        logger.info("KillfeedCommands cog loaded")
        # Ensure db is set before attempting any database operations
        if not self.db and hasattr(self.bot, 'db'):
            self.db = self.bot.db
            logger.debug("Set database for KillfeedCommands cog from bot")
            
        # Load settings
        await self.load_killfeed_settings()
        
    async def load_killfeed_settings(self):
        """Load killfeed settings from the database"""
        if not self.db:
            logger.warning("Cannot load killfeed settings: database not initialized")
            return
            
        try:
            # Load all killfeed settings
            killfeed_collection = await self.db.get_collection("killfeed_settings")
            cursor = killfeed_collection.find({})
            
            settings = {}
            async for doc in cursor:
                if "guild_id" in doc:
                    guild_id = str(doc["guild_id"])
                    settings[guild_id] = doc
                    
            self.killfeed_settings = settings
            logger.info(f"Loaded killfeed settings for {len(settings)} guilds")
        except Exception as e:
            logger.error(f"Error loading killfeed settings: {e}")
            logger.error(traceback.format_exc())
    
    @killfeed_group.command(
        name="channel",
        description="Set the channel for killfeed notifications",
        contexts=[discord.InteractionContextType.guild], 
        integration_types=[discord.IntegrationType.guild_install]
    )
    @commands.has_permissions(manage_guild=True)
    async def killfeed_channel(
        self, 
        ctx,
        channel: discord.Option(discord.TextChannel, "Channel to send notifications to", required=True)
    ):
        """Set the channel for killfeed notifications"""
        try:
            if not self.db:
                return await ctx.respond("⚠️ Database connection not available", ephemeral=True)
                
            # Update the killfeed settings
            await self.update_killfeed_settings(ctx.guild.id, channel_id=channel.id)
            
            embed = create_success_embed(
                "Killfeed Channel Set",
                f"Killfeed notifications will now be sent to {channel.mention}"
            )
            await ctx.respond(embed=embed)
            
        except Exception as e:
            logger.error(f"Error setting killfeed channel: {e}")
            logger.error(traceback.format_exc())
            await ctx.respond(f"❌ Error setting killfeed channel: {str(e)}", ephemeral=True)
    
    @killfeed_group.command(
        name="toggle",
        description="Enable or disable killfeed notifications",
        contexts=[discord.InteractionContextType.guild], 
        integration_types=[discord.IntegrationType.guild_install]
    )
    @commands.has_permissions(manage_guild=True)
    async def killfeed_toggle(
        self,
        ctx,
        enabled: discord.Option(bool, "Enable or disable notifications", required=True)
    ):
        """Enable or disable killfeed notifications"""
        try:
            if not self.db:
                return await ctx.respond("⚠️ Database connection not available", ephemeral=True)
                
            # Update the killfeed settings
            await self.update_killfeed_settings(ctx.guild.id, enabled=enabled)
            
            if enabled:
                embed = create_success_embed(
                    "Killfeed Notifications Enabled",
                    "You will now receive notifications for kills"
                )
            else:
                embed = discord.Embed(
                    title="❌ Killfeed Notifications Disabled",
                    description="You will no longer receive notifications for kills",
                    color=discord.Color.red()
                )
            await ctx.respond(embed=embed)
            
        except Exception as e:
            logger.error(f"Error toggling killfeed: {e}")
            logger.error(traceback.format_exc())
            await ctx.respond(f"❌ Error toggling killfeed notifications: {str(e)}", ephemeral=True)
            
    @killfeed_group.command(
        name="filter",
        description="Customize which kills to show in the killfeed",
        contexts=[discord.InteractionContextType.guild], 
        integration_types=[discord.IntegrationType.guild_install]
    )
    @commands.has_permissions(manage_guild=True)
    async def killfeed_filter(
        self,
        ctx,
        show_ai_kills: discord.Option(bool, "Show kills against AI", default=None),
        show_ai_deaths: discord.Option(bool, "Show deaths by AI", default=None),
        show_vehicle_kills: discord.Option(bool, "Show kills with vehicles", default=None),
        show_suicides: discord.Option(bool, "Show suicides", default=None),
        min_distance: discord.Option(int, "Minimum kill distance to show (meters)", default=None),
        show_headshots_only: discord.Option(bool, "Only show headshot kills", default=None)
    ):
        """Customize which kills to show in the killfeed"""
        try:
            if not self.db:
                return await ctx.respond("⚠️ Database connection not available", ephemeral=True)
                
            # Get current filters
            guild_id = ctx.guild.id
            settings = await KillfeedSettings.get_for_guild(self.db, guild_id)
            
            # If no settings yet, create default filters
            current_filters = settings.get("filters", {}) if settings else {}
            
            # Build the new filters by merging any provided values with current values
            filters = current_filters.copy()
            
            if show_ai_kills is not None:
                filters["show_ai_kills"] = show_ai_kills
            if show_ai_deaths is not None:
                filters["show_ai_deaths"] = show_ai_deaths
            if show_vehicle_kills is not None:
                filters["show_vehicle_kills"] = show_vehicle_kills
            if show_suicides is not None:
                filters["show_suicides"] = show_suicides
            if min_distance is not None:
                filters["min_distance"] = min_distance
            if show_headshots_only is not None:
                filters["show_headshots_only"] = show_headshots_only
                
            # Update the database
            await self.update_killfeed_settings(guild_id, filters=filters)
            
            # Create a nice embed to show the current filters
            embed = create_success_embed(
                "Killfeed Filters Updated",
                "The following filters have been applied:"
            )
            
            for key, value in filters.items():
                # Convert snake_case to Title Case With Spaces
                display_name = key.replace("_", " ").title()
                embed.add_field(
                    name=display_name,
                    value=str(value),
                    inline=True
                )
                
            await ctx.respond(embed=embed)
            
        except Exception as e:
            logger.error(f"Error setting killfeed filters: {e}")
            logger.error(traceback.format_exc())
            await ctx.respond(f"❌ Error setting killfeed filters: {str(e)}", ephemeral=True)
    
    @killfeed_group.command(
        name="status",
        description="Check the current killfeed notification settings",
        contexts=[discord.InteractionContextType.guild], 
        integration_types=[discord.IntegrationType.guild_install]
    )
    async def killfeed_status(self, ctx):
        """Check the current killfeed notification settings"""
        await ctx.defer()
        try:
            if not self.db:
                return await ctx.respond("⚠️ Database connection not available", ephemeral=True)
                
            # Get settings for this guild
            guild_id = ctx.guild.id
            settings = await KillfeedSettings.get_for_guild(self.db, guild_id)
            
            if not settings:
                return await ctx.respond("No killfeed settings found. Use `/killfeed channel` to set up notifications.", ephemeral=True)
                
            enabled = settings.get("enabled", False)
            channel_id = settings.get("channel_id")
            filters = settings.get("filters", {})
            
            # Create a nice embed with the current settings
            if enabled:
                embed = discord.Embed(
                    title="Killfeed Notification Settings",
                    color=discord.Color.green()
                )
                embed.add_field(
                    name="Status",
                    value="✅ Enabled",
                    inline=False
                )
                
                if channel_id:
                    channel = ctx.guild.get_channel(int(channel_id))
                    channel_value = channel.mention if channel else f"Unknown Channel (ID: {channel_id})"
                    embed.add_field(
                        name="Channel",
                        value=channel_value,
                        inline=False
                    )
                
                if filters:
                    filter_text = "\n".join([f"**{k.replace('_', ' ').title()}**: {v}" for k, v in filters.items()])
                    embed.add_field(
                        name="Filters",
                        value=filter_text,
                        inline=False
                    )
            else:
                embed = discord.Embed(
                    title="Killfeed Notification Settings",
                    color=discord.Color.red()
                )
                embed.add_field(
                    name="Status",
                    value="❌ Disabled",
                    inline=False
                )
                embed.add_field(
                    name="⚠️ Notifications Disabled",
                    value="Killfeed notifications are currently disabled. Use `/killfeed toggle true` to enable them.",
                    inline=False
                )
                
            await ctx.respond(embed=embed)
            
        except Exception as e:
            logger.error(f"Error retrieving killfeed status: {e}")
            logger.error(traceback.format_exc())
            await ctx.respond(f"❌ Error retrieving killfeed status: {str(e)}", ephemeral=True)
    
    @killfeed_group.command(
        name="highlights",
        description="Configure highlighted kills for special notification",
        contexts=[discord.InteractionContextType.guild], 
        integration_types=[discord.IntegrationType.guild_install]
    )
    @commands.has_permissions(manage_guild=True)
    async def killfeed_highlights(
        self,
        ctx,
        highlight_distance: discord.Option(int, "Highlight kills above this distance (meters)", default=None),
        highlight_streaks: discord.Option(bool, "Highlight kill streaks", default=None),
        streak_threshold: discord.Option(int, "Number of kills to be considered a streak", default=None)
    ):
        """Configure highlighted kills for special notification"""
        try:
            if not self.db:
                return await ctx.respond("⚠️ Database connection not available", ephemeral=True)
                
            # Get current filters
            guild_id = ctx.guild.id
            settings = await KillfeedSettings.get_for_guild(self.db, guild_id)
            
            # If no settings yet, create default filters
            current_filters = settings.get("filters", {}) if settings else {}
            
            # Build the new filters by merging any provided values with current values
            filters = current_filters.copy()
            
            # Update highlight related filters
            if highlight_distance is not None:
                filters["highlight_distance"] = highlight_distance
            if highlight_streaks is not None:
                filters["highlight_streaks"] = highlight_streaks
            if streak_threshold is not None:
                filters["streak_threshold"] = streak_threshold
                
            # Update the database
            await self.update_killfeed_settings(guild_id, filters=filters)
            
            # Create a nice embed to show the highlight settings
            embed = create_success_embed(
                "Killfeed Highlight Settings Updated",
                "These kills will receive special highlighting:"
            )
            
            # Just show the highlight-related settings
            highlight_keys = ["highlight_distance", "highlight_streaks", "streak_threshold"]
            for key in highlight_keys:
                if key in filters:
                    # Convert snake_case to Title Case With Spaces
                    display_name = key.replace("_", " ").title()
                    embed.add_field(
                        name=display_name,
                        value=str(filters[key]),
                        inline=True
                    )
                
            await ctx.respond(embed=embed)
            
        except Exception as e:
            logger.error(f"Error setting highlight filters: {e}")
            logger.error(traceback.format_exc())
            await ctx.respond(f"❌ Error setting highlight filters: {str(e)}", ephemeral=True)
            
    async def should_send_kill_notification(self, kill, server):
        """
        Check if a kill should be sent as a notification based on filters
        
        Args:
            kill: Kill document
            server: Server document
            
        Returns:
            bool: True if the kill should be sent, False otherwise
        """
        try:
            # Always need a guild_id to check filters
            guild_id = server.get("guild_id")
            if not guild_id:
                logger.warning(f"No guild_id found in server document: {server.get('_id')}")
                return False
                
            # Get killfeed settings for this guild
            settings = await KillfeedSettings.get_for_guild(self.db, guild_id)
            
            # If no settings or disabled, don't send notification
            if not settings or not settings.get("enabled", False):
                return False
                
            # Get filters
            filters = settings.get("filters", {})
            
            # Apply filters to kill
            # Is this an AI kill?
            killer_is_ai = kill.get("killer_is_ai", False)
            victim_is_ai = kill.get("victim_is_ai", False)
            
            # Check AI kill filters
            if killer_is_ai and not filters.get("show_ai_kills", True):
                return False
                
            if victim_is_ai and not filters.get("show_ai_deaths", True):
                return False
                
            # Is this a vehicle kill?
            is_vehicle_kill = "vehicle" in kill.get("weapon_name", "").lower()
            if is_vehicle_kill and not filters.get("show_vehicle_kills", True):
                return False
                
            # Is this a suicide?
            is_suicide = kill.get("killer_name") == kill.get("victim_name")
            if is_suicide and not filters.get("show_suicides", False):
                return False
                
            # Check distance filter
            if "min_distance" in filters:
                distance = kill.get("distance", 0)
                if distance < filters["min_distance"]:
                    return False
                    
            # Check headshots only filter
            if filters.get("show_headshots_only", False):
                is_headshot = kill.get("is_headshot", False)
                if not is_headshot:
                    return False
                    
            # If we get here, the kill passed all filters
            return True
            
        except Exception as e:
            logger.error(f"Error applying killfeed filters: {e}")
            logger.error(traceback.format_exc())
            return False
            
    async def format_kill_notification(self, kill, server, guild_id):
        """
        Format a kill notification message
        
        Args:
            kill: Kill document
            server: Server document
            guild_id: Discord guild ID
            
        Returns:
            dict: Formatted message with content, embed, etc.
        """
        try:
            # Get killfeed settings for highlights
            settings = await KillfeedSettings.get_for_guild(self.db, guild_id)
            filters = settings.get("filters", {}) if settings else {}
            
            # Get relevant kill details
            killer_name = kill.get("killer_name", "Unknown")
            victim_name = kill.get("victim_name", "Unknown")
            weapon_name = kill.get("weapon_name", "Unknown")
            distance = kill.get("distance", 0)
            is_headshot = kill.get("is_headshot", False)
            killer_is_ai = kill.get("killer_is_ai", False)
            victim_is_ai = kill.get("victim_is_ai", False)
            
            # Determine highlight status
            is_highlighted = False
            highlight_reason = None
            
            # Distance highlight
            if "highlight_distance" in filters and distance >= filters["highlight_distance"]:
                is_highlighted = True
                highlight_reason = f"Long distance kill ({distance}m)"
                
            # TODO: Implement streak highlighting
            
            # Create embed color based on type of kill
            if is_highlighted:
                color = discord.Color.gold()  # Highlighted kills get gold
            elif is_headshot:
                color = discord.Color.red()  # Headshots get red
            else:
                color = discord.Color.blue()  # Regular kills get blue
                
            # Create the embed
            embed = discord.Embed(
                title="Killfeed Update",
                color=color,
                timestamp=datetime.datetime.now()
            )
            
            # Add server name to footer
            server_name = server.get("name", "Unknown Server")
            embed.set_footer(text=f"{server_name}")
            
            # Determine kill description
            if killer_is_ai and victim_is_ai:
                description = f"AI **{killer_name}** killed AI **{victim_name}**"
            elif killer_is_ai:
                description = f"AI **{killer_name}** killed **{victim_name}**"
            elif victim_is_ai:
                description = f"**{killer_name}** killed AI **{victim_name}**"
            else:
                description = f"**{killer_name}** killed **{victim_name}**"
                
            # Add weapon
            description += f" with **{weapon_name}**"
            
            # Add distance if significant
            if distance > 0:
                description += f" from **{distance}m**"
                
            # Add headshot indicator
            if is_headshot:
                description += " **(HEADSHOT)**"
                
            embed.description = description
            
            # Add highlight reason if any
            if highlight_reason:
                embed.add_field(
                    name="⭐ Highlight",
                    value=highlight_reason,
                    inline=False
                )
                
            return {
                "embed": embed,
                "is_highlighted": is_highlighted
            }
            
        except Exception as e:
            logger.error(f"Error formatting kill notification: {e}")
            logger.error(traceback.format_exc())
            return {
                "embed": discord.Embed(
                    title="Kill Notification Error",
                    description=f"Error formatting kill notification: {str(e)}",
                    color=discord.Color.red()
                ),
                "is_highlighted": False
            }
            
    async def send_kill_notification(self, kill, server):
        """
        Send a kill notification to the appropriate channel
        
        Args:
            kill: Kill document
            server: Server document
        """
        try:
            # Check if this kill should be sent based on filters
            should_send = await self.should_send_kill_notification(kill, server)
            if not should_send:
                return
                
            # Get the guild_id from the server
            guild_id = server.get("guild_id")
            if not guild_id:
                logger.warning(f"No guild_id found in server document: {server.get('_id')}")
                return
                
            # Get killfeed settings
            settings = await KillfeedSettings.get_for_guild(self.db, guild_id)
            if not settings:
                logger.debug(f"No killfeed settings found for guild {guild_id}")
                return
                
            # Get the channel ID
            channel_id = settings.get("channel_id")
            if not channel_id:
                logger.debug(f"No channel set for killfeed in guild {guild_id}")
                return
                
            # Format the notification
            notification = await self.format_kill_notification(kill, server, guild_id)
            
            # Get the channel
            channel = self.bot.get_channel(int(channel_id))
            if not channel:
                logger.warning(f"Could not find channel {channel_id} for guild {guild_id}")
                return
                
            # Send the notification
            await channel.send(embed=notification["embed"])
            
            # TODO: If this is a highlighted kill, maybe ping a role or send to a different channel
            
        except Exception as e:
            logger.error(f"Error sending kill notification: {e}")
            logger.error(traceback.format_exc())
    
    async def update_killfeed_settings(self, guild_id, enabled=None, channel_id=None, filters=None):
        """Update killfeed settings for a guild"""
        if not self.db:
            raise Exception("Database connection not available")
            
        # Convert to strings for MongoDB
        guild_id = str(guild_id)
        if channel_id is not None:
            channel_id = str(channel_id)
            
        # Get the existing settings
        killfeed_collection = await self.db.get_collection("killfeed_settings")
        settings = await killfeed_collection.find_one({"guild_id": guild_id})
        
        if not settings:
            # Create new settings document
            settings = {
                "guild_id": guild_id,
                "enabled": False,
                "filters": {}
            }
            
        # Update with any provided values
        if enabled is not None:
            settings["enabled"] = enabled
        if channel_id is not None:
            settings["channel_id"] = channel_id
        if filters is not None:
            settings["filters"] = filters
            
        # Save back to database
        await killfeed_collection.update_one(
            {"guild_id": guild_id},
            {"$set": settings},
            upsert=True
        )
        
        # Update the local cache
        self.killfeed_settings[guild_id] = settings
        
        logger.info(f"Updated killfeed settings for guild {guild_id}")
        logger.debug(f"Settings: {settings}")
        return settings

def setup(bot):
    """Required setup function for cog loading"""
    bot.add_cog(KillfeedCommands(bot))