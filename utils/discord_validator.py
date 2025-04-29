import os
import sys
import re
import json
import aiohttp
import asyncio

async def test_discord_connection(token):
    """Test the Discord connection with the provided token"""
    results = []
    
    if not token:
        results.append("No Discord token provided")
        return results
    
    results.append("Testing Discord API connection...")
    
    headers = {
        'Authorization': f'Bot {token}',
        'Content-Type': 'application/json'
    }
    
    async with aiohttp.ClientSession() as session:
        try:
            # Test connection by getting the bot's information
            async with session.get('https://discord.com/api/v10/users/@me', headers=headers) as response:
                if response.status == 200:
                    bot_info = await response.json()
                    results.append(f"✅ Successfully connected to Discord API")
                    results.append(f"Bot username: {bot_info.get('username', 'Unknown')}#{bot_info.get('discriminator', 'Unknown')}")
                    results.append(f"Bot ID: {bot_info.get('id', 'Unknown')}")
                    
                    # Get bot guilds (servers)
                    async with session.get('https://discord.com/api/v10/users/@me/guilds', headers=headers) as guilds_response:
                        if guilds_response.status == 200:
                            guilds = await guilds_response.json()
                            results.append(f"Bot is in {len(guilds)} servers")
                        else:
                            results.append(f"Could not retrieve bot's servers: HTTP {guilds_response.status}")
                
                elif response.status == 401:
                    results.append("❌ Authentication failed: Invalid Discord token")
                else:
                    results.append(f"❌ Discord API request failed: HTTP {response.status}")
                    error_text = await response.text()
                    results.append(f"Error details: {error_text}")
        
        except aiohttp.ClientError as e:
            results.append(f"❌ Network error connecting to Discord API: {str(e)}")
        except Exception as e:
            results.append(f"❌ Error testing Discord connection: {str(e)}")
    
    return results

def check_for_common_discord_issues(bot_dir):
    """Check for common Discord.py issues in the code"""
    results = []
    
    if not bot_dir or not os.path.exists(bot_dir):
        results.append("Bot directory does not exist")
        return results
    
    for root, dirs, files in os.walk(bot_dir):
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, bot_dir)
                
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        
                        # Check for intents configuration (Discord.py 2.0+)
                        if 'discord.Intents' in content:
                            if 'default()' in content and 'message_content' not in content:
                                results.append(f"ISSUE in {rel_path}: Using default intents without enabling message_content. Bot may not be able to read message content.")
                            
                            if 'message_content = True' not in content and 'on_message' in content:
                                results.append(f"POTENTIAL ISSUE in {rel_path}: Using on_message event but message_content intent might not be enabled")
                        
                        # Check for proper event error handling
                        if 'async def on_' in content and 'try:' not in content:
                            results.append(f"TIP for {rel_path}: Consider adding try/except blocks in event handlers to prevent bot crashes")
                        
                        # Check for proper command error handling
                        if '@commands.command' in content and 'on_command_error' not in content:
                            results.append(f"TIP for {rel_path}: Commands used but no error handler found. Consider implementing on_command_error")
                        
                        # Check for rate limiting awareness
                        if 'channel.send' in content or 'send_message' in content:
                            # Check if there are any sleep calls or rate limiting handling
                            if 'sleep(' not in content and 'wait_for' not in content and 'wait_until' not in content:
                                results.append(f"TIP for {rel_path}: Be aware of Discord rate limits when sending messages")
                        
                        # Check for proper token handling
                        if 'client.run' in content or 'bot.run' in content:
                            if not re.search(r'os\.(getenv|environ\.get)', content):
                                results.append(f"SECURITY ISSUE in {rel_path}: Consider using environment variables for Discord token")
                        
                        # Check for client vs bot usage
                        if 'discord.Client' in content and '@client.event' in content:
                            results.append(f"TIP for {rel_path}: Using discord.Client. Consider using discord.ext.commands.Bot for command handling")
                        
                except Exception as e:
                    results.append(f"Error analyzing {rel_path}: {str(e)}")
    
    return results

def validate_discord_token(token):
    """Validate Discord token and check for common Discord issues"""
    results = ["Starting Discord API validation..."]
    
    if not token:
        results.append("No Discord token provided for testing")
        return results
    
    # Run the async function in a new event loop
    try:
        connection_results = asyncio.run(test_discord_connection(token))
        results.extend(connection_results)
    except Exception as e:
        results.append(f"Error testing Discord connection: {str(e)}")
    
    results.append("Discord API validation completed")
    return results

if __name__ == "__main__":
    if len(sys.argv) > 1:
        token = sys.argv[1]
        bot_dir = sys.argv[2] if len(sys.argv) > 2 else None
        
        # Validate token
        results = validate_discord_token(token)
        for line in results:
            print(line)
        
        # Check for common issues if bot directory is provided
        if bot_dir:
            issue_results = check_for_common_discord_issues(bot_dir)
            for line in issue_results:
                print(line)
    else:
        print("Please provide a Discord token and optionally a bot directory path")
