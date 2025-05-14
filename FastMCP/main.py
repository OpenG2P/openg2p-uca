"""
Main entry point for the Social Benefits Assistant using FastMCP.

This script allows you to run the Eligibility and Grievance MCP servers,
as well as the client application that connects to them.
"""

import argparse
import os
import sys
import logging
import subprocess
from typing import List
import time

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('SocialBenefits-Main')

def get_project_root():
    """Get the absolute path of the project root directory."""
    return os.path.dirname(os.path.abspath(__file__))

def run_server(server_type: str, transport: str, host: str, port: int):
    """Run an MCP server in a subprocess."""
    
    server_script = f"{server_type}_server.py"
    script_path = os.path.join(get_project_root(), server_script)
    
    if not os.path.exists(script_path):
        logger.error(f"Server script not found: {script_path}")
        return None
    
    # Get the correct Python executable
    python_executable = sys.executable
    
    # Build command based on transport type
    if transport == "stdio":
        cmd = [python_executable, script_path, "--transport", "stdio"]
    else:  # SSE transport
        cmd = [python_executable, script_path, "--transport", "sse", "--host", host, "--port", str(port)]
    
    logger.info(f"Starting {server_type} server with command: {' '.join(cmd)}")
    
    # Run the server
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1
    )
    
    # Return the process
    return proc

def run_client(eligibility_url: str, grievance_url: str, ollama_url: str, model: str):
    """Run the MCP client application."""
    
    client_script = os.path.join(get_project_root(), "mcp_client.py")
    
    if not os.path.exists(client_script):
        logger.error(f"Client script not found: {client_script}")
        return None
    
    # Get the correct Python executable
    python_executable = sys.executable
    
    # Build command
    cmd = [
        python_executable, 
        client_script, 
        "--eligibility-url", eligibility_url,
        "--grievance-url", grievance_url,
        "--ollama-url", ollama_url,
        "--model", model
    ]
    
    logger.info(f"Starting client with command: {' '.join(cmd)}")
    
    # Run the client
    proc = subprocess.Popen(cmd)
    
    # Return the process
    return proc

def main():
    """Run the MCP-based social benefits assistant."""
    parser = argparse.ArgumentParser(description="MCP-based Social Benefits Assistant")
    
    # Database paths - using defaults from your original main.py
    parser.add_argument("--db", type=str, default="../program_db", help="Path to program database")
    parser.add_argument("--grievance-db", type=str, default="../grievance_db.sqlite", help="Path to grievance database")
    parser.add_argument("--index", type=str, default="../program_db_faiss/programs_index", help="Path to FAISS index")
    
    # Server configuration
    parser.add_argument("--transport", type=str, default="sse", choices=["stdio", "sse"], 
                      help="Transport protocol to use for MCP servers")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host for SSE servers")
    parser.add_argument("--eligibility-port", type=int, default=8000, help="Port for Eligibility MCP server")
    parser.add_argument("--grievance-port", type=int, default=8001, help="Port for Grievance MCP server")
    
    # Ollama configuration
    parser.add_argument("--ollama-url", type=str, default="http://localhost:11434", help="Ollama API URL")
    parser.add_argument("--model", type=str, default="llama2:8b", help="Ollama model name")
    parser.add_argument("--temp", type=float, default=0.1, help="Temperature for generation")
    
    # Run mode
    parser.add_argument("--mode", type=str, default="all", choices=["all", "eligibility", "grievance", "client"],
                      help="Which components to run")
    
    args = parser.parse_args()
    
    # Set environment variables for database paths
    os.environ["PROGRAM_DB_PATH"] = args.db
    os.environ["GRIEVANCE_DB_PATH"] = args.grievance_db
    os.environ["FAISS_INDEX_PATH"] = args.index
    
    print("\n==== MCP-based Social Benefits Assistant ====\n")
    
    servers = []
    eligibility_url = f"http://{args.host}:{args.eligibility_port}/sse"
    grievance_url = f"http://{args.host}:{args.grievance_port}/sse"
    
    try:
        # Start Eligibility server if needed
        if args.mode in ["all", "eligibility"]:
            eligibility_server = run_server("eligibility", args.transport, args.host, args.eligibility_port)
            if eligibility_server:
                servers.append(eligibility_server)
                print(f"Eligibility server started on port {args.eligibility_port}")
                # Wait a bit for server to initialize
                time.sleep(1)
        
        # Start Grievance server if needed
        if args.mode in ["all", "grievance"]:
            grievance_server = run_server("grievance", args.transport, args.host, args.grievance_port)
            if grievance_server:
                servers.append(grievance_server)
                print(f"Grievance server started on port {args.grievance_port}")
                # Wait a bit for server to initialize
                time.sleep(1)
        
        # Start client if needed
        if args.mode in ["all", "client"]:
            client = run_client(eligibility_url, grievance_url, args.ollama_url, args.model)
            if client:
                print("Client started and connected to servers")
                # Wait for client to exit
                client.wait()
        else:
            print("\nServers started. Press Ctrl+C to exit.")
            # Keep running until interrupted
            while True:
                time.sleep(1)
    
    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        # Terminate any running servers
        for server in servers:
            if server:
                server.terminate()
                try:
                    server.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    server.kill()
        
        print("All components terminated.")

if __name__ == "__main__":
    main()