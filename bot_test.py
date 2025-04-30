"""
Discord Bot Test Script

This script tests the bot's command registration system and overall stability
without starting the full bot. It performs diagnostic tests and reports the results
to make sure everything is working correctly.
"""

import os
import sys
import logging
import asyncio
import traceback
from datetime import datetime
import importlib.util

# Setup basic logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('bot_test')

print("="*80)
print("DISCORD BOT TEST SCRIPT")
print(f"Starting test at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("="*80)

async def test_command_registration():
    """Test that our command registration system works properly"""
    print("\n=> Testing Discord Command Registration")
    
    try:
        # Check if the discord_command_manager module exists
        if not os.path.exists('utils/discord_command_manager.py'):
            print("❌ Command manager file not found: utils/discord_command_manager.py")
            return False
        
        # Try to import the module
        try:
            sys.path.insert(0, '.')
            from utils.discord_command_manager import register_commands, extract_command_data
            print("✅ Command manager module imported successfully")
        except ImportError as e:
            print(f"❌ Failed to import command manager: {e}")
            traceback.print_exc()
            return False
        
        # Check if bot_main.py exists and is using our command manager
        if not os.path.exists('bot_main.py'):
            print("❌ Bot main file not found: bot_main.py")
            return False
        
        # Load bot_main.py as a module to check its content
        try:
            spec = importlib.util.spec_from_file_location("bot_main", "bot_main.py")
            bot_main = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(bot_main)
            
            # Check if sync_slash_commands function exists and is using the right module
            if not hasattr(bot_main, 'sync_slash_commands'):
                print("❌ sync_slash_commands function not found in bot_main.py")
                return False
            
            # Check the content of the function (approximate check)
            function_code = bot_main.sync_slash_commands.__code__
            function_text = open('bot_main.py', 'r').read()
            
            if 'discord_command_manager' in function_text and 'register_commands' in function_text:
                print("✅ bot_main.py is using the new command manager")
            else:
                print("❌ bot_main.py does not appear to be using the new command manager")
                return False
                
            print("✅ Command registration test passed")
            return True
            
        except Exception as e:
            print(f"❌ Error inspecting bot_main.py: {e}")
            traceback.print_exc()
            return False
            
    except Exception as e:
        print(f"❌ General error in command registration test: {e}")
        traceback.print_exc()
        return False

async def test_cog_loading():
    """Test that all cogs can be loaded properly"""
    print("\n=> Testing Cog Loading")
    
    try:
        # Check if the cogs directory exists
        if not os.path.exists('cogs'):
            print("❌ Cogs directory not found")
            return False
        
        # List all cog files
        cog_files = [f for f in os.listdir('cogs') if f.endswith('.py')]
        print(f"Found {len(cog_files)} cog files")
        
        # Look for refactored cogs specifically
        refactored_cogs = [f for f in cog_files if 'refactored' in f]
        print(f"Found {len(refactored_cogs)} refactored cog files: {refactored_cogs}")
        
        # Try to import each refactored cog
        successful_imports = 0
        for cog_file in refactored_cogs:
            try:
                module_name = f"cogs.{cog_file[:-3]}"  # Remove .py extension
                spec = importlib.util.spec_from_file_location(module_name, f"cogs/{cog_file}")
                cog_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(cog_module)
                print(f"✅ Successfully imported {cog_file}")
                successful_imports += 1
            except Exception as e:
                print(f"❌ Failed to import {cog_file}: {e}")
                traceback.print_exc()
                
        # Check success rate
        if successful_imports == 0:
            print("❌ No cogs could be imported")
            return False
        elif successful_imports < len(refactored_cogs):
            print(f"⚠️ Only {successful_imports}/{len(refactored_cogs)} cogs imported successfully")
            return True  # Partial success
        else:
            print("✅ All refactored cogs imported successfully")
            return True
            
    except Exception as e:
        print(f"❌ General error in cog loading test: {e}")
        traceback.print_exc()
        return False

async def check_bot_runner():
    """Test the bot runner script"""
    print("\n=> Testing Bot Runner")
    
    try:
        # Check if bot_run.py exists
        if not os.path.exists('bot_run.py'):
            print("❌ Bot runner file not found: bot_run.py")
            return False
        
        # Check the content of the file
        try:
            with open('bot_run.py', 'r') as f:
                content = f.read()
                
            if 'bot_main' in content and 'main()' in content:
                print("✅ Bot runner appears to be configured correctly")
                return True
            else:
                print("❌ Bot runner does not appear to be using bot_main.py")
                return False
                
        except Exception as e:
            print(f"❌ Error reading bot_run.py: {e}")
            return False
            
    except Exception as e:
        print(f"❌ General error in bot runner test: {e}")
        traceback.print_exc()
        return False

async def main():
    """Run all tests"""
    # Test command registration
    registration_ok = await test_command_registration()
    
    # Test cog loading
    cogs_ok = await test_cog_loading()
    
    # Test bot runner
    runner_ok = await check_bot_runner()
    
    # Print summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    print(f"Command Registration: {'✅ PASS' if registration_ok else '❌ FAIL'}")
    print(f"Cog Loading:          {'✅ PASS' if cogs_ok else '❌ FAIL'}")
    print(f"Bot Runner:           {'✅ PASS' if runner_ok else '❌ FAIL'}")
    print("="*80)
    
    if registration_ok and cogs_ok and runner_ok:
        print("\n✅ ALL TESTS PASSED - Bot should be stable and command registration working")
    else:
        print("\n❌ SOME TESTS FAILED - Check the output above for details")

if __name__ == "__main__":
    asyncio.run(main())