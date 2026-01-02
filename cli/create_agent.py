#!/usr/bin/env python3
"""
CLI tool to create agents using LibreChat-MCP
Usage: python LibreChat-MCP/cli/create_agent.py
"""
import sys
import os
from pathlib import Path

# Add LibreChat-MCP directory to path for relative imports
librechat_mcp_path = Path(__file__).parent.parent
sys.path.insert(0, str(librechat_mcp_path))

# Change to LibreChat-MCP directory so relative imports work
original_cwd = os.getcwd()
os.chdir(str(librechat_mcp_path))

# Import using relative imports (as if running from LibreChat-MCP directory)
from tools.agent import create_agent
from shared.storage import set_current_user, token_store

# Restore original directory
os.chdir(original_cwd)

def get_user_from_mongodb():
    """Try to get a user ID from MongoDB"""
    try:
        import subprocess
        result = subprocess.run(
            ['docker', 'exec', 'chat-mongodb', 'mongosh', '--quiet', '--eval', 'db.users.findOne({}, {_id: 1})'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            import json
            import re
            # Try to parse the output
            output = result.stdout.strip()
            # Try JSON first
            try:
                data = json.loads(output)
                if '_id' in data:
                    if isinstance(data['_id'], dict) and '$oid' in data['_id']:
                        return data['_id']['$oid']
                    elif isinstance(data['_id'], str):
                        return data['_id']
            except:
                # Try regex for ObjectId
                match = re.search(r'ObjectId\("([^"]+)"\)', output)
                if match:
                    return match.group(1)
    except:
        pass
    return None

def main():
    """Create The Navigator agent"""
    
    # Get user ID from command line, environment, database, or MongoDB
    user_id = None
    
    # Check command line argument
    if len(sys.argv) > 1:
        user_id = sys.argv[1]
    
    # Check environment
    if not user_id:
        user_id = os.environ.get('LIBRECHAT_USER_ID')
    
    # Check token database
    if not user_id:
        import sqlite3
        db_path = token_store.db_path
        if db_path.exists():
            with sqlite3.connect(db_path) as conn:
                cursor = conn.execute("SELECT user_id FROM user_tokens LIMIT 1")
                row = cursor.fetchone()
                if row:
                    user_id = row[0]
    
    # Try MongoDB as last resort
    if not user_id:
        user_id = get_user_from_mongodb()
        if user_id:
            print(f"📝 Found user in MongoDB: {user_id}")
            print("⚠️  Warning: This user may not have a token. Authentication may fail.")
            print("   If it fails, please authenticate via LibreChat-MCP OAuth first.")
    
    if not user_id:
        print("❌ No user ID found.")
        print("   Usage: python LibreChat-MCP/cli/create_agent.py [user_id]")
        print("   Or set LIBRECHAT_USER_ID environment variable")
        print("   Or authenticate via LibreChat-MCP OAuth first")
        sys.exit(1)
    
    print(f"📝 Using user: {user_id}")
    
    # Set current user context
    set_current_user(user_id)
    
    # Check if token exists, if not try to generate one
    token_data = token_store.get_token(user_id)
    
    if not token_data:
        # Try to generate a token using JWT_SECRET if available
        jwt_secret = os.environ.get('JWT_SECRET')
        if not jwt_secret:
            # Try to get from LibreChat container
            try:
                import subprocess
                result = subprocess.run(
                    ['docker', 'exec', 'LibreChat', 'printenv', 'JWT_SECRET'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    jwt_secret = result.stdout.strip()
            except:
                pass
        
        if jwt_secret:
            print("⚠️  No stored token found, but JWT_SECRET available.")
            print("   Attempting to generate token (may fail if API validates against database)...")
            # Generate a short-lived token
            import jwt
            import time
            token = jwt.encode(
                {'id': user_id, 'iat': int(time.time())},
                jwt_secret,
                algorithm='HS256'
            )
            # Save it temporarily
            token_store.save_token(user_id, token, {})
            token_data = {'jwt_token': token, 'cookies': {}}
        else:
            print(f"❌ No token found for user {user_id}")
            print("   Please authenticate via LibreChat-MCP OAuth first.")
            print("   Or set JWT_SECRET environment variable to generate a token.")
            sys.exit(1)
    
    # Read agent instructions (from project root)
    project_root = Path(__file__).parent.parent.parent
    instructions_path = project_root / "docs" / "cursor" / "navigator-agent-instructions.md"
    if not instructions_path.exists():
        print(f"❌ Instructions file not found: {instructions_path}")
        sys.exit(1)
    
    instructions = instructions_path.read_text()
    
    # Override API_BASE_URL to use localhost if running from host
    api_base_url = os.environ.get("LIBRECHAT_API_BASE_URL", "http://api:3080/api")
    if "api:" in api_base_url:
        # Running from host, use localhost
        port = os.environ.get("PORT", "3080")
        api_base_url = f"http://localhost:{port}/api"
        os.environ["LIBRECHAT_API_BASE_URL"] = api_base_url
    
    # Create agent
    print("🚀 Creating The Navigator agent...\n")
    print(f"   API URL: {api_base_url}")
    
    try:
        result = create_agent(
            name="The Navigator",
            description="Your personal task management and planning assistant, helping you navigate your workload using GTD methodology and Eisenhower Matrix prioritization. Ahoy! Let's chart your course to productivity!",
            instructions=instructions,
            provider="groq",
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            category="task-management",
            conversation_starters=[
                "Ahoy! What tasks need charting today?",
                "Let's review your tasks and priorities",
                "What project should we focus on?",
                "Show me my tasks for @work"
            ],
            recursion_limit=25
        )
        
        # Extract agent ID
        agent_id = result.get('id') or result.get('_id') or result.get('agent_id')
        
        if not agent_id:
            print("❌ Agent created but could not extract ID")
            print(f"Response: {result}")
            sys.exit(1)
        
        print(f"\n✅ Navigator agent created successfully!")
        print(f"   Agent ID: {agent_id}")
        
        # Update librechat.yaml (from project root)
        yaml_path = project_root / "librechat.yaml"
        if yaml_path.exists():
            content = yaml_path.read_text()
            if 'agent_PLACEHOLDER_UPDATE_AFTER_CREATION' in content:
                content = content.replace(
                    'agent_id: "agent_PLACEHOLDER_UPDATE_AFTER_CREATION"',
                    f'agent_id: "{agent_id}"'
                )
                yaml_path.write_text(content)
                print(f"✅ Updated librechat.yaml with agent_id")
            else:
                print(f"⚠️  Could not find placeholder in librechat.yaml")
                print(f"   Please manually update with agent_id: {agent_id}")
        
        print(f"\n🎉 Done! The Navigator agent is ready to use.")
        return 0
        
    except Exception as e:
        print(f"❌ Failed to create agent: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    sys.exit(main())

