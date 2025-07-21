import asyncio
import json
import os
import sys
from typing import Optional
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()  # load environment variables from .env

class MCPClient:
    def __init__(self):
        # Initialize session and client objects
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.openai = OpenAI()

    def log_blackboard(self, message: dict):
        with open("blackboard_log.txt", "a", encoding="utf-8") as f:
            f.write(json.dumps(message) + "\n")

    async def connect_to_server(self, server_script_path: str):
        """Connect to an MCP server
        
        Args:
            server_script_path: Path to the server script (.py or .js)
        """
        is_python = server_script_path.endswith('.py')
        is_js = server_script_path.endswith('.js')
        if not (is_python or is_js):
            raise ValueError("Server script must be a .py or .js file")
            
        command = "python" if is_python else "node"
        # Add this block to set PYTHONPATH
        env = os.environ.copy()
        venv_site_packages = os.path.join(sys.prefix, 'Lib', 'site-packages')
        if 'PYTHONPATH' in env:
            env['PYTHONPATH'] = f"{venv_site_packages};{env['PYTHONPATH']}"
        else:
            env['PYTHONPATH'] = venv_site_packages

        server_params = StdioServerParameters(
            command=command,
            args=[server_script_path],
            env=env
        )
        
        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
        self.stdio, self.write = stdio_transport
        self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))
        
        await self.session.initialize()
        
        # List available tools
        response = await self.session.list_tools()
        tools = response.tools
        print("\nConnected to server with tools:", [tool.name for tool in tools])

    async def process_query(self, query: str) -> str:
        """Process a query using OpenAI and available tools"""
        messages = [
            {
                "role": "user",
                "content": query
            }
        ]

        response = await self.session.list_tools()
        available_tools = [{ 
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.inputSchema
            }
        } for tool in response.tools]

        # Initial OpenAI API call
        response = self.openai.chat.completions.create(
            model="gpt-4o",
            max_tokens=1000,
            messages=messages,
            tools=available_tools if available_tools else None
        )

        # Process response and handle tool calls
        tool_results = []
        final_text = []
        
        choice = response.choices[0]
        message = choice.message

        if message.content:
            final_text.append(message.content)

        # Handle tool calls
        if message.tool_calls:
            messages.append({
                "role": "assistant",
                "content": message.content,
                "tool_calls": message.tool_calls
            })
            
            for tool_call in message.tool_calls:
                tool_name = tool_call.function.name
                tool_args = json.loads(tool_call.function.arguments)
                
                # Log the outgoing tool call
                self.log_blackboard({
                    "direction": "client_to_server",
                    "type": "tool_call",
                    "tool_name": tool_name,
                    "arguments": tool_args
                })
                
                # Execute tool call
                result = await self.session.call_tool(tool_name, tool_args)
                tool_results.append({"call": tool_name, "result": result})
                
                # Log the incoming tool result
                self.log_blackboard({
                    "direction": "server_to_client",
                    "type": "tool_result",
                    "tool_name": tool_name,
                    "result": str(result.content)  # Ensure JSON serializable
                })
                
                # Add tool result to messages
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": str(result.content)
                })

            # Get next response from OpenAI with tool results
            response = self.openai.chat.completions.create(
                model="gpt-4o",
                max_tokens=1000,
                messages=messages,
            )

            final_text.append(response.choices[0].message.content)

        return "\n".join(final_text)

    async def chat_loop(self):
        """Run an interactive chat loop"""
        print("\nMCP Client Started!")
        print("Type your queries or 'quit' to exit.")
        
        while True:
            try:
                query = input("\nQuery: ").strip()
                
                if query.lower() == 'quit':
                    break
                    
                response = await self.process_query(query)
                print("\n" + response)
                    
            except Exception as e:
                print(f"\nError: {str(e)}")
    
    async def cleanup(self):
        """Clean up resources"""
        await self.exit_stack.aclose()

async def main():
    if len(sys.argv) < 2:
        print("Usage: python client.py <path_to_server_script>")
        sys.exit(1)
        
    client = MCPClient()
    try:
        await client.connect_to_server(sys.argv[1])
        await client.chat_loop()
    finally:
        await client.cleanup()

if __name__ == "__main__":
    asyncio.run(main())