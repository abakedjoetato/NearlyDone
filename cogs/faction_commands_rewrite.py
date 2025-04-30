"""
Faction Commands Cog

This module contains commands for managing player factions.
It includes functionality for creating, joining, leaving, and managing factions.
"""

import discord
from discord.ext import commands, tasks
import logging
from datetime import datetime
from bson import ObjectId

# Import database models and utilities
from database.models import Faction, Player, Server
from utils.embeds import create_faction_embed
from utils.decorators import premium_tier_required, guild_only
from utils.premium import check_feature_access, get_tier_display_info
from utils.background_tasks import background_task

logger = logging.getLogger('deadside_bot.factions')

# Create a SlashCommandGroup for faction commands
faction_group = discord.SlashCommandGroup(
    name="faction",
    description="Commands for managing player factions",
    default_member_permissions=discord.Permissions(manage_roles=True),
    contexts=[discord.InteractionContextType.guild],
    integration_types=[discord.IntegrationType.guild_install]
)

class FactionCommands(commands.Cog):
    """Commands for managing player factions"""
    
    def __init__(self, bot):
        self.bot = bot
        self.db = getattr(bot, 'db', None)  # Get db from bot if available
    
    async def cog_load(self):
        """Called when the cog is loaded. Safe to use async code here."""
        logger.info("Faction commands cog loaded")
        # Ensure db is set before attempting any database operations
        if not self.db and hasattr(self.bot, 'db'):
            self.db = self.bot.db
    
    # This function is needed to expose the commands to the bot
    def get_commands(self):
        return [faction_group]
    
    @faction_group.command(
        name="create", 
        description="Create a new faction",
        contexts=[discord.InteractionContextType.guild],
        integration_types=[discord.IntegrationType.guild_install]
    )
    @premium_tier_required(tier=1)
    @guild_only()
    async def create_faction(
        self, 
        ctx, 
        name: discord.Option(str, "Name of the faction", required=True),
        abbreviation: discord.Option(str, "Abbreviation (max 3 chars)", required=True)
    ):
        """
        Create a new faction with the given name and abbreviation
        
        This will create a Discord role for the faction and set up the creator as the faction leader.
        """
        # Check if the abbreviation is valid (3 chars or less)
        if len(abbreviation) > 3:
            await ctx.respond("⚠️ Faction abbreviation must be 3 characters or less.", ephemeral=True)
            return
        
        # Check if the user is already in a faction
        db = self.bot.db
        existing_faction = await Faction.get_by_member(db, str(ctx.author.id), ctx.guild.id)
        if existing_faction:
            await ctx.respond(f"⚠️ You are already a member of faction '{existing_faction.name}'. Leave that faction first.", ephemeral=True)
            return
        
        # Check if a faction with this name or abbreviation already exists
        existing_by_name = await Faction.get_by_name(db, name, ctx.guild.id)
        if existing_by_name:
            await ctx.respond(f"⚠️ A faction with the name '{name}' already exists.", ephemeral=True)
            return
        
        existing_by_abbrev = await Faction.get_by_abbreviation(db, abbreviation, ctx.guild.id)
        if existing_by_abbrev:
            await ctx.respond(f"⚠️ A faction with the abbreviation '{abbreviation}' already exists.", ephemeral=True)
            return
        
        # Check if bot has permission to manage roles
        if not ctx.guild.me.guild_permissions.manage_roles:
            await ctx.respond("⚠️ I don't have permission to manage roles in this server. Please grant the 'Manage Roles' permission.", ephemeral=True)
            return
        
        # Create faction role
        try:
            role = await ctx.guild.create_role(
                name=f"Faction: {name}",
                reason=f"Faction created by {ctx.author.display_name}",
                mentionable=True
            )
        except Exception as e:
            await ctx.respond(f"⚠️ Failed to create faction role: {e}", ephemeral=True)
            return
        
        # Create faction in database
        faction = Faction(
            name=name,
            abbreviation=abbreviation,
            guild_id=str(ctx.guild.id),
            leader_id=str(ctx.author.id),
            role_id=str(role.id),
            members=[str(ctx.author.id)],
            created_at=datetime.utcnow()
        )
        
        await faction.save(db)
        
        # Add role to creator
        try:
            await ctx.author.add_roles(role)
        except Exception as e:
            await ctx.respond(f"⚠️ Failed to assign faction role: {e}", ephemeral=True)
            # Clean up if role assignment fails
            await role.delete(reason="Faction creation failed")
            await faction.delete(db)
            return
        
        # Update nickname with faction abbreviation
        try:
            current_name = ctx.author.display_name
            new_nickname = f"{abbreviation} {current_name}"
            if len(new_nickname) > 32:  # Discord nickname limited to 32 chars
                new_nickname = new_nickname[:32]
            await ctx.author.edit(nick=new_nickname)
        except discord.Forbidden:
            await ctx.respond(f"✅ Faction '{name}' created successfully, but I couldn't update your nickname due to missing permissions", ephemeral=True)
        except Exception as e:
            await ctx.respond(f"✅ Faction '{name}' created successfully, but I couldn't update your nickname: {e}", ephemeral=True)
        
        await ctx.respond(f"✅ Faction '{name}' created successfully! You are now the faction leader.")
    
    @faction_group.command(
        name="info", 
        description="View information about a faction",
        contexts=[discord.InteractionContextType.guild],
        integration_types=[discord.IntegrationType.guild_install]
    )
    @premium_tier_required(tier=1)
    @background_task(initial_message="⏳ Gathering faction data...")
    async def faction_info(
        self, 
        ctx, 
        name: discord.Option(str, "Faction name or abbreviation", required=False),
        progress=None
    ):
        """View detailed information about a faction"""
        db = self.bot.db
        
        # Get the faction
        faction = None
        if not name:
            # If no name provided, try to find the user's faction
            faction = await Faction.get_by_member(db, str(ctx.author.id), ctx.guild.id)
            if not faction:
                await ctx.respond("⚠️ You are not in a faction. Specify a faction name or join a faction first.", ephemeral=True)
                return
        else:
            # Try to find the faction by name
            faction = await Faction.get_by_name(db, name, ctx.guild.id)
            if not faction:
                # Try by abbreviation
                faction = await Faction.get_by_abbreviation(db, name, ctx.guild.id)
                if not faction:
                    await ctx.respond(f"⚠️ Faction '{name}' not found.", ephemeral=True)
                    return
        
        # Update progress
        progress['message'] = f"📊 Analyzing faction: {faction.name}"
        progress['percent'] = 25
        
        # Calculate member stats
        member_stats = {
            "kills": 0,
            "deaths": 0,
            "damage_dealt": 0,
            "weapon_counts": {},
            "longest_shot": 0,
            "member_count": len(faction.members)
        }
        
        # Update progress
        progress['message'] = f"🔎 Analyzing {len(faction.members)} members in {faction.name}"
        progress['percent'] = 50
        
        # Get stats for all members
        players_collection = db["players"]
        for i, member_id in enumerate(faction.members):
            # Update per-member progress
            current_member = i + 1
            progress['percent'] = 50 + int((current_member / len(faction.members)) * 45)
            
            try:
                player_stats = await players_collection.find_one({"discord_id": member_id})
                if player_stats:
                    # Add up stats
                    member_stats["kills"] += player_stats.get("kills", 0)
                    member_stats["deaths"] += player_stats.get("deaths", 0)
                    member_stats["damage_dealt"] += player_stats.get("damage_dealt", 0)
                    
                    # Track longest shot
                    longest_shot = player_stats.get("longest_shot", 0)
                    if longest_shot > member_stats["longest_shot"]:
                        member_stats["longest_shot"] = longest_shot
                    
                    # Track weapons used
                    weapons = player_stats.get("weapons_used", {})
                    for weapon, count in weapons.items():
                        if weapon in member_stats["weapon_counts"]:
                            member_stats["weapon_counts"][weapon] += count
                        else:
                            member_stats["weapon_counts"][weapon] = count
            except Exception as e:
                logger.error(f"Error processing member stats: {e}")
                
        # Create and return faction embed
        progress['message'] = f"✅ Creating faction info for {faction.name}"
        progress['percent'] = 100
        
        # Get top weapon used
        top_weapon = None
        if member_stats["weapon_counts"]:
            top_weapon = sorted(member_stats["weapon_counts"].items(), key=lambda x: x[1], reverse=True)[0]
        
        embed = create_faction_embed(faction, ctx.guild, member_stats)
        return embed
    
    @faction_group.command(
        name="list", 
        description="List all factions in this server",
        contexts=[discord.InteractionContextType.guild],
        integration_types=[discord.IntegrationType.guild_install]
    )
    @premium_tier_required(tier=1)
    async def list_factions(self, ctx):
        """List all factions in the current guild"""
        db = self.bot.db
        factions = await Faction.get_all_for_guild(db, ctx.guild.id)
        
        if not factions:
            await ctx.respond("No factions have been created in this server yet.", ephemeral=True)
            return
            
        # Create an embed to display the factions
        embed = discord.Embed(
            title="Factions",
            description="List of all factions in this server",
            color=discord.Color.blue()
        )
        
        for faction in factions:
            # Add field for each faction
            embed.add_field(
                name=f"{faction.name} [{faction.abbreviation}]",
                value=f"Members: {len(faction.members)}\nLeader: <@{faction.leader_id}>",
                inline=True
            )
            
        await ctx.respond(embed=embed)
    
    @faction_group.command(
        name="invite", 
        description="Invite a member to your faction",
        contexts=[discord.InteractionContextType.guild],
        integration_types=[discord.IntegrationType.guild_install]
    )
    @premium_tier_required(tier=1)
    async def invite_member(
        self, 
        ctx, 
        member: discord.Option(discord.Member, "Member to invite", required=True)
    ):
        """
        Invite a member to your faction
        
        Only faction leaders can invite new members.
        """
        db = self.bot.db
        
        # Check if the user is a faction leader
        faction = await Faction.get_by_member(db, str(ctx.author.id), ctx.guild.id)
        if not faction:
            await ctx.respond("⚠️ You are not in a faction.", ephemeral=True)
            return
            
        if faction.leader_id != str(ctx.author.id):
            await ctx.respond("⚠️ Only faction leaders can invite new members.", ephemeral=True)
            return
            
        # Check if the target member is already in a faction
        member_faction = await Faction.get_by_member(db, str(member.id), ctx.guild.id)
        if member_faction:
            await ctx.respond(f"⚠️ {member.display_name} is already a member of the faction '{member_faction.name}'.", ephemeral=True)
            return
            
        # Check if bot has permission to manage roles and nicknames
        if not ctx.guild.me.guild_permissions.manage_roles:
            await ctx.respond("⚠️ I don't have permission to manage roles in this server. Please grant the 'Manage Roles' permission.", ephemeral=True)
            return
            
        if not ctx.guild.me.guild_permissions.manage_nicknames:
            await ctx.respond("⚠️ I don't have permission to manage nicknames in this server. Please grant the 'Manage Nicknames' permission.", ephemeral=True)
            return
            
        # Get the faction role
        faction_role = discord.utils.get(ctx.guild.roles, id=int(faction.role_id)) if faction.role_id else None
        if not faction_role:
            await ctx.respond(f"⚠️ Faction role for '{faction.name}' not found. The role may have been deleted.", ephemeral=True)
            return
            
        # Add the member to the faction
        faction.members.append(str(member.id))
        await faction.update(db)
        
        # Add the role to the member
        try:
            await member.add_roles(faction_role)
        except Exception as e:
            await ctx.respond(f"⚠️ Failed to assign faction role: {e}", ephemeral=True)
            # Remove the member from the faction in the database
            faction.members.remove(str(member.id))
            await faction.update(db)
            return
        
        # Update the member's nickname with the faction abbreviation
        try:
            current_name = member.display_name
            if not current_name.startswith(f"{faction.abbreviation}"):
                new_nickname = f"{faction.abbreviation} {current_name}"
                if len(new_nickname) > 32:  # Discord nickname limited to 32 chars
                    new_nickname = new_nickname[:32]
                await member.edit(nick=new_nickname)
        except discord.Forbidden:
            await ctx.respond(f"✅ {member.mention} has been added to the faction, but I couldn't update their nickname due to missing permissions", ephemeral=True)
        except Exception as e:
            await ctx.respond(f"✅ {member.mention} has been added to the faction, but I couldn't update their nickname: {e}", ephemeral=True)
            
        # Send success message
        await ctx.respond(f"✅ {member.mention} has been added to the faction '{faction.name}'!")
        
        # Send a DM to the invited member
        try:
            await member.send(f"You have been invited to join the faction '{faction.name}' in {ctx.guild.name}!")
        except:
            # Silently ignore if we can't DM the member
            pass
    
    @faction_group.command(
        name="leave", 
        description="Leave your current faction",
        contexts=[discord.InteractionContextType.guild],
        integration_types=[discord.IntegrationType.guild_install]
    )
    @premium_tier_required(tier=1)
    async def leave_faction(self, ctx):
        """Leave your current faction"""
        db = self.bot.db
        
        # Check if the user is in a faction
        faction = await Faction.get_by_member(db, str(ctx.author.id), ctx.guild.id)
        if not faction:
            await ctx.respond("⚠️ You are not in a faction.", ephemeral=True)
            return
            
        # If the user is the faction leader, they can't leave unless they're the only member
        if faction.leader_id == str(ctx.author.id) and len(faction.members) > 1:
            await ctx.respond("⚠️ As the faction leader, you can't leave the faction while there are other members. Either transfer leadership first using `/faction_transfer` or remove all members.", ephemeral=True)
            return
            
        # If they're the last member (and therefore the leader), delete the faction
        if len(faction.members) == 1 and faction.leader_id == str(ctx.author.id):
            # Delete the faction role
            try:
                faction_role = discord.utils.get(ctx.guild.roles, id=int(faction.role_id)) if faction.role_id else None
                if faction_role:
                    await faction_role.delete(reason=f"Faction '{faction.name}' deleted by last member")
            except Exception as e:
                await ctx.respond(f"⚠️ Failed to delete faction role: {e}", ephemeral=True)
                
            # Delete the faction from the database
            await faction.delete(db)
            
            # Reset the user's nickname
            try:
                current_name = ctx.author.display_name
                if current_name.startswith(f"{faction.abbreviation} "):
                    new_nickname = current_name[len(faction.abbreviation)+1:]
                    await ctx.author.edit(nick=new_nickname)
            except Exception as e:
                logger.error(f"Error resetting nickname: {e}")
                
            await ctx.respond(f"✅ You have left faction '{faction.name}' and it has been deleted as you were the last member.")
            return
        
        # Otherwise just remove them from the faction
        faction.members.remove(str(ctx.author.id))
        await faction.update(db)
        
        # Remove the faction role
        try:
            faction_role = discord.utils.get(ctx.guild.roles, id=int(faction.role_id)) if faction.role_id else None
            if faction_role:
                await ctx.author.remove_roles(faction_role)
        except Exception as e:
            await ctx.respond(f"⚠️ Failed to remove faction role: {e}", ephemeral=True)
        
        # Reset the user's nickname
        try:
            current_name = ctx.author.display_name
            if current_name.startswith(f"{faction.abbreviation} "):
                new_nickname = current_name[len(faction.abbreviation)+1:]
                await ctx.author.edit(nick=new_nickname)
        except:
            pass
            
        await ctx.respond(f"✅ You have left the faction '{faction.name}'.")
    
    @faction_group.command(
        name="remove", 
        description="Remove a member from your faction",
        contexts=[discord.InteractionContextType.guild],
        integration_types=[discord.IntegrationType.guild_install]
    )
    @premium_tier_required(tier=1)
    async def remove_member(
        self, 
        ctx, 
        member: discord.Option(discord.Member, "Member to remove", required=True)
    ):
        """
        Remove a member from your faction
        
        Only faction leaders can remove members.
        """
        db = self.bot.db
        
        # Check if the user is a faction leader
        faction = await Faction.get_by_member(db, str(ctx.author.id), ctx.guild.id)
        if not faction:
            await ctx.respond("⚠️ You are not in a faction.", ephemeral=True)
            return
            
        if faction.leader_id != str(ctx.author.id):
            await ctx.respond("⚠️ Only faction leaders can remove members.", ephemeral=True)
            return
            
        # Check if the target member is in the faction
        if str(member.id) not in faction.members:
            await ctx.respond(f"⚠️ {member.display_name} is not a member of your faction.", ephemeral=True)
            return
            
        # Check if the target is the leader (can't remove yourself this way)
        if str(member.id) == faction.leader_id:
            await ctx.respond("⚠️ You can't remove yourself as the faction leader. Use `/faction_leave` instead.", ephemeral=True)
            return
        
        # Remove member from the faction
        faction.members.remove(str(member.id))
        await faction.update(db)
        
        # Remove faction role
        try:
            faction_role = discord.utils.get(ctx.guild.roles, id=int(faction.role_id)) if faction.role_id else None
            if faction_role:
                await member.remove_roles(faction_role)
        except Exception as e:
            await ctx.respond(f"⚠️ Failed to remove faction role: {e}", ephemeral=True)
        
        # Reset the member's nickname
        try:
            current_name = member.display_name
            if current_name.startswith(f"{faction.abbreviation} "):
                new_nickname = current_name[len(faction.abbreviation)+1:]
                await member.edit(nick=new_nickname)
        except:
            pass
            
        await ctx.respond(f"✅ {member.mention} has been removed from the faction '{faction.name}'.")
        
        # Send a DM to the removed member
        try:
            await member.send(f"You have been removed from the faction '{faction.name}' in {ctx.guild.name}.")
        except:
            # Silently ignore if we can't DM the member
            pass
    
    @faction_group.command(
        name="transfer", 
        description="Transfer faction leadership to another member",
        contexts=[discord.InteractionContextType.guild],
        integration_types=[discord.IntegrationType.guild_install]
    )
    @premium_tier_required(tier=1)
    async def transfer_leadership(
        self, 
        ctx, 
        member: discord.Option(discord.Member, "New faction leader", required=True)
    ):
        """
        Transfer faction leadership to another member
        
        Only faction leaders can transfer leadership.
        """
        db = self.bot.db
        
        # Check if the user is a faction leader
        faction = await Faction.get_by_member(db, str(ctx.author.id), ctx.guild.id)
        if not faction:
            await ctx.respond("⚠️ You are not in a faction.", ephemeral=True)
            return
            
        if faction.leader_id != str(ctx.author.id):
            await ctx.respond("⚠️ Only faction leaders can transfer leadership.", ephemeral=True)
            return
            
        # Check if the target member is in the faction
        if str(member.id) not in faction.members:
            await ctx.respond(f"⚠️ {member.display_name} is not a member of your faction.", ephemeral=True)
            return
            
        # Check if the target is already the leader
        if str(member.id) == faction.leader_id:
            await ctx.respond(f"⚠️ {member.display_name} is already the faction leader.", ephemeral=True)
            return
            
        # Transfer leadership
        faction.leader_id = str(member.id)
        await faction.update(db)
            
        await ctx.respond(f"✅ Leadership of faction '{faction.name}' has been transferred to {member.mention}.")
        
        # Send a DM to the new leader
        try:
            await member.send(f"You are now the leader of the faction '{faction.name}' in {ctx.guild.name}!")
        except:
            # Silently ignore if we can't DM the member
            pass
    
    @faction_group.command(
        name="stats", 
        description="View faction statistics and leaderboard",
        contexts=[discord.InteractionContextType.guild],
        integration_types=[discord.IntegrationType.guild_install]
    )
    @premium_tier_required(tier=1)
    @background_task(initial_message="⏳ Gathering faction statistics...")
    async def faction_stats(
        self, 
        ctx,
        progress=None
    ):
        """View statistics and leaderboard for all factions"""
        db = self.bot.db
        
        # Get all factions
        factions = await Faction.get_all_for_guild(db, ctx.guild.id)
        
        if not factions:
            await ctx.respond("No factions have been created in this server yet.", ephemeral=True)
            return
        
        # Update progress
        progress['message'] = f"📊 Analyzing {len(factions)} factions"
        progress['percent'] = 10
        
        # Calculate stats for each faction
        faction_stats = {}
        players_collection = db["players"]
        killfeed_collection = db["killfeed"]
        
        # Initialize stats for each faction
        for faction in factions:
            faction_stats[faction.name] = {
                "kills": 0,
                "deaths": 0,
                "kd_ratio": 0,
                "members": len(faction.members),
                "longest_shot": 0,
                "faction_kills": 0,  # Kills against other factions
                "abbreviation": faction.abbreviation,
                "leader_id": faction.leader_id
            }
        
        # Update progress
        progress['message'] = "🔫 Calculating kill statistics for factions"
        progress['percent'] = 30
        
        # Process killfeed to find faction vs faction kills
        faction_members = {}
        for faction in factions:
            for member_id in faction.members:
                faction_members[member_id] = faction.name
        
        # Get recent killfeed entries (limit to last 1000 to avoid too much processing)
        killfeed_entries = await killfeed_collection.find({
            "guild_id": str(ctx.guild.id)
        }).sort("timestamp", -1).limit(1000).to_list(length=None)
        
        # Track faction vs faction kills
        for entry in killfeed_entries:
            killer_id = entry.get("killer_id")
            victim_id = entry.get("victim_id")
            
            if killer_id in faction_members and victim_id in faction_members:
                killer_faction = faction_members[killer_id]
                victim_faction = faction_members[victim_id]
                
                if killer_faction != victim_faction:
                    # This is a faction vs faction kill
                    faction_stats[killer_faction]["faction_kills"] += 1
        
        # Update progress
        progress['message'] = "👥 Processing player statistics for each faction"
        progress['percent'] = 60
        
        # Process player stats for each faction
        for i, faction in enumerate(factions):
            # Update per-faction progress
            current_faction = i + 1
            progress['percent'] = 60 + int((current_faction / len(factions)) * 30)
            progress['message'] = f"📈 Processing faction {current_faction}/{len(factions)}: {faction.name}"
            
            # Get stats for all members
            for member_id in faction.members:
                player_stats = await players_collection.find_one({"discord_id": member_id})
                if player_stats:
                    # Add up stats
                    kills = player_stats.get("kills", 0)
                    deaths = player_stats.get("deaths", 0)
                    
                    faction_stats[faction.name]["kills"] += kills
                    faction_stats[faction.name]["deaths"] += deaths
                    
                    # Track longest shot
                    longest_shot = player_stats.get("longest_shot", 0)
                    if longest_shot > faction_stats[faction.name]["longest_shot"]:
                        faction_stats[faction.name]["longest_shot"] = longest_shot
            
            # Calculate K/D ratio
            kills = faction_stats[faction.name]["kills"]
            deaths = faction_stats[faction.name]["deaths"]
            
            if deaths > 0:
                faction_stats[faction.name]["kd_ratio"] = round(kills / deaths, 2)
            else:
                faction_stats[faction.name]["kd_ratio"] = kills if kills > 0 else 0
        
        # Update progress
        progress['message'] = "🏆 Creating faction leaderboard"
        progress['percent'] = 95
        
        # Create leaderboard embed
        embed = discord.Embed(
            title="🏆 Faction Leaderboard",
            description=f"Statistics for all factions in {ctx.guild.name}",
            color=discord.Color.gold()
        )
        
        # Sort factions by kills
        sorted_factions = sorted(
            faction_stats.items(), 
            key=lambda x: x[1]["kills"], 
            reverse=True
        )
        
        # Add fields for top stats
        rank = 1
        for faction_name, stats in sorted_factions:
            embed.add_field(
                name=f"{rank}. {faction_name} [{stats['abbreviation']}]",
                value=(
                    f"👥 Members: {stats['members']}\n"
                    f"🔫 Kills: {stats['kills']}\n"
                    f"💀 Deaths: {stats['deaths']}\n"
                    f"📊 K/D: {stats['kd_ratio']}\n"
                    f"⚔️ Faction Kills: {stats['faction_kills']}"
                ),
                inline=True
            )
            rank += 1
        
        # Add longest shot field
        longest_shot_faction = max(faction_stats.items(), key=lambda x: x[1]["longest_shot"])
        if longest_shot_faction[1]["longest_shot"] > 0:
            embed.add_field(
                name="🎯 Longest Shot Record",
                value=f"{longest_shot_faction[0]}: {longest_shot_faction[1]['longest_shot']}m",
                inline=False
            )
        
        embed.set_footer(text=f"Updated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
        
        # Return the embed as the result
        progress['percent'] = 100
        return embed

def setup(bot):
    """Add the cog to the bot"""
    bot.add_cog(FactionCommands(bot))