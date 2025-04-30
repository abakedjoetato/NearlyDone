#!/bin/bash
# Script to start the Discord bot properly

echo "Starting Discord bot..."

# First, let's check if we have a Discord token
if [ -z "$DISCORD_TOKEN" ]; then
    echo "ERROR: DISCORD_TOKEN environment variable is not set!"
    echo "The bot cannot start without a valid Discord token."
    exit 1
fi

# Kill any existing bot processes
echo "Cleaning up any existing bot processes..."
pkill -f "python bot_main.py" || true
pkill -f "python bot_launcher.py" || true

# Remove any stale PID files
rm -f temp/bot.pid || true

# First run command registration to ensure all commands are registered
echo "Registering commands with Discord..."
python smart_register_commands.py

# Wait a moment for command registration to complete
sleep 3

# Now start the actual bot
echo "Starting the bot process..."
nohup python bot_main.py > logs/bot_output.log 2>&1 &

# Save the PID to a file
echo $! > temp/bot.pid
echo "Bot started with PID: $!"
echo "Log output will be saved to logs/bot_output.log"
echo "Done!"