"""
Main entry point for the Social Benefits Assistant using Low-Level MCP.
"""

import argparse
import logging
import datetime
import sys

from social_benefits_mcp import SocialBenefitsMCP

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('SocialBenefits-Main')

def main():
    """Run the MCP-based social benefits assistant."""
    parser = argparse.ArgumentParser(description="MCP-based Social Benefits Assistant")
    parser.add_argument("--db", type=str, default="../program_db", help="Path to program database")
    parser.add_argument("--grievance-db", type=str, default="../grievance_db.sqlite", help="Path to grievance database")
    parser.add_argument("--index", type=str, default="../program_db_faiss/programs_index", help="Path to FAISS index")
    parser.add_argument("--model", type=str, default="deepseek-r1:8b", help="Ollama model name")
    parser.add_argument("--temp", type=float, default=0.1, help="Temperature for generation")
    parser.add_argument("--url", type=str, default="http://localhost:11434", help="Ollama API URL")
    parser.add_argument("--transport", type=str, default="stdio", choices=["stdio", "sse"], help="Transport protocol to use")
    
    args = parser.parse_args()
    
    print("\n==== MCP-based Social Benefits Assistant ====\n")
    print("Initializing system components...")
    
    # Initialize the MCP-based assistant
    assistant = SocialBenefitsMCP(
        db_path=args.db,
        grievance_db_path=args.grievance_db,
        faiss_index_path=args.index,
        model=args.model,
        temperature=args.temp,
        ollama_url=args.url
    )
    
    # Check if we should run in server mode or interactive mode
    if args.transport != "stdio":
        print(f"\nStarting server with {args.transport} transport...")
        # Run the MCP server with the specified transport
        assistant.run(args.transport)
    else:
        # Interactive mode
        print("\nAssistant Ready!")
        print("You can ask about program information, eligibility, or file grievances.")
        print("Type 'quit' to exit, 'reset' to clear conversation history.")
        
        # Generate unique thread ID for this session
        session_id = f"cli_session_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # Interactive loop
        while True:
            try:
                # Get user input
                user_input = input("\nYou: ")
                
                # Check for special commands
                if user_input.lower() in ["quit", "exit", "bye"]:
                    print("\nThank you for using the Social Benefits Assistant. Goodbye!")
                    break
                    
                if user_input.lower() == "reset":
                    assistant.reset_conversation(session_id)
                    print("Conversation history has been reset.")
                    continue
                
                # Process the query
                print("Processing...")
                response = assistant.process_query(user_input, session_id)
                
                # Display the response
                print(f"\nAssistant: {response}")
                
            except KeyboardInterrupt:
                print("\nExiting...")
                break
            except Exception as e:
                print(f"\nError: {e}")
                print("Please try again.")

if __name__ == "__main__":
    main()