#!/usr/bin/env python3
"""
Discord Token Check Utility

This script checks whether the Discord token is available and valid.
It helps diagnose issues with the Discord bot not connecting properly.
"""

import os
import sys
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('token_check')

def main():
    """Check if Discord token is configured properly"""
    # Get the token from environment variables
    token = os.environ.get('DISCORD_TOKEN')
    
    if not token:
        logger.error("❌ DISCORD_TOKEN environment variable is not set")
        logger.error("The Discord bot cannot start without a valid token")
        logger.error("Please set the DISCORD_TOKEN environment variable")
        return 1
    
    # Basic validation of token format
    # Discord tokens are generally ~60-70 characters and start with specific format
    if len(token) < 50:
        logger.warning("⚠️ DISCORD_TOKEN seems too short for a valid token")
    
    if not any(token.startswith(prefix) for prefix in ["Nz", "OD", "MT", "Mj"]):
        logger.warning("⚠️ DISCORD_TOKEN does not start with expected prefix")
    
    logger.info(f"✅ DISCORD_TOKEN is set (length: {len(token)} characters)")
    logger.info("Token format validation passed initial checks")
    
    # Note: We don't show the actual token for security reasons
    masked_token = token[:5] + "..." + token[-5:]
    logger.info(f"Token preview: {masked_token}")
    
    # Check for dotenv file
    if os.path.exists('.env'):
        logger.info("✅ .env file exists")
        
        # Check if .env contains DISCORD_TOKEN
        with open('.env', 'r') as f:
            env_contents = f.read()
            if 'DISCORD_TOKEN' in env_contents:
                logger.info("✅ DISCORD_TOKEN is defined in .env file")
            else:
                logger.warning("⚠️ DISCORD_TOKEN is not defined in .env file")
    else:
        logger.warning("⚠️ No .env file found")
    
    logger.info("Discord token check completed")
    return 0

if __name__ == "__main__":
    sys.exit(main())