# LibreChat Model Context Protocol (MCP) Server

Based on [FastMCP](https://github.com/jlowin/fastmcp),
This mcp server allows LLMs to access LibreChats API.

## Features
- CRUD Agents

## Deployment

You can deploy the MCP server using Docker.

Start command: python main.py

## Helpful commands
### Set Token via cli with email & password (for local Docker/dev)
```bash
export LIBRECHAT_JWT_TOKEN=$(curl -c cookies.txt -sX POST "http://api:3080/api/auth/login" -H "Content-Type: application/json" -d '{"email":"'"$LIBRECHAT_EMAIL"'","password":"'"$LIBRECHAT_PASSWORD"'"}' | jq -r '.token')
```

curl -b cookies.txt -H "Authorization: Bearer $LIBRECHAT_JWT_TOKEN" -H "Accept: application/json" http://api:3080/api/agents?page=1&limit=10

# Troubleshooting
# If you see 'event: error' and 'Illegal request', try the following:
# 1. Try the versioned endpoint:
#    curl -b cookies.txt -H "Authorization: Bearer $LIBRECHAT_JWT_TOKEN" -H "Accept: application/json" http://api:3080/api/v1/agents?page=1&limit=10
# 2. Make sure your user is not banned and is verified in the database.
# 3. Check the backend logs for more details on the error.
# 4. Ensure you are hitting the backend API, not the frontend or a proxy.
```

python dev.py list_agents --page 1 --limit 5