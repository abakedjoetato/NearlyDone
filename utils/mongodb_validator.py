import os
import re
import subprocess
import sys
import time

def validate_mongodb_connection(bot_dir, mongodb_uri=None):
    """Validate MongoDB connection in the bot"""
    results = ["Starting MongoDB connection validation..."]
    
    if not bot_dir or not os.path.exists(bot_dir):
        results.append("Error: Bot directory does not exist")
        return results
    
    # Try to find MongoDB connection in the code
    mongo_files = []
    connection_patterns = []
    
    for root, dirs, files in os.walk(bot_dir):
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, bot_dir)
                
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        
                        # Check for MongoDB imports and usage
                        if 'import pymongo' in content or 'from pymongo' in content:
                            mongo_files.append(rel_path)
                            
                            # Extract connection patterns
                            # Look for MongoClient instantiation
                            client_matches = re.findall(r'MongoClient\s*\(\s*([^)]+)\s*\)', content)
                            for match in client_matches:
                                connection_patterns.append((rel_path, match.strip()))
                            
                            # Look for environment variable usage
                            env_matches = re.findall(r'os\.(getenv|environ\.get)\s*\(\s*[\'"](\w+)[\'"]', content)
                            for _, env_var in env_matches:
                                if 'MONGO' in env_var or 'DB' in env_var.upper():
                                    connection_patterns.append((rel_path, f"Environment variable: {env_var}"))
                            
                except Exception as e:
                    results.append(f"Error reading {rel_path}: {str(e)}")
    
    results.append(f"Found {len(mongo_files)} files with MongoDB imports")
    
    if not mongo_files:
        results.append("WARNING: No MongoDB imports found. Make sure the bot is using PyMongo library.")
        return results
    
    results.append(f"Found {len(connection_patterns)} potential MongoDB connection patterns:")
    for file, pattern in connection_patterns:
        results.append(f"  - {file}: {pattern}")
    
    # Test MongoDB connection
    if mongodb_uri:
        results.append("Testing MongoDB connection with provided URI...")
        
        # Create a temporary Python script to test the connection
        test_script = """
import pymongo
import sys
try:
    client = pymongo.MongoClient("%s", serverSelectionTimeoutMS=5000)
    # The ismaster command is cheap and does not require auth
    client.admin.command('ismaster')
    print("MongoDB connection successful")
    dbs = client.list_database_names()
    print(f"Available databases: {', '.join(dbs)}")
    sys.exit(0)
except Exception as e:
    print(f"MongoDB connection failed: {str(e)}")
    sys.exit(1)
""" % mongodb_uri
        
        test_script_path = os.path.join(bot_dir, '_mongo_test.py')
        try:
            with open(test_script_path, 'w') as f:
                f.write(test_script)
            
            process = subprocess.Popen(
                [sys.executable, test_script_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True
            )
            
            output, _ = process.communicate(timeout=10)
            results.extend(output.splitlines())
            
            if process.returncode == 0:
                results.append("✅ MongoDB connection test succeeded")
            else:
                results.append("❌ MongoDB connection test failed")
                
        except Exception as e:
            results.append(f"Error testing MongoDB connection: {str(e)}")
        finally:
            # Clean up the temporary script
            if os.path.exists(test_script_path):
                os.remove(test_script_path)
    else:
        results.append("No MongoDB URI provided for testing. Please provide a MongoDB URI to test the connection.")
    
    # Check if MongoDB connection is properly handled in the code
    try:
        connection_issues = check_mongodb_code_issues(bot_dir)
        results.extend(connection_issues)
    except Exception as e:
        results.append(f"Error checking MongoDB code issues: {str(e)}")
    
    results.append("MongoDB validation completed")
    return results

def check_mongodb_code_issues(bot_dir):
    """Check for common MongoDB code issues"""
    results = []
    
    for root, dirs, files in os.walk(bot_dir):
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, bot_dir)
                
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        
                        # Check for MongoClient without exception handling
                        if 'MongoClient' in content:
                            if 'try:' not in content or 'except' not in content:
                                results.append(f"ISSUE in {rel_path}: MongoDB connection without proper exception handling")
                        
                        # Check for proper serverSelectionTimeoutMS
                        if 'MongoClient' in content and 'serverSelectionTimeoutMS' not in content:
                            results.append(f"TIP for {rel_path}: Consider adding serverSelectionTimeoutMS to MongoClient to prevent hanging on connection issues")
                        
                        # Check for proper connection string usage
                        if 'MongoClient' in content and not re.search(r'os\.(getenv|environ\.get)', content):
                            results.append(f"SECURITY TIP for {rel_path}: Consider using environment variables for MongoDB connection string")
                        
                        # Check for proper connection closing
                        if 'MongoClient' in content and 'client.close' not in content:
                            results.append(f"TIP for {rel_path}: Consider explicitly closing MongoDB connections when done")
                        
                except Exception as e:
                    results.append(f"Error analyzing {rel_path}: {str(e)}")
    
    return results

if __name__ == "__main__":
    if len(sys.argv) > 1:
        bot_dir = sys.argv[1]
        mongodb_uri = sys.argv[2] if len(sys.argv) > 2 else None
        results = validate_mongodb_connection(bot_dir, mongodb_uri)
        for line in results:
            print(line)
    else:
        print("Please provide the bot directory path and optionally a MongoDB URI")
