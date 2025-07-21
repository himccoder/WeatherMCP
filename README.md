


You would need to run this in virutal environment. 

## FOR ALREADY SET UP ENVIRONMENT: 
# To run server: 

uv run mcp dev "weather.py" 

# To run client: 
uv run client.py ../weather/weather.py

As you give queries the messages between client nad server tools will be logged. in json format under mcp-client/blackboard_log.txt


Also be sure to add .env file to you mcp-client with OPENAI_API_KEY = ...

## FOR FIRST TIME SET UP ENVIRONMENT: 
# Setup MCP weather server: 
cd weather
uv venv
.venv\Scripts\activate   # On Windows
# OR
source .venv/bin/activate   # On Unix/MacOS

uv add mcp[cli] httpx

# Set Up the MCP Client:
cd ../mcp-client
uv venv
.venv\Scripts\activate   # On Windows
# OR
source .venv/bin/activate   # On Unix/MacOS

uv add mcp openai python-dotenv

# Start the server:
cd ../weather
uv run mcp dev "weather.py"

# In a new terminal, start the client:
cd mcp-client
uv run client.py ../weather/weather.py


