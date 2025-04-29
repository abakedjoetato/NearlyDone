import os
import logging
from flask import Flask, render_template, request, jsonify, session, flash, redirect, url_for
import tempfile
import shutil
import zipfile
import subprocess
import time
import threading

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "development_secret_key")

# Global variable to store the uploaded bot's directory
BOT_DIR = None
DEBUG_OUTPUT = []
BOT_PROCESS = None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_bot():
    global BOT_DIR
    
    if 'bot_file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    bot_file = request.files['bot_file']
    
    if bot_file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    if not bot_file.filename.endswith('.zip'):
        return jsonify({'error': 'File must be a ZIP archive'}), 400
    
    # Create a temporary directory to extract the bot
    if BOT_DIR and os.path.exists(BOT_DIR):
        shutil.rmtree(BOT_DIR)
    
    BOT_DIR = tempfile.mkdtemp()
    
    try:
        # Save the uploaded file
        zip_path = os.path.join(BOT_DIR, 'bot.zip')
        bot_file.save(zip_path)
        
        # Extract the ZIP file
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(BOT_DIR)
        
        # Remove the ZIP file
        os.remove(zip_path)
        
        # Scan for main bot file
        main_files = []
        for root, dirs, files in os.walk(BOT_DIR):
            for file in files:
                if file.endswith('.py'):
                    with open(os.path.join(root, file), 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        if 'import discord' in content and ('client = ' in content or 'bot = ' in content):
                            main_files.append(os.path.relpath(os.path.join(root, file), BOT_DIR))
        
        if not main_files:
            return jsonify({'error': 'No Discord bot main file found'}), 400
        
        # List all Python files in the project
        python_files = []
        for root, dirs, files in os.walk(BOT_DIR):
            for file in files:
                if file.endswith('.py'):
                    python_files.append(os.path.relpath(os.path.join(root, file), BOT_DIR))
        
        return jsonify({
            'success': True,
            'main_files': main_files,
            'python_files': python_files
        })
    
    except Exception as e:
        logger.exception("Error processing uploaded bot")
        return jsonify({'error': str(e)}), 500

@app.route('/debug', methods=['GET', 'POST'])
def debug():
    global BOT_DIR, DEBUG_OUTPUT, BOT_PROCESS
    
    if not BOT_DIR or not os.path.exists(BOT_DIR):
        flash('Please upload a bot first', 'danger')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'validate_structure':
            # Analyze bot structure
            DEBUG_OUTPUT = []
            from bot_debugger import analyze_bot_structure
            results = analyze_bot_structure(BOT_DIR)
            DEBUG_OUTPUT.extend(results)
            
        elif action == 'validate_mongodb':
            # Test MongoDB connection
            DEBUG_OUTPUT = []
            from utils.mongodb_validator import validate_mongodb_connection
            mongodb_uri = request.form.get('mongodb_uri', '')
            results = validate_mongodb_connection(BOT_DIR, mongodb_uri)
            DEBUG_OUTPUT.extend(results)
            
        elif action == 'validate_discord':
            # Test Discord token
            DEBUG_OUTPUT = []
            from utils.discord_validator import validate_discord_token
            discord_token = request.form.get('discord_token', '')
            results = validate_discord_token(discord_token)
            DEBUG_OUTPUT.extend(results)
            
        elif action == 'run_bot':
            # Run the bot
            if BOT_PROCESS and BOT_PROCESS.poll() is None:
                BOT_PROCESS.terminate()
                time.sleep(1)
            
            main_file = request.form.get('main_file')
            discord_token = request.form.get('discord_token', '')
            mongodb_uri = request.form.get('mongodb_uri', '')
            
            if not main_file:
                DEBUG_OUTPUT = ["Error: No main file selected"]
            else:
                DEBUG_OUTPUT = ["Starting bot process..."]
                
                # Set environment variables for the subprocess
                env = os.environ.copy()
                if discord_token:
                    env['DISCORD_TOKEN'] = discord_token
                if mongodb_uri:
                    env['MONGODB_URI'] = mongodb_uri
                
                try:
                    BOT_PROCESS = subprocess.Popen(
                        ['python', os.path.join(BOT_DIR, main_file)],
                        cwd=BOT_DIR,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        env=env
                    )
                    
                    # Start a thread to capture output
                    def capture_output():
                        while BOT_PROCESS.poll() is None:
                            line = BOT_PROCESS.stdout.readline()
                            if line:
                                DEBUG_OUTPUT.append(line.strip())
                    
                    threading.Thread(target=capture_output, daemon=True).start()
                    
                except Exception as e:
                    DEBUG_OUTPUT.append(f"Error starting bot: {str(e)}")
        
        elif action == 'stop_bot':
            # Stop the bot if it's running
            if BOT_PROCESS and BOT_PROCESS.poll() is None:
                BOT_PROCESS.terminate()
                DEBUG_OUTPUT.append("Bot process terminated")
            else:
                DEBUG_OUTPUT.append("No bot process running")
    
    # Get list of Python files for the form
    python_files = []
    if BOT_DIR and os.path.exists(BOT_DIR):
        for root, dirs, files in os.walk(BOT_DIR):
            for file in files:
                if file.endswith('.py'):
                    python_files.append(os.path.relpath(os.path.join(root, file), BOT_DIR))
    
    return render_template('debug.html', debug_output=DEBUG_OUTPUT, python_files=python_files)

@app.route('/debug_output', methods=['GET'])
def get_debug_output():
    global DEBUG_OUTPUT
    return jsonify({'output': DEBUG_OUTPUT})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
