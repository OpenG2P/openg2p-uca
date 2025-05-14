"""
Social Benefits Assistant using Low-Level MCP Architecture.

This implements the main Social Benefits Assistant class using the Model Context Protocol.
"""

import anyio
import logging
import json
import re
from typing import Dict, Any, List, Optional

from mcp.server.lowlevel import Server, NotificationOptions
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.server.sse import SseServerTransport
from starlette.applications import Starlette
from starlette.routing import Mount, Route
import uvicorn

from conversation_manager import ConversationManager
from eligibility_subsystem import EligibilitySubsystem
from grievance_subsystem import GrievanceSubsystem
from utils import OllamaClient, SQLDatabaseTool

# Set up logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('SocialBenefits-MCP')

class SocialBenefitsMCP:
    """MCP-based social benefits assistant with modular subsystem architecture."""
    
    def __init__(
        self,
        db_path: str,
        grievance_db_path: str,
        faiss_index_path: str,
        model: str = "deepseek-r1:8b",
        temperature: float = 0.1,
        ollama_url: str = "http://localhost:11434"
    ):
        """Initialize the MCP-based assistant."""
        logger.info(f"Initializing MCP-based Social Benefits Assistant with model: {model}")
        
        # Create the low-level MCP server
        self.mcp_server = Server(
            name="SocialBenefitsAssistant",
            instructions="Social Benefits Assistant to help users find programs, check eligibility, and handle grievances."
        )
        
        # Initialize shared components
        self.ollama_client = OllamaClient(base_url=ollama_url, model=model, temperature=temperature)
        self.db_tool = SQLDatabaseTool(db_path)
        self.grievance_db_tool = SQLDatabaseTool(grievance_db_path, validate_tables=False)
        
        # Initialize conversation manager
        self.conversation_manager = ConversationManager()
        
        # Initialize subsystems
        self.eligibility_subsystem = EligibilitySubsystem(
            db_tool=self.db_tool,
            ollama_client=self.ollama_client,
            faiss_index_path=faiss_index_path,
            conversation_manager=self.conversation_manager
        )
        
        self.grievance_subsystem = GrievanceSubsystem(
            db_tool=self.grievance_db_tool,
            ollama_client=self.ollama_client,
            conversation_manager=self.conversation_manager
        )
        
        # Define the main system prompt
        self.system_prompt = """You are a Social Benefits Assistant that helps users find and understand benefit programs they may be eligible for.

Your primary responsibilities:
1. Help users identify relevant social benefit programs based on their situation
2. Provide accurate information about program eligibility, benefits, and application processes
3. Respond to queries in a warm, conversational manner like a helpful friend would
4. Handle complaints or issues with existing benefits (grievances)

You have access to various tools that help you find information, but the user doesn't need to know about these tools. Just respond naturally as if the information comes from your own knowledge.

When handling program information:
- Explain eligibility requirements clearly
- Provide details about application processes
- Show empathy for the user's situation

When handling grievances:
- Verify user identity with care
- Collect detailed information about their issue
- Create formal tickets to track problems
- Provide clear next steps for resolution

If the user asks about something unrelated to benefits:
- Respond briefly and naturally to acknowledge their question
- Gently steer the conversation back to how you can help with social benefit programs
- Never be dismissive or robotic in your redirection

Remember to maintain a warm, friendly tone throughout the conversation. Use natural language patterns, show empathy, and make the user feel supported in navigating complex benefit systems."""
        
        # Register MCP handlers
        self._register_handlers()
        
        logger.info("SocialBenefitsMCP initialization complete")
    
    def _register_handlers(self):
        """Register handlers for MCP protocol requests."""
        # Register tool handlers
        self.mcp_server.list_tools()(self.list_tools)
        self.mcp_server.call_tool()(self.call_tool)
        
        # Register prompt handlers
        self.mcp_server.list_prompts()(self.list_prompts)
        self.mcp_server.get_prompt()(self.get_prompt)
    
    async def list_tools(self) -> List[Dict]:
        """List all available tools."""
        return [
            # Orchestration tools
            {
                "name": "analyze_query_intent",
                "description": "Analyze the intent and determine how to route a query",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "The user query"},
                        "thread_id": {"type": "string", "description": "Thread ID for conversation context"}
                    },
                    "required": ["query", "thread_id"]
                }
            },
            # Eligibility subsystem tools
            {
                "name": "extract_user_details",
                "description": "Extract user details from query and conversation history",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "The user query"},
                        "thread_id": {"type": "string", "description": "Thread ID for conversation context"}
                    },
                    "required": ["query", "thread_id"]
                }
            },
            {
                "name": "search_programs", 
                "description": "Search for programs based on user query",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "The search query"}
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "analyze_eligibility",
                "description": "Analyze user eligibility for programs",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "program_ids": {"type": "array", "items": {"type": "integer"}, "description": "List of program IDs"},
                        "user_profile": {"type": "object", "description": "User profile information"}
                    },
                    "required": ["program_ids"]
                }
            },
            # Grievance subsystem tools
            {
                "name": "identify_user_id",
                "description": "Identify if a query contains a valid USER ID", 
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "The user query"}
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "verify_user",
                "description": "Verify user ID and retrieve user details",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "user_id": {"type": "string", "description": "User ID in format USER###"}
                    },
                    "required": ["user_id"]
                }
            },
            {
                "name": "process_complaint",
                "description": "Process a user complaint",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "complaint": {"type": "string", "description": "The complaint text"},
                        "previous_parts": {"type": "array", "items": {"type": "string"}, "description": "Previous parts of the complaint"},
                        "is_follow_up": {"type": "boolean", "description": "Whether this is a follow-up to an existing complaint"}
                    },
                    "required": ["complaint"]
                }
            },
            {
                "name": "create_ticket",
                "description": "Create a support ticket for a complaint",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "user_id": {"type": "string", "description": "User ID in format USER###"},
                        "program_id": {"type": "integer", "description": "Program ID"},
                        "complaint": {"type": "string", "description": "The complaint text"}
                    },
                    "required": ["user_id", "complaint"]
                }
            },
            {
                "name": "check_status",
                "description": "Check the status of a program enrollment or ticket",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "user_id": {"type": "string", "description": "User ID in format USER###"},
                        "ticket_id": {"type": "string", "description": "Optional ticket ID to check"}
                    },
                    "required": ["user_id"]
                }
            },
            # Response formatting tool
            {
                "name": "format_response",
                "description": "Format a response based on query type and retrieved information",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "The original user query"},
                        "thread_id": {"type": "string", "description": "Thread ID for conversation context"},
                        "response_type": {"type": "string", "enum": ["eligibility", "grievance", "clarification", "followup"]},
                        "subtype": {"type": "string", "description": "Subtype of response (e.g., verification, complaint, status_check)"},
                        "data": {"type": "object", "description": "Data for response formatting"}
                    },
                    "required": ["query", "thread_id", "response_type"]
                }
            }
        ]
    
    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> List[Dict]:
        """Call a tool by name with arguments."""
        logger.info(f"Tool call: {name} with arguments: {arguments}")
        
        # Query intent analysis - the core router for our system
        if name == "analyze_query_intent":
            result = await self._analyze_query_intent(arguments["query"], arguments["thread_id"])
            return [{"type": "text", "text": result}]
        
        # Eligibility subsystem tools
        elif name in ["extract_user_details", "search_programs", "analyze_eligibility"]:
            result = await self.eligibility_subsystem.call_tool(name, arguments)
            return [{"type": "text", "text": result}]
        
        # Grievance subsystem tools
        elif name in ["identify_user_id", "verify_user", "process_complaint", "create_ticket", "check_status"]:
            result = await self.grievance_subsystem.call_tool(name, arguments)
            return [{"type": "text", "text": result}]
        
        # Response formatting
        elif name == "format_response":
            result = await self._format_response(
                arguments["query"],
                arguments["thread_id"],
                arguments["response_type"],
                arguments.get("subtype", "general"),
                arguments.get("data", {})
            )
            return [{"type": "text", "text": result}]
        
        else:
            # Unknown tool
            logger.error(f"Unknown tool: {name}")
            return [{"type": "text", "text": f"Error: Unknown tool '{name}'"}]
    
    async def list_prompts(self) -> List[Dict]:
        """List available prompts."""
        return [
            {
                "name": "clarification",
                "description": "Request clarification from the user",
                "arguments": [
                    {"name": "query", "description": "The original query", "required": True}
                ]
            },
            {
                "name": "grievance_identification",
                "description": "Request user ID for grievance processing",
                "arguments": []
            },
            {
                "name": "grievance_complaint",
                "description": "Collect complaint details",
                "arguments": [
                    {"name": "user_name", "description": "User's name", "required": True},
                    {"name": "program_name", "description": "Program name", "required": True}
                ]
            },
            {
                "name": "eligibility_info",
                "description": "Explain program eligibility",
                "arguments": [
                    {"name": "program_name", "description": "Name of the program", "required": True},
                    {"name": "eligibility_criteria", "description": "Eligibility criteria", "required": True}
                ]
            }
        ]
    
    async def get_prompt(self, name: str, arguments: Optional[Dict[str, str]] = None) -> Dict:
        """Get a prompt by name with arguments."""
        if arguments is None:
            arguments = {}
        
        logger.info(f"Getting prompt: {name} with arguments: {arguments}")
        
        if name == "clarification":
            query = arguments.get("query", "")
            return {
                "messages": [
                    {
                        "role": "assistant",
                        "content": {
                            "type": "text",
                            "text": f"""I'd like to help you with social benefits programs, but I need a bit more clarity.

Based on your question: "{query}"

Could you please provide more details about:
- What specific type of benefit or assistance you're looking for
- Any particular circumstances or needs you have
- What specific information would be most helpful for you

This will help me provide you with the most relevant information about available programs."""
                        }
                    }
                ]
            }
            
        elif name == "grievance_identification":
            return {
                "messages": [
                    {
                        "role": "assistant",
                        "content": {
                            "type": "text",
                            "text": """I understand you need assistance with an issue related to your benefits. To help you properly, I'll need your USER ID to access your account information.

Your USER ID should be in the format USER### (for example, USER123).

Could you please provide your USER ID so I can look up your information?"""
                        }
                    }
                ]
            }
            
        elif name == "grievance_complaint":
            user_name = arguments.get("user_name", "")
            program_name = arguments.get("program_name", "")
            
            return {
                "messages": [
                    {
                        "role": "assistant",
                        "content": {
                            "type": "text",
                            "text": f"""Thank you for verifying your information, {user_name}.

I can see you're enrolled in the {program_name} program. I'd like to help address any issues you're experiencing.

Could you please describe the problem you're having in detail? The more specific information you can provide, the better we can assist you."""
                        }
                    }
                ]
            }
            
        elif name == "eligibility_info":
            program_name = arguments.get("program_name", "")
            eligibility_criteria = arguments.get("eligibility_criteria", "")
            
            return {
                "messages": [
                    {
                        "role": "assistant",
                        "content": {
                            "type": "text",
                            "text": f"""Based on what you've shared, here's information about the {program_name} program:

To qualify for this program, you would need to meet these eligibility requirements:
{eligibility_criteria}

Would you like more information about how to apply for this program?"""
                        }
                    }
                ]
            }
            
        else:
            # Unknown prompt
            logger.warning(f"Unknown prompt: {name}")
            return {
                "messages": [
                    {
                        "role": "assistant",
                        "content": {
                            "type": "text",
                            "text": "I'm sorry, I couldn't find the prompt you requested."
                        }
                    }
                ]
            }

    async def _analyze_query_intent(self, query: str, thread_id: str) -> str:
        """
        Analyze a query's intent and determine routing.
        
        This is the central decision-making component that routes queries
        to the appropriate subsystem and determines if they're follow-ups.
        """
        # Get current context
        context = self.conversation_manager.get_thread_context(thread_id)
        
        # Check if this is a follow-up to a previous message
        is_followup = False
        needs_new_info = True
        
        # Only check for follow-up if we have prior conversation
        if len(context.get("conversation_history", [])) > 1:
            followup_result = await self._detect_followup(query, context, thread_id)
            is_followup = followup_result.get("is_followup", False)
            needs_new_info = followup_result.get("needs_new_info", True)
        
        # Check for active grievance context
        if context.get("grievance_context", {}).get("active", False):
            # Already in grievance flow, continue there
            return json.dumps({
                "intent": "grievance",
                "confidence": 0.9,
                "is_followup": is_followup,
                "should_use_tools": True
            })
        
        # Check if query is a USER ID format - fast path to grievance
        user_id_result = await self.grievance_subsystem.identify_user_id(query)
        try:
            user_id_data = json.loads(user_id_result)
            if user_id_data.get("found", False):
                # Activate grievance context
                self.conversation_manager.update_grievance_context(
                    thread_id,
                    {
                        "active": True,
                        "stage": "identification",
                        "user_id": user_id_data.get("user_id")
                    }
                )
                
                return json.dumps({
                    "intent": "grievance",
                    "confidence": 0.9,
                    "is_followup": False,
                    "should_use_tools": True
                })
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse user_id_result as JSON: {user_id_result}")
        
        # Check if this is a follow-up and we have enough context
        if is_followup and not needs_new_info:
            # Use existing context to answer
            return json.dumps({
                "intent": "followup",
                "confidence": 0.8,
                "is_followup": True,
                "should_use_tools": False
            })
        
        # For all other queries, use LLM to analyze intent
        intent_analysis = await self._analyze_intent(query, context)
        
        # Check if query is a grievance
        if intent_analysis.get("primary_intent") == "grievance":
            # Activate grievance context
            self.conversation_manager.update_grievance_context(
                thread_id,
                {
                    "active": True,
                    "stage": "identification"
                }
            )
            
            return json.dumps({
                "intent": "grievance",
                "confidence": intent_analysis.get("confidence", 0.7),
                "is_followup": is_followup,
                "should_use_tools": True
            })
        
        # Check if query is unclear
        if intent_analysis.get("confidence", 0) < 0.6:
            return json.dumps({
                "intent": "unclear",
                "confidence": intent_analysis.get("confidence", 0.3),
                "is_followup": False,
                "should_use_tools": False
            })
        
        # Default to eligibility/program info intent
        return json.dumps({
            "intent": intent_analysis.get("primary_intent", "program_info"),
            "confidence": intent_analysis.get("confidence", 0.7),
            "is_followup": is_followup,
            "should_use_tools": True
        })
    
    async def _detect_followup(self, query: str, context: Dict, thread_id: str) -> Dict:
        """
        Detect if a query is a follow-up to previous conversation.
        
        Uses LLM to analyze the query in context of the conversation history.
        """
        recent_messages = context.get("conversation_history", [])[-3:]
        
        # Create prompt for follow-up detection
        prompt = f"""CONVERSATION HISTORY:
{recent_messages}

NEW QUERY: "{query}"

Is this query a follow-up to the previous conversation? Answer with JSON:
{{
  "is_followup": true/false,
  "confidence": 0-1 (how confident are you),
  "intent": "program_info"/"status_check"/"grievance"/"greeting",
  "needs_new_info": true/false (does answering require new information)
}}

If the query asks about a completely new topic, it's not a follow-up.
If it refers to something mentioned earlier or asks for more details, it's a follow-up.
If it uses pronouns like "it", "this program", "that", it's likely a follow-up.
"""
        
        # Use DETECT system prompt specifically for follow-up detection
        response = self.ollama_client.generate(
            "You are a follow-up detection system. Return only valid JSON.",
            prompt,
            f"{thread_id}_followup_analysis"
        )
        
        try:
            # Extract JSON response from LLM output
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group(0))
                return result
            else:
                logger.warning("Could not extract JSON from follow-up detection response")
                return {
                    "is_followup": False,
                    "confidence": 0.0,
                    "intent": "unknown",
                    "needs_new_info": True
                }
                
        except Exception as e:
            logger.error(f"Error in follow-up detection: {e}")
            return {
                "is_followup": False,
                "confidence": 0.0,
                "intent": "unknown",
                "needs_new_info": True
            }
    
    async def _analyze_intent(self, query: str, context: Dict) -> Dict:
        """
        Analyze the intent of a query.
        
        Uses LLM to classify the query intent and extract entities.
        """
        # Create prompt for intent analysis
        prompt = f"""You are an intent analysis system for a Social Benefits Assistant. Your task is to understand the user's intent and classify it appropriately.

Analyze this user query: "{query}"

Classify the intent and respond in JSON format with these fields:

1. primary_intent: ONE of ["greeting", "program_info", "status_check", "grievance", "unclear"]
   - "greeting": Simple greetings, hellos, or initial contact
   - "program_info": Questions about benefits, eligibility, or available programs
   - "status_check": Queries about application status, tracking, or updates
   - "grievance": Complaints, issues, or problems with benefits
   - "unclear": Ambiguous queries or when user hasn't specified their needs

2. confidence: number between 0-1 indicating how confident you are in this classification
   - Use high confidence (0.8-1.0) for clear intents
   - Use medium confidence (0.6-0.8) for somewhat clear intents
   - Use low confidence (0.3-0.6) for ambiguous queries
   - Use very low confidence (<0.3) for completely unclear queries

3. entities: {{
   "user_id": USER### format if present,
   "program_id": any program ID mentioned,
   "demographic_info": any demographic information like age, gender, marital status, income level, etc.
}}

Examples of how to classify:
- "hi" -> greeting, high confidence
- "hello there" -> greeting, high confidence
- "what programs can I get?" -> program_info, high confidence
- "tell me about benefits" -> program_info, high confidence
- "where is my application?" -> status_check, high confidence
- "i have a problem with my benefits" -> grievance, high confidence
- "help" -> unclear, low confidence
- "what can you do?" -> unclear, low confidence

Remember:
- Be conservative in your confidence scores
- When in doubt, classify as "unclear" with low confidence
- Only use high confidence when the intent is very clear
- Consider the natural flow of conversation
"""
        
        # Use ANALYZE system prompt for intent classification
        session_id = context['conversation_history'][0]['timestamp'] if context.get('conversation_history') else 'default'
        response = self.ollama_client.generate(
            "You are an intent analysis system that extracts structured information. Respond with valid JSON only.",
            prompt,
            f"{session_id}_intent_analysis"
        )
        
        try:
            # Extract JSON response
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group(0))
                return result
            else:
                logger.warning("Could not extract JSON from intent analysis response")
                return {
                    "primary_intent": "unclear",
                    "confidence": 0.3,
                    "entities": {}
                }
                
        except Exception as e:
            logger.error(f"Error in intent analysis: {e}")
            return {
                "primary_intent": "unclear",
                "confidence": 0.3,
                "entities": {}
            }
    
    async def _format_response(self, query: str, thread_id: str, response_type: str, subtype: str, data: Dict) -> str:
        """
        Format a response based on type and data.
        
        This is a central function for generating user-facing responses from structured data.
        """
        # Get persona from context
        context = self.conversation_manager.get_thread_context(thread_id)
        persona = context.get("persona", {
            "tone": "friendly and supportive",
            "speech_patterns": ["uses contractions", "asks occasional questions", "expresses empathy"],
            "personality_traits": ["helpful", "encouraging", "warm"]
        })
        
        # Switch based on response type
        if response_type == "eligibility":
            if subtype == "no_programs":
                # No programs found
                formatter_prompt = f"""
                USER QUERY: {query}
                
                USER PROFILE:
                {json.dumps(data.get("user_profile", {}), indent=2)}
                
                PERSONA TO USE:
                {json.dumps(persona, indent=2)}
                
                INSTRUCTIONS:
                1. The user asked about programs, but we couldn't find specific matches
                2. Let them know you don't have specific program matches
                3. Ask for more details about their situation to help find appropriate programs
                4. Suggest common categories of programs they might be interested in
                5. Use a warm, friendly tone according to the persona
                
                Your response should be natural and conversational, not mentioning any technical details about "no programs found" etc.
                """
            else:
                # Program details found
                formatter_prompt = f"""
                USER QUERY: {query}
                
                PROGRAM INFORMATION:
                {json.dumps(data.get("programs", []), indent=2)}
                
                ELIGIBILITY ANALYSIS:
                {json.dumps(data.get("eligibility_analysis", []), indent=2)}
                
                USER PROFILE:
                {json.dumps(data.get("user_profile", {}), indent=2)}
                
                PERSONA TO USE:
                {json.dumps(persona, indent=2)}
                
                INSTRUCTIONS:
                1. Respond as a helpful, friendly social benefits assistant
                2. Use a warm, conversational tone (not formal or bureaucratic)
                3. Present program information naturally as a human would
                4. Express things like "it looks like" or "based on what you've shared" instead of formal assessments
                5. Show empathy about the user's situation
                6. Break information into conversational chunks
                7. If appropriate, ask a follow-up question at the end
                8. DO NOT list eligibility criteria as bullet points
                9. DO NOT mention the tools or analysis process
                10. Make the response sound like a knowledgeable friend giving advice
                
                Your response should be in plain text, conversational format.
                """
        
        elif response_type == "grievance":
            if subtype == "verification":
                # User verification successful
                user_details = data.get("user_details", {})
                program_details = data.get("program_details", {})
                
                formatter_prompt = f"""
                USER DETAILS:
                {json.dumps(user_details, indent=2)}
                
                PROGRAM DETAILS:
                {json.dumps(program_details, indent=2)}
                
                PERSONA TO USE:
                {json.dumps(persona, indent=2)}
                
                INSTRUCTIONS:
                1. Acknowledge that you can see their enrollment information
                2. Ask them to describe what issue they're having with their program
                3. Be empathetic and professional
                4. Keep your response conversational and helpful
                
                Your response should be in plain text, conversational format.
                """
            
            elif subtype == "verification_failed":
                # User verification failed
                user_id = data.get("user_id", "")
                
                formatter_prompt = f"""
                USER ID: {user_id}
                
                PERSONA TO USE:
                {json.dumps(persona, indent=2)}
                
                INSTRUCTIONS:
                1. Politely inform them that you couldn't find their USER ID in our system
                2. Ask them to double-check their USER ID and try again
                3. Suggesting contacting support directly if they continue to have issues
                4. Be empathetic and understanding
                
                Your response should be in plain text, conversational format.
                """
            
            elif subtype == "complaint":
                # Complaint collection
                complaint_data = data.get("complaint", {})
                user_details = data.get("user_details", {})
                program_details = data.get("program_details", {})
                
                formatter_prompt = f"""
                USER DETAILS:
                {json.dumps(user_details, indent=2)}
                
                PROGRAM DETAILS:
                {json.dumps(program_details, indent=2)}
                
                COMPLAINT INFORMATION:
                {json.dumps(complaint_data, indent=2)}
                
                PERSONA TO USE:
                {json.dumps(persona, indent=2)}
                
                INSTRUCTIONS:
                1. Thank them for the information provided so far
                2. Ask if they have any additional details they'd like to add
                3. Let them know they can say "no" or "that's all" if they've shared everything
                4. Be empathetic and supportive
                5. Keep your response conversational
                
                Your response should be in plain text, conversational format.
                """
                
            elif subtype == "status_check":
                # Status check
                status_data = data.get("status_data", {})
                user_details = data.get("user_details", {})
                
                formatter_prompt = f"""
                USER DETAILS:
                {json.dumps(user_details, indent=2)}
                
                STATUS INFORMATION:
                {json.dumps(status_data, indent=2)}
                
                PERSONA TO USE:
                {json.dumps(persona, indent=2)}
                
                INSTRUCTIONS:
                1. Provide clear information about their current status
                2. Explain what this status means (if ACTIVE, PENDING, etc.)
                3. Ask if they have any concerns about their status
                4. Be helpful and conversational
                
                Your response should be in plain text, conversational format.
                """
            
            elif subtype == "ticket_creation":
                # Ticket creation
                ticket_details = data.get("ticket_details", {})
                user_details = data.get("user_details", {})
                program_details = data.get("program_details", {})
                complaint = data.get("complaint", "")
                
                formatter_prompt = f"""
                TICKET INFORMATION:
                {json.dumps(ticket_details, indent=2)}
                
                USER DETAILS:
                {json.dumps(user_details, indent=2)}
                
                PROGRAM DETAILS:
                {json.dumps(program_details, indent=2)}
                
                COMPLAINT:
                {complaint}
                
                PERSONA TO USE:
                {json.dumps(persona, indent=2)}
                
                INSTRUCTIONS:
                1. Thank the user for reporting their issue
                2. Inform them that a ticket has been created with the ticket ID
                3. Tell them a support agent will review their case within 3-5 business days
                4. Express that you were glad to help them today
                5. Ask if there's anything else they need assistance with
                6. Be empathetic and friendly but professional
                
                Your response should be in plain text, conversational format.
                """
            
            else:
                # Generic grievance response
                formatter_prompt = f"""
                USER QUERY: {query}
                
                PERSONA TO USE:
                {json.dumps(persona, indent=2)}
                
                INSTRUCTIONS:
                1. Respond to the user's grievance in a helpful, empathetic way
                2. Acknowledge their concern
                3. Provide clear next steps
                4. Use a warm, conversational tone
                
                Your response should be in plain text, conversational format.
                """
        
        elif response_type == "followup":
            # Follow-up using existing context
            formatter_prompt = f"""
            USER QUERY: {query}
            
            CONTEXT:
            {json.dumps(data.get("context", {}), indent=2)}
            
            INTENT: {data.get("intent", "general")}
            
            PERSONA TO USE:
            {json.dumps(persona, indent=2)}
            
            INSTRUCTIONS:
            1. This is a follow-up question about information we've already discussed
            2. Use the existing information to provide a helpful response
            3. Maintain a warm, conversational tone according to the persona
            4. Do not mention that you're using previously retrieved information
            5. Respond as naturally as a helpful friend would
            
            Your response should directly address their question using the information we already have.
            If they're asking about something we don't have information on, acknowledge that and offer
            to help find that information if they provide more details.
            """
        
        else:
            # Generic response
            formatter_prompt = f"""
            USER QUERY: {query}
            
            PERSONA TO USE:
            {json.dumps(persona, indent=2)}
            
            INSTRUCTIONS:
            1. Respond to the user's query in a helpful, friendly way
            2. Use a warm, conversational tone
            3. Be concise but thorough
            
            Your response should be in plain text, conversational format.
            """
        
        # Generate the response
        logger.info(f"Generating {response_type} response")
        
        # Use the LLM to format the response
        response = self.ollama_client.generate(
            "You are a helpful and friendly social benefits assistant. Respond conversationally.",
            formatter_prompt,
            f"{thread_id}_{response_type}_formatter"
        )
        
        return response
    
    def process_query(self, query: str, thread_id: str = "default") -> str:
        """
        Process a user query using the MCP framework with enhanced classification.
        
        This is the main entry point for the application.
        """
        try:
            logger.info(f"Processing query: '{query}'")
            
            # Add user message to conversation history
            self.conversation_manager.update_conversation_history(thread_id, "user", query)
            
            # Run synchronously via anyio
            return anyio.run(self._process_query_async, query, thread_id)
            
        except Exception as e:
            logger.error(f"Error in process_query: {e}")
            error_message = "I'm sorry, I seem to be having some technical difficulties. Could you please try again?"
            
            # Add error response to conversation history
            self.conversation_manager.update_conversation_history(thread_id, "assistant", error_message)
            
            return error_message
    
    async def _process_query_async(self, query: str, thread_id: str) -> str:
        """Asynchronous implementation of query processing."""
        try:
            # Step 1: Analyze query intent
            intent_result = await self.call_tool("analyze_query_intent", {
                "query": query,
                "thread_id": thread_id
            })
            
            # Parse the result
            decision = json.loads(intent_result[0]["text"])
            logger.info(f"Query decision: {decision}")
            
            # Step 2: Route based on intent
            if decision["intent"] == "greeting":
                # Handle greetings with a welcome message
                welcome_message = """Hello! I'm your Social Benefits Assistant. I can help you with:

1. Finding social benefit programs you may be eligible for
2. Checking your eligibility for specific programs
3. Filing grievances or checking the status of your applications

What would you like help with today?"""
                
                # Add assistant message to conversation history
                self.conversation_manager.update_conversation_history(thread_id, "assistant", welcome_message)
                return welcome_message
                
            elif decision["intent"] == "unclear":
                # Handle unclear queries with clarification prompt
                prompt_result = await self.get_prompt("clarification", {
                    "query": query
                })
                clarification_response = prompt_result["messages"][0]["content"]["text"]
                
                # Add assistant message to conversation history
                self.conversation_manager.update_conversation_history(thread_id, "assistant", clarification_response)
                return clarification_response
                
            elif decision["intent"] == "grievance":
                # Handle grievance queries
                response = await self._process_grievance_query(query, thread_id)
                return response
            
            elif decision["intent"] == "followup" and not decision["should_use_tools"]:
                # Use existing context to answer follow-up
                # Get context
                context = self.conversation_manager.get_thread_context(thread_id)
                
                # Format response using existing context
                response = await self._format_response(
                    query,
                    thread_id,
                    "followup",
                    "general",
                    {"context": context}
                )
                
                # Add assistant message to conversation history
                self.conversation_manager.update_conversation_history(thread_id, "assistant", response)
                return response
            
            else:
                # Process as eligibility or general query
                # Step 1: Extract user details from query and conversation history
                user_details_result = await self.call_tool("extract_user_details", {
                    "query": query,
                    "thread_id": thread_id
                })
                
                user_details = json.loads(user_details_result[0]["text"])
                
                # Update user profile with new details
                if user_details:
                    self.conversation_manager.update_user_profile(thread_id, user_details)
                
                # Step 2: Search for relevant programs
                search_result = await self.call_tool("search_programs", {
                    "query": query
                })
                
                program_ids = json.loads(search_result[0]["text"])
                
                if not program_ids:
                    # No programs found
                    response = await self._format_response(
                        query,
                        thread_id,
                        "eligibility",
                        "no_programs",
                        {"user_profile": self.conversation_manager.get_user_profile(thread_id)}
                    )
                    
                    # Add assistant message to conversation history
                    self.conversation_manager.update_conversation_history(thread_id, "assistant", response)
                    return response
                
                # Step 3: Analyze eligibility based on user profile
                eligibility_result = await self.call_tool("analyze_eligibility", {
                    "program_ids": program_ids,
                    "user_profile": self.conversation_manager.get_user_profile(thread_id)
                })
                
                eligibility_data = json.loads(eligibility_result[0]["text"])
                
                # Update retrieved programs in context
                self.conversation_manager.update_retrieved_programs(thread_id, eligibility_data["programs"])
                
                # Step 4: Format response
                response = await self._format_response(
                    query,
                    thread_id,
                    "eligibility",
                    "program_details",
                    {
                        "programs": eligibility_data["programs"],
                        "eligibility_analysis": eligibility_data["analysis"],
                        "user_profile": self.conversation_manager.get_user_profile(thread_id)
                    }
                )
                
                # Add assistant message to conversation history
                self.conversation_manager.update_conversation_history(thread_id, "assistant", response)
                return response
                
        except Exception as e:
            logger.error(f"Error in _process_query_async: {e}")
            import traceback
            logger.error(traceback.format_exc())
            error_message = "I'm sorry, I seem to be having some technical difficulties. Could you please try again?"
            
            # Add error response to conversation history
            self.conversation_manager.update_conversation_history(thread_id, "assistant", error_message)
            
            return error_message
    
    async def _process_grievance_query(self, query: str, thread_id: str) -> str:
        """Process a query in the grievance flow."""
        # Get current context
        context = self.conversation_manager.get_thread_context(thread_id)
        grievance_context = context.get("grievance_context", {})
        current_stage = grievance_context.get("stage", "identification")
        
        logger.info(f"Processing grievance query. Current stage: {current_stage}")
        
        # Handle based on current stage
        if current_stage == "identification":
            # Check for USER ID
            user_id_result = await self.call_tool("identify_user_id", {
                "query": query
            })
            user_id_data = json.loads(user_id_result[0]["text"])
            
            if user_id_data.get("found"):
                # Found USER ID, proceed to verification
                user_id = user_id_data["user_id"]
                logger.info(f"Found USER ID: {user_id}")
                
                # Update grievance context
                self.conversation_manager.update_grievance_context(
                    thread_id, 
                    {"user_id": user_id, "stage": "verification"}
                )
                
                # Process verification directly
                verification_result = await self.call_tool("verify_user", {
                    "user_id": user_id
                })
                verification_data = json.loads(verification_result[0]["text"])
                
                if verification_data.get("verified"):
                    # User verified, update context and proceed to complaint
                    self.conversation_manager.update_grievance_context(
                        thread_id,
                        {
                            "user_details": verification_data["user_details"],
                            "program_details": verification_data["program_details"],
                            "stage": "complaint"
                        }
                    )
                    
                    # Format verification response
                    response = await self._format_response(
                        query,
                        thread_id,
                        "grievance",
                        "verification",
                        {
                            "user_details": verification_data["user_details"],
                            "program_details": verification_data["program_details"]
                        }
                    )
                else:
                    # Verification failed
                    response = await self._format_response(
                        query,
                        thread_id,
                        "grievance",
                        "verification_failed",
                        {"user_id": user_id}
                    )
                    
                    # Return to identification stage
                    self.conversation_manager.update_grievance_context(
                        thread_id,
                        {"stage": "identification"}
                    )
            else:
                # No USER ID found, ask for it
                prompt_result = await self.get_prompt("grievance_identification")
                response = prompt_result["messages"][0]["content"]["text"]
        
        elif current_stage == "verification":
            # Should not reach here directly, but handle just in case
            user_id = grievance_context.get("user_id")
            if not user_id:
                # No user ID, go back to identification
                self.conversation_manager.update_grievance_context(
                    thread_id,
                    {"stage": "identification"}
                )
                
                # Ask for USER ID
                prompt_result = await self.get_prompt("grievance_identification")
                response = prompt_result["messages"][0]["content"]["text"]
            else:
                # Verify user
                verification_result = await self.call_tool("verify_user", {
                    "user_id": user_id
                })
                verification_data = json.loads(verification_result[0]["text"])
                
                if verification_data.get("verified"):
                    # User verified, update context and proceed to complaint
                    self.conversation_manager.update_grievance_context(
                        thread_id,
                        {
                            "user_details": verification_data["user_details"],
                            "program_details": verification_data["program_details"],
                            "stage": "complaint"
                        }
                    )
                    
                    # Format verification response
                    response = await self._format_response(
                        query,
                        thread_id,
                        "grievance",
                        "verification",
                        {
                            "user_details": verification_data["user_details"],
                            "program_details": verification_data["program_details"]
                        }
                    )
                else:
                    # Verification failed
                    response = await self._format_response(
                        query,
                        thread_id,
                        "grievance",
                        "verification_failed",
                        {"user_id": user_id}
                    )
                    
                    # Return to identification stage
                    self.conversation_manager.update_grievance_context(
                        thread_id,
                        {"stage": "identification"}
                    )
        
        elif current_stage == "complaint":
            # Check for completion phrases
            done_phrases = ["no", "none", "that's all", "no more", "that is all", "nothing else", "that's it", "all done"]
            if any(phrase == query.lower().strip() for phrase in done_phrases):
                # User is done providing details, move to ticket creation
                self.conversation_manager.update_grievance_context(
                    thread_id,
                    {"stage": "ticket_creation"}
                )
                
                # Process ticket creation
                return await self._process_ticket_creation(thread_id)
            
            # Check for status request
            status_phrases = ["status", "check status", "what is my status", "what's happening", "any updates", "progress"]
            if any(phrase in query.lower() for phrase in status_phrases):
                # User is asking about status, move to status check
                self.conversation_manager.update_grievance_context(
                    thread_id,
                    {"stage": "status_check"}
                )
                
                # Process status check
                return await self._process_status_check(thread_id)
            
            # Process the complaint
            user_id = grievance_context.get("user_id")
            complaint_parts = grievance_context.get("complaint_parts", [])
            is_follow_up = len(complaint_parts) > 0
            
            # Add this complaint part
            self.conversation_manager.add_complaint_part(thread_id, query)
            
            # Process the complaint
            complaint_result = await self.call_tool("process_complaint", {
                "complaint": query,
                "previous_parts": complaint_parts,
                "is_follow_up": is_follow_up
            })
            complaint_data = json.loads(complaint_result[0]["text"])
            
            # Update grievance context
            self.conversation_manager.update_grievance_context(
                thread_id,
                {"enough_detail": complaint_data.get("enough_detail", False)}
            )
            
            # Format complaint response
            response = await self._format_response(
                query,
                thread_id,
                "grievance",
                "complaint",
                {
                    "complaint": complaint_data,
                    "user_details": grievance_context.get("user_details"),
                    "program_details": grievance_context.get("program_details")
                }
            )
        
        elif current_stage == "status_check":
            # Process status check
            response = await self._process_status_check(thread_id)
        
        elif current_stage == "ticket_creation":
            # Process ticket creation
            response = await self._process_ticket_creation(thread_id)
        
        else:
            # Unknown stage, reset grievance context
            logger.warning(f"Unknown grievance stage: {current_stage}")
            
            # Reset grievance context
            self.conversation_manager.update_grievance_context(
                thread_id,
                {"active": False, "stage": None}
            )
            
            # Generate error response
            response = await self._format_response(
                query,
                thread_id,
                "grievance",
                "error",
                {}
            )
        
        # Add assistant message to conversation history
        self.conversation_manager.update_conversation_history(thread_id, "assistant", response)
        
        return response
    
    async def _process_status_check(self, thread_id: str) -> str:
        """Process a status check request."""
        # Get grievance context
        context = self.conversation_manager.get_thread_context(thread_id)
        grievance_context = context.get("grievance_context", {})
        user_id = grievance_context.get("user_id")
        
        if not user_id:
            logger.warning(f"No user ID found for status check in thread {thread_id}")
            
            # Ask for user ID
            prompt_result = await self.get_prompt("grievance_identification")
            response = prompt_result["messages"][0]["content"]["text"]
            
            # Update grievance context
            self.conversation_manager.update_grievance_context(
                thread_id,
                {"stage": "identification"}
            )
            
            return response
        
        # Check status
        status_result = await self.call_tool("check_status", {
            "user_id": user_id
        })
        status_data = json.loads(status_result[0]["text"])
        
        # Format status response
        response = await self._format_response(
            "status check",
            thread_id,
            "grievance",
            "status_check",
            {
                "status_data": status_data,
                "user_details": grievance_context.get("user_details")
            }
        )
        
        # Return to complaint stage after status check
        self.conversation_manager.update_grievance_context(
            thread_id,
            {"stage": "complaint"}
        )
        
        return response
    
    async def _process_ticket_creation(self, thread_id: str) -> str:
        """Process ticket creation for a grievance."""
        # Get grievance context
        context = self.conversation_manager.get_thread_context(thread_id)
        grievance_context = context.get("grievance_context", {})
        
        user_id = grievance_context.get("user_id")
        program_details = grievance_context.get("program_details", {})
        program_id = program_details.get("program_id", 0) if program_details else 0
        complaint_parts = grievance_context.get("complaint_parts", [])
        
        if not user_id or not complaint_parts:
            logger.warning(f"Missing user ID or complaint for ticket creation in thread {thread_id}")
            
            # Return to complaint stage
            self.conversation_manager.update_grievance_context(
                thread_id,
                {"stage": "complaint"}
            )
            
            # Generate error response
            response = await self._format_response(
                "ticket creation",
                thread_id,
                "grievance",
                "error",
                {}
            )
            
            return response
        
        # Combine all complaint parts
        full_complaint = "\n".join(complaint_parts)
        
        # Create the ticket
        ticket_result = await self.call_tool("create_ticket", {
            "user_id": user_id,
            "program_id": program_id,
            "complaint": full_complaint
        })
        ticket_data = json.loads(ticket_result[0]["text"])
        
        # Update grievance context
        self.conversation_manager.update_grievance_context(
            thread_id,
            {
                "ticket_id": ticket_data.get("ticket_id"),
                "stage": "follow_up"
            }
        )
        
        # Format ticket creation response
        response = await self._format_response(
            "ticket creation",
            thread_id,
            "grievance",
            "ticket_creation",
            {
                "ticket_details": ticket_data,
                "user_details": grievance_context.get("user_details"),
                "program_details": program_details,
                "complaint": full_complaint
            }
        )
        
        return response
    
    def reset_conversation(self, thread_id: str = "default"):
        """Reset the conversation context."""
        logger.info(f"Resetting conversation for thread_id: {thread_id}")
        
        # Clear the conversation context
        self.conversation_manager.clear_thread(thread_id)
        
        # # Clear Ollama conversation histories
        # self.ollama_client.clear_thread(thread_id)
        # self.ollama_client.clear_thread(f"{thread_id}_intent_analysis")
        # self.ollama_client.clear_thread(f"{thread_id}_followup_analysis")
        # self.ollama_client.clear_thread(f"{thread_id}_eligibility_formatter")
        # self.ollama_client.clear_thread(f"{thread_id}_grievance_formatter")
        
        logger.info(f"Conversation reset complete for thread_id: {thread_id}")
    
    def run(self, transport: str = "stdio"):
        """Run the MCP server with the specified transport."""
        # Set up server capabilities
        capabilities = self.mcp_server.get_capabilities(
            notification_options=NotificationOptions(
                resources_changed=True,
                tools_changed=True,
                prompts_changed=True
            ),
            experimental_capabilities={}
        )
        
        # Create initialization options
        init_options = InitializationOptions(
            server_name="SocialBenefitsAssistant",
            server_version="1.0.0",
            capabilities=capabilities,
            instructions="Social Benefits Assistant to help users find programs, check eligibility, and handle grievances."
        )
        
        if transport == "stdio":
            # Run with stdio transport
            anyio.run(self._run_stdio, init_options)
        else:
            # Run with SSE transport
            anyio.run(self._run_sse, init_options)
    
    async def _run_stdio(self, init_options):
        """Run with stdio transport."""
        async with stdio_server() as (read_stream, write_stream):
            await self.mcp_server.run(
                read_stream,
                write_stream,
                init_options
            )
    
    async def _run_sse(self, init_options):
        """Run with SSE transport."""
        sse = SseServerTransport("/messages/")
        
        async def handle_sse(request):
            async with sse.connect_sse(
                request.scope, request.receive, request._send
            ) as streams:
                await self.mcp_server.run(
                    streams[0],
                    streams[1],
                    init_options
                )
        
        app = Starlette(
            debug=True,
            routes=[
                Route("/sse", endpoint=handle_sse),
                Mount("/messages/", app=sse.handle_post_message),
            ],
        )
        
        uvicorn.run(app, host="0.0.0.0", port=8000)