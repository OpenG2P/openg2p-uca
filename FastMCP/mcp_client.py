"""
MCP Client for Social Benefits Assistant.

This module implements the client side of the MCP protocol, connecting to the Ollama LLM
and calling the appropriate MCP servers (eligibility and grievance) based on user intent.
"""

import argparse
import asyncio
import json
import logging
import re
from typing import Dict, List, Any, Optional, Tuple

import anyio
import httpx
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.client.sse import sse_client
from mcp.shared.session import RequestResponder
from mcp.types import JSONRPCMessage, ServerRequest, ServerNotification

# Set up logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('SocialBenefits-MCPClient')

class OllamaClient:
    """Client for interacting with Ollama LLMs."""
    
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llama2:8b", temperature: float = 0.1):
        """Initialize the Ollama client."""
        self.base_url = base_url
        self.model = model
        self.temperature = temperature
        self.conversation_history = []
        logger.info(f"OllamaClient initialized with model: {model}, temperature: {temperature}")
    
    async def generate(self, prompt: str, system_prompt: str = None) -> str:
        """Generate a response using the Ollama API."""
        try:
            # Prepare the request
            url = f"{self.base_url}/api/chat"
            
            messages = [
                {"role": "system", "content": system_prompt or "You are a helpful assistant."},
                *self.conversation_history,
                {"role": "user", "content": prompt}
            ]
            
            payload = {
                "model": self.model,
                "messages": messages,
                "temperature": self.temperature,
                "stream": False
            }
            
            # Send the request
            logger.debug(f"Sending request to Ollama API")
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                result = response.json()
            
            assistant_message = result["message"]["content"]
            
            # Update conversation history
            self.conversation_history.append({"role": "user", "content": prompt})
            self.conversation_history.append({"role": "assistant", "content": assistant_message})
            
            # Keep history manageable
            if len(self.conversation_history) > 10:
                self.conversation_history = self.conversation_history[-10:]
            
            logger.debug(f"Generated response (length: {len(assistant_message)})")
            return assistant_message
            
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return f"Error: {e}"
    
    def clear_history(self):
        """Clear the conversation history."""
        self.conversation_history = []
        logger.info("Cleared conversation history")

class MCPClientApp:
    """Main MCP client application for Social Benefits Assistant."""
    
    SYSTEM_PROMPT = """You are a Social Benefits Assistant that helps users find and understand benefit programs they may be eligible for.
    
You have access to two specialized subsystems:
1. Eligibility subsystem - for finding programs and analyzing eligibility
2. Grievance subsystem - for handling complaints and issues with benefits

Based on the user's query, determine which subsystem to use and call the appropriate MCP tools. 
If the user mentions issues, complaints, or status checking, use the Grievance subsystem.
Otherwise, use the Eligibility subsystem to help them find programs.

When calling MCP tools, format the response in a natural, conversational style. 
Avoid mentioning the underlying technical details of how you retrieved the information.

Always be friendly, empathetic, and supportive in your responses.
"""

    def __init__(
        self,
        eligibility_url: str = "http://localhost:8000/sse",
        grievance_url: str = "http://localhost:8001/sse",
        ollama_url: str = "http://localhost:11434",
        model: str = "llama2:8b"
    ):
        """Initialize the MCP client application."""
        self.eligibility_url = eligibility_url
        self.grievance_url = grievance_url
        self.ollama_client = OllamaClient(base_url=ollama_url, model=model)
        self.eligibility_session = None
        self.grievance_session = None
        
        # State for tracking active sessions
        self.active_sessions = {}
        self.session_id = None
        
        logger.info("MCP Client Application initialized")
    
    async def connect_to_servers(self):
        """Connect to eligibility and grievance MCP servers."""
        logger.info("Connecting to MCP servers...")
        
        # Connect to Eligibility MCP server
        eligibility_streams = await sse_client(self.eligibility_url)
        self.eligibility_session = await self._create_session(eligibility_streams)
        
        # Connect to Grievance MCP server
        grievance_streams = await sse_client(self.grievance_url)
        self.grievance_session = await self._create_session(grievance_streams)
        
        logger.info("Connected to MCP servers successfully")
    
    async def _create_session(self, streams):
        """Create an MCP client session."""
        session = ClientSession(*streams)
        await session.initialize()
        return session
    
    async def analyze_intent(self, query: str) -> str:
        """Analyze the intent of a user query to determine which subsystem to use."""
        try:
            # Simple rule-based intent analysis for now
            # In a real application, this could use more sophisticated NLP or ML
            
            # Keywords that indicate grievance intent
            grievance_keywords = [
                'complaint', 'issue', 'problem', 'wrong', 'error', 'mistake',
                'not working', 'ticket', 'status', 'check', 'verification',
                'verify', 'USER', 'user', 'TKT', 'tkt'
            ]
            
            # Check for user ID pattern
            if re.search(r'USER\d{3}', query, re.IGNORECASE):
                return "grievance"
            
            # Check for ticket ID pattern
            if re.search(r'TKT-\d{8}-\d{4}', query, re.IGNORECASE):
                return "grievance"
            
            # Check for grievance keywords
            for keyword in grievance_keywords:
                if keyword.lower() in query.lower():
                    return "grievance"
            
            # Default to eligibility
            return "eligibility"
        except Exception as e:
            logger.error(f"Error analyzing intent: {e}")
            return "eligibility"  # Default to eligibility on error
    
    async def process_query(self, query: str) -> str:
        """Process a user query through the appropriate MCP server."""
        try:
            # Analyze intent to determine which subsystem to use
            intent = await self.analyze_intent(query)
            logger.info(f"Query intent determined: {intent}")
            
            if intent == "grievance":
                # Process using Grievance subsystem
                return await self.process_grievance_query(query)
            else:
                # Process using Eligibility subsystem
                return await self.process_eligibility_query(query)
        except Exception as e:
            logger.error(f"Error processing query: {e}")
            return "I'm sorry, but I'm having trouble processing your request. Please try again."
    
    async def process_eligibility_query(self, query: str) -> str:
        """Process an eligibility-related query using the Eligibility MCP server."""
        logger.info("Processing eligibility query")
        
        try:
            # 1. Extract user details
            user_details = await self.eligibility_session.call_tool(
                "extract_user_details",
                {"query": query, "ctx": {}}
            )
            logger.info(f"Extracted user details: {user_details}")
            
            # 2. Search for programs
            program_ids = await self.eligibility_session.call_tool(
                "search_programs",
                {"query": query, "ctx": {}}
            )
            logger.info(f"Found {len(program_ids)} relevant programs")
            
            # 3. Analyze eligibility
            eligibility_results = await self.eligibility_session.call_tool(
                "analyze_eligibility",
                {"program_ids": program_ids, "user_profile": user_details, "ctx": {}}
            )
            logger.info("Completed eligibility analysis")
            
            # 4. Get eligibility response prompt
            prompt_result = await self.eligibility_session.get_prompt(
                "eligibility_response",
                {
                    "programs": eligibility_results.get("programs", []),
                    "analysis": eligibility_results.get("analysis", []),
                    "user_profile": user_details
                }
            )
            
            # 5. Format the response using Ollama
            messages = prompt_result.messages
            
            # If no programs found, give a simple response
            if not eligibility_results.get("programs"):
                return "I searched our database but couldn't find specific programs matching your criteria. Could you provide more details about your situation? For example, your income level, family size, or specific needs you're looking for assistance with."
            
            # Extract content from the first assistant message
            if messages and len(messages) > 0 and messages[0].get("role") == "assistant":
                content = messages[0].get("content", {})
                if isinstance(content, dict) and "text" in content:
                    return content["text"]
                elif isinstance(content, str):
                    return content
            
            # Fallback: Generate response with Ollama
            prompt_for_ollama = f"""
            Based on the user query: "{query}"
            
            I found these programs: {json.dumps(eligibility_results.get('programs', []), indent=2)}
            
            With this eligibility analysis: {json.dumps(eligibility_results.get('analysis', []), indent=2)}
            
            Provide a helpful, conversational response explaining these programs and the user's potential eligibility.
            """
            
            return await self.ollama_client.generate(prompt_for_ollama, self.SYSTEM_PROMPT)
            
        except Exception as e:
            logger.error(f"Error processing eligibility query: {e}")
            return "I'm sorry, but I encountered an issue while analyzing program eligibility. Could you please try again or rephrase your question?"
    
    async def process_grievance_query(self, query: str) -> str:
        """Process a grievance-related query using the Grievance MCP server."""
        logger.info("Processing grievance query")
        
        try:
            # 1. Check for USER ID
            user_id_result = await self.grievance_session.call_tool(
                "identify_user_id",
                {"query": query, "ctx": {}}
            )
            logger.info(f"User ID check result: {user_id_result}")
            
            # If USER ID found, verify and process accordingly
            if user_id_result.get("found", False):
                user_id = user_id_result.get("user_id")
                return await self.process_user_verification(user_id, query)
            
            # Check for ticket pattern for status check
            ticket_match = re.search(r'TKT-\d{8}-\d{4}', query, re.IGNORECASE)
            if ticket_match:
                ticket_id = ticket_match.group(0)
                return await self.process_ticket_status(ticket_id)
            
            # Otherwise, prompt for USER ID
            return "To help with your request about benefits or to file a complaint, I'll need your USER ID. Your USER ID should be in the format USER### (for example, USER123). Could you please provide your USER ID so I can look up your information?"
            
        except Exception as e:
            logger.error(f"Error processing grievance query: {e}")
            return "I'm sorry, but I encountered an issue while processing your request. Could you please try again or provide your USER ID in the format USER### so I can help you better?"
    
    async def process_user_verification(self, user_id: str, query: str) -> str:
        """Process user verification and subsequent actions."""
        try:
            # Verify user
            verification_result = await self.grievance_session.call_tool(
                "verify_user",
                {"user_id": user_id, "ctx": {}}
            )
            logger.info(f"User verification result: {verification_result.get('verified', False)}")
            
            if verification_result.get("verified", False):
                # User verified - check if query contains complaint or status check
                if "status" in query.lower() or "check" in query.lower():
                    # Process as status check
                    status_result = await self.grievance_session.call_tool(
                        "check_status",
                        {"user_id": user_id, "ctx": {}}
                    )
                    
                    # Get status check response prompt
                    prompt_result = await self.grievance_session.get_prompt(
                        "status_check_response",
                        {"status_data": status_result}
                    )
                    
                    # Extract response from prompt
                    messages = prompt_result.messages
                    if messages and len(messages) > 0 and messages[0].get("role") == "assistant":
                        content = messages[0].get("content", {})
                        if isinstance(content, dict) and "text" in content:
                            return content["text"]
                        elif isinstance(content, str):
                            return content
                else:
                    # Process as complaint
                    user_details = verification_result.get("user_details", {})
                    program_details = verification_result.get("program_details", {})
                    
                    # Get user verification response prompt
                    prompt_result = await self.grievance_session.get_prompt(
                        "user_verification_response",
                        {"user_details": user_details, "program_details": program_details}
                    )
                    
                    # Extract response from prompt
                    messages = prompt_result.messages
                    if messages and len(messages) > 0 and messages[0].get("role") == "assistant":
                        content = messages[0].get("content", {})
                        if isinstance(content, dict) and "text" in content:
                            return content["text"]
                        elif isinstance(content, str):
                            return content
            else:
                # User verification failed
                prompt_result = await self.grievance_session.get_prompt(
                    "verification_failed_response",
                    {"user_id": user_id}
                )
                
                # Extract response from prompt
                messages = prompt_result.messages
                if messages and len(messages) > 0 and messages[0].get("role") == "assistant":
                    content = messages[0].get("content", {})
                    if isinstance(content, dict) and "text" in content:
                        return content["text"]
                    elif isinstance(content, str):
                        return content
            
            # Fallback response
            return f"I found your user ID ({user_id}), but I need more information about what you'd like assistance with. Are you checking your status, filing a complaint, or looking for information about benefits?"
            
        except Exception as e:
            logger.error(f"Error processing user verification: {e}")
            return "I'm sorry, but I encountered an issue while verifying your information. Could you please try again or contact our support team directly for assistance?"
    
    async def process_ticket_status(self, ticket_id: str) -> str:
        """Process a ticket status check."""
        try:
            # Check ticket status
            status_result = await self.grievance_session.call_tool(
                "check_status",
                {"user_id": "Unknown", "ticket_id": ticket_id, "ctx": {}}
            )
            
            # Get status check response prompt
            prompt_result = await self.grievance_session.get_prompt(
                "status_check_response",
                {"status_data": status_result}
            )
            
            # Extract response from prompt
            messages = prompt_result.messages
            if messages and len(messages) > 0 and messages[0].get("role") == "assistant":
                content = messages[0].get("content", {})
                if isinstance(content, dict) and "text" in content:
                    return content["text"]
                elif isinstance(content, str):
                    return content
            
            # Fallback response
            if status_result.get("found", False):
                return f"I found ticket {ticket_id} with status: {status_result.get('status', 'Unknown')}. You can check back later for updates."
            else:
                return f"I'm sorry, but I couldn't find any information for ticket {ticket_id}. Please double-check the ticket ID and try again."
            
        except Exception as e:
            logger.error(f"Error processing ticket status: {e}")
            return "I'm sorry, but I encountered an issue while checking the ticket status. Could you please try again or contact our support team directly for assistance?"
    
    async def process_complaint(self, user_id: str, complaint: str) -> str:
        """Process a complaint and create a ticket."""
        try:
            # 1. Verify user
            verification_result = await self.grievance_session.call_tool(
                "verify_user",
                {"user_id": user_id, "ctx": {}}
            )
            
            if not verification_result.get("verified", False):
                # User verification failed
                return f"I'm sorry, but I couldn't verify your user ID ({user_id}). Please double-check and try again."
            
            # 2. Process complaint
            complaint_result = await self.grievance_session.call_tool(
                "process_complaint",
                {"complaint": complaint, "ctx": {}}
            )
            
            # 3. Check if enough detail
            if not complaint_result.get("enough_detail", False):
                # Not enough detail, ask for more
                missing_info = complaint_result.get("missing_information", [])
                if missing_info:
                    return f"Thank you for your initial report. To better assist you, could you please provide some additional details? Specifically, I need information about: {', '.join(missing_info)}"
                else:
                    return "Thank you for your initial report. Could you please provide more details about the issue so I can better assist you?"
            
            # 4. Create ticket
            user_details = verification_result.get("user_details", {})
            program_details = verification_result.get("program_details", {})
            program_id = program_details.get("program_id", 0) if program_details else 0
            
            ticket_result = await self.grievance_session.call_tool(
                "create_ticket",
                {"user_id": user_id, "complaint": complaint, "program_id": program_id, "ctx": {}}
            )
            
            # 5. Get ticket creation response prompt
            prompt_result = await self.grievance_session.get_prompt(
                "ticket_creation_response",
                {
                    "ticket_details": ticket_result,
                    "user_details": user_details,
                    "complaint": complaint
                }
            )
            
            # Extract response from prompt
            messages = prompt_result.messages
            if messages and len(messages) > 0 and messages[0].get("role") == "assistant":
                content = messages[0].get("content", {})
                if isinstance(content, dict) and "text" in content:
                    return content["text"]
                elif isinstance(content, str):
                    return content
            
            # Fallback response
            return f"Thank you for reporting this issue. I've created ticket {ticket_result.get('ticket_id')} for you. A support agent will review your case within 3-5 business days."
            
        except Exception as e:
            logger.error(f"Error processing complaint: {e}")
            return "I'm sorry, but I encountered an issue while processing your complaint. Could you please try again or contact our support team directly for assistance?"
    
    async def close_sessions(self):
        """Close MCP sessions."""
        if self.eligibility_session:
            await self.eligibility_session.aclose()
        
        if self.grievance_session:
            await self.grievance_session.aclose()
        
        logger.info("Closed MCP sessions")

async def run_interactive(client: MCPClientApp):
    """Run the client in interactive mode."""
    try:
        await client.connect_to_servers()
        
        print("\n==== Social Benefits Assistant ====\n")
        print("Type 'quit' to exit, 'reset' to clear conversation history.")
        
        while True:
            user_input = input("\nYou: ")
            
            if user_input.lower() in ["quit", "exit", "bye"]:
                print("\nThank you for using the Social Benefits Assistant. Goodbye!")
                break
                
            if user_input.lower() == "reset":
                client.ollama_client.clear_history()
                print("Conversation history has been reset.")
                continue
            
            print("Processing...")
            response = await client.process_query(user_input)
            
            print(f"\nAssistant: {response}")
    finally:
        await client.close_sessions()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Social Benefits MCP Client")
    parser.add_argument("--eligibility-url", type=str, default="http://localhost:8000/sse", 
                      help="URL for the Eligibility MCP server")
    parser.add_argument("--grievance-url", type=str, default="http://localhost:8001/sse", 
                      help="URL for the Grievance MCP server")
    parser.add_argument("--ollama-url", type=str, default="http://localhost:11434", 
                      help="URL for the Ollama API")
    parser.add_argument("--model", type=str, default="llama2:8b", 
                      help="Ollama model to use")
    
    args = parser.parse_args()
    
    client = MCPClientApp(
        eligibility_url=args.eligibility_url,
        grievance_url=args.grievance_url,
        ollama_url=args.ollama_url,
        model=args.model
    )
    
    anyio.run(run_interactive, client)