import os
import ast
import importlib.util
import sys
import re

def analyze_bot_structure(bot_dir):
    """Analyze the bot's structure and look for common issues"""
    results = ["Starting bot structure analysis..."]
    
    # Check if bot directory exists
    if not os.path.exists(bot_dir):
        results.append("Error: Bot directory does not exist")
        return results
    
    # Look for essential Discord.py imports
    discord_imports = []
    mongodb_imports = []
    main_bot_files = []
    token_from_env = []
    mongodb_from_env = []
    
    for root, dirs, files in os.walk(bot_dir):
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, bot_dir)
                
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        
                        # Check for Discord.py imports
                        if 'import discord' in content or 'from discord' in content:
                            discord_imports.append(rel_path)
                        
                        # Check for MongoDB imports
                        if 'import pymongo' in content or 'from pymongo' in content:
                            mongodb_imports.append(rel_path)
                        
                        # Check for main bot files
                        if 'client = ' in content or 'bot = ' in content:
                            main_bot_files.append(rel_path)
                        
                        # Check for environment variable usage for Discord token
                        if 'os.getenv' in content or 'os.environ.get' in content:
                            if re.search(r'os\.(getenv|environ\.get)\s*\(\s*[\'"]DISCORD_TOKEN[\'"]', content):
                                token_from_env.append(rel_path)
                        
                        # Check for environment variable usage for MongoDB URI
                        if 'os.getenv' in content or 'os.environ.get' in content:
                            if re.search(r'os\.(getenv|environ\.get)\s*\(\s*[\'"]MONGODB_URI[\'"]', content):
                                mongodb_from_env.append(rel_path)
                except Exception as e:
                    results.append(f"Error reading {rel_path}: {str(e)}")
    
    results.append(f"Found {len(discord_imports)} files with Discord.py imports")
    if not discord_imports:
        results.append("WARNING: No Discord.py imports found. Make sure the bot is using Discord.py library.")
    
    results.append(f"Found {len(mongodb_imports)} files with MongoDB imports")
    if not mongodb_imports:
        results.append("WARNING: No MongoDB imports found. Make sure the bot is using PyMongo library.")
    
    results.append(f"Found {len(main_bot_files)} potential main bot files")
    if not main_bot_files:
        results.append("WARNING: No main bot files found. Look for files that create a Discord client/bot instance.")
    
    # Check if the bot is getting tokens from environment variables
    results.append(f"Found {len(token_from_env)} files using environment variables for Discord token")
    if not token_from_env:
        results.append("WARNING: No files found using environment variables for Discord token. This is a security risk.")
    
    results.append(f"Found {len(mongodb_from_env)} files using environment variables for MongoDB URI")
    if not mongodb_from_env:
        results.append("WARNING: No files found using environment variables for MongoDB URI. This is a security risk.")
    
    # Check requirement dependencies
    try:
        for root, dirs, files in os.walk(bot_dir):
            if 'requirements.txt' in files:
                req_path = os.path.join(root, 'requirements.txt')
                with open(req_path, 'r') as f:
                    requirements = f.read()
                results.append("Found requirements.txt file")
                
                # Check essential packages
                if 'discord.py' not in requirements and 'discord' not in requirements:
                    results.append("WARNING: discord.py not found in requirements.txt")
                
                if 'pymongo' not in requirements:
                    results.append("WARNING: pymongo not found in requirements.txt")
                
                break
        else:
            results.append("WARNING: No requirements.txt file found")
    except Exception as e:
        results.append(f"Error checking requirements: {str(e)}")
    
    # Check for common bot issues in code
    try:
        common_issues = check_for_common_issues(bot_dir)
        results.extend(common_issues)
    except Exception as e:
        results.append(f"Error checking for common issues: {str(e)}")
    
    results.append("Bot structure analysis completed")
    return results

def check_for_common_issues(bot_dir):
    """Check for common issues in Discord bot code"""
    results = []
    
    for root, dirs, files in os.walk(bot_dir):
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, bot_dir)
                
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        
                        # Check for hardcoded tokens
                        if re.search(r'token\s*=\s*[\'"][A-Za-z0-9._-]{59,}[\'"]', content, re.IGNORECASE):
                            results.append(f"SECURITY ISSUE in {rel_path}: Possible hardcoded Discord token found")
                        
                        # Check for hardcoded MongoDB URIs
                        if re.search(r'mongodb(\+srv)?://[^\s\'\"]+', content):
                            results.append(f"SECURITY ISSUE in {rel_path}: Possible hardcoded MongoDB URI found")
                        
                        # Check for proper exception handling
                        if 'except:' in content and not re.search(r'except\s+\w+', content):
                            results.append(f"CODE ISSUE in {rel_path}: Bare 'except:' clause found. Consider catching specific exceptions")
                        
                        # Check for proper intents usage (Discord.py v2.0+)
                        if 'discord.Intents.default()' in content and 'intents.message_content' not in content:
                            results.append(f"POTENTIAL ISSUE in {rel_path}: Using default intents without message_content. Bot may not be able to read message content")
                        
                        # Check for on_ready event
                        if 'async def on_ready' in content and 'print' in content:
                            results.append(f"TIP for {rel_path}: 'on_ready' event with print statement found. Consider using logging instead of print")
                        
                        # Check MongoDB connection without try/except
                        if ('MongoClient' in content and 'try:' not in content) or ('connect' in content and 'pymongo' in content and 'try:' not in content):
                            results.append(f"POTENTIAL ISSUE in {rel_path}: MongoDB connection without exception handling found")
                        
                        # Check for proper Discord command error handling
                        if '@commands.command' in content and 'on_command_error' not in content:
                            results.append(f"TIP for {rel_path}: Commands used but no global error handler found. Consider implementing on_command_error")
                        
                except Exception as e:
                    results.append(f"Error analyzing {rel_path}: {str(e)}")
    
    return results

if __name__ == "__main__":
    if len(sys.argv) > 1:
        bot_dir = sys.argv[1]
        results = analyze_bot_structure(bot_dir)
        for line in results:
            print(line)
    else:
        print("Please provide the bot directory path")
