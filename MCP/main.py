import json
import datetime
import argparse
import threading
import traceback
import logging
import os
import re

# Set up logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('SocialBenefits-Main')

from mcp_server import MCPServer
from tools import Tools
from typing import Dict, List, Any

# Import original components
from original_code import OllamaClient, SQLDatabaseTool
from original_grievance import GrievanceAgent

class SocialBenefitsMCP:
    """MCP-based social benefits assistant with tool-based architecture."""
    
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
        
        # Initialize shared components from original code
        self.ollama = OllamaClient(base_url=ollama_url, model=model, temperature=temperature)
        self.db_tool = SQLDatabaseTool(db_path)
        
        # Initialize the original grievance agent for reference
        # Note: We don't use this directly in the MCP flow, but it's here for reference/alternative use
        self.grievance_agent = GrievanceAgent(db_path=grievance_db_path)
        
        # Initialize grievance database - without creating tables
        self.grievance_db_tool = SQLDatabaseTool(grievance_db_path, validate_tables=False)
        
        # Initialize the MCP server
        self.mcp_server = MCPServer()
        
        # Initialize tools
        self.tools = Tools(
            db_tool=self.db_tool,
            ollama=self.ollama,
            faiss_index_path=faiss_index_path
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
        
        # Prompt for greeting responses
        self.greeting_prompt = """You are a warm, friendly Social Benefits Assistant. The user has just greeted you or asked a casual question.

Respond in a friendly, conversational manner, keeping these guidelines in mind:
1. Keep your response brief (1-3 sentences)
2. Be warm and welcoming
3. Mention that you can help with finding benefit programs, eligibility information, or application assistance
4. Mention that you can also help with reporting issues or filing grievances
5. Don't be overly formal or robotic
6. Use a conversational tone with contractions (like "I'm" instead of "I am")

Make the user feel comfortable asking about benefit programs without being pushy."""
        
        logger.info("SocialBenefitsMCP initialization complete")
    
    def process_query(self, query: str, thread_id: str = "default") -> str:
        """Process a user query using the MCP framework with enhanced classification."""
        try:
            logger.info(f"Processing query: '{query}'")
            
            # Add user message to conversation history
            self.mcp_server.update_conversation_history(thread_id, "user", query)
            
            # Get current context
            context = self.mcp_server.get_thread_context(thread_id)
            logger.info(f"Retrieved context for thread_id: {thread_id}")
            
            # Check if we're in active grievance handling mode
            grievance_active = context["grievance_context"]["active"]
            
            if grievance_active:
                logger.info("Processing as a grievance query")
                return self._process_grievance_query(query, thread_id, context)
            
            # Determine if we need to call tools or can use existing context
            # Use enhanced prompt-based classification via MCP server
            tool_decision = self.mcp_server.should_call_tools(thread_id, query, self.ollama)
            
            # Handle clarification requests
            if tool_decision == "CLARIFICATION":
                # The response has already been added to conversation history in should_call_tools
                # Just get the last assistant message and return it
                last_message = self.mcp_server.get_thread_context(thread_id)["conversation_history"][-1]
                return last_message["content"]
            
            # Additional logging to help debug classification issues
            logger.info(f"Tool decision for query '{query}': {tool_decision}")
            
            # Check if grievance context was activated during classification
            if not grievance_active and context["grievance_context"]["active"]:
                logger.info("Grievance context was activated during classification")
                return self._process_grievance_query(query, thread_id, context)
            
            # For GRIEVANCE decision, process as grievance directly
            if tool_decision == "GRIEVANCE":
                # Ensure grievance context is active
                if not context["grievance_context"]["active"]:
                    self.mcp_server.update_grievance_context(thread_id, {"active": True, "stage": "identification"})
                # Process as grievance
                return self._process_grievance_query(query, thread_id, context)
                
            # NEW: For COLLECT_INFO decision, ask for more user details before proceeding
            if tool_decision == "COLLECT_INFO":
                logger.info("Collecting additional user information before proceeding")
                
                # Review existing profile
                user_profile = context["user_profile"]
                
                # Create a prompt to ask for specific missing information
                collection_prompt = f"""
                The user has asked about program eligibility with this query: "{query}"
                
                Current user profile information:
                {json.dumps(user_profile, indent=2)}
                
                Create a friendly, conversational response that:
                1. Acknowledges their interest in finding eligible programs
                2. Explains that you need a bit more information to provide the best recommendations
                3. Asks about specific missing information such as:
                - Age or age group if not provided
                - Income level if not provided  
                - Marital status if not provided
                - Employment status if not provided
                - Household size/dependents if not provided
                - Any special circumstances (disabilities, veteran status, etc.)
                4. Explains why this information helps find the right programs
                5. Reassures them about privacy and that this helps provide better results
                
                Make it warm and conversational, not like filling out a form.
                """
                
                # Generate the information collection response
                collection_response = self.ollama.generate(
                    "You are a helpful social benefits assistant. Respond conversationally.",
                    collection_prompt,
                    f"{thread_id}_info_collection"
                )
                
                # Add to conversation history
                self.mcp_server.update_conversation_history(thread_id, "assistant", collection_response)
                return collection_response
            
            # Only treat as greeting if we explicitly decided to use context AND it's an early turn
            if tool_decision == "CONTEXT" and len(context["conversation_history"]) <= 2:
                # This is likely a greeting or casual question (first turn)
                logger.info("Handling as greeting or casual question")
                greeting_response = self.ollama.generate(
                    self.greeting_prompt,
                    f"USER: {query}",
                    f"{thread_id}_greeting"
                )
                
                # Add assistant message to conversation history
                self.mcp_server.update_conversation_history(thread_id, "assistant", greeting_response)
                return greeting_response
            
            if tool_decision == "TOOLS":
                logger.info("Executing tool chain for new information")
                
                # Execute the full tool chain
                # 1. Extract user details from query and conversation history
                user_details = self.tools.extract_user_details_tool(
                    query, 
                    context["conversation_history"]
                )
                
                # Record tool execution
                self.mcp_server.record_tool_execution(
                    thread_id, 
                    "extract_user_details_tool",
                    {"query": query}, 
                    user_details
                )
                
                # Update user profile with new details
                if user_details:
                    self.mcp_server.update_user_profile(thread_id, user_details)
                    logger.info(f"Updated user profile with new details: {user_details}")
                else:
                    logger.warning("No user details extracted from query")
                
                # 2. Search for relevant programs
                vector_results = self.tools.vector_search_tool(query)
                
                # Record tool execution
                self.mcp_server.record_tool_execution(
                    thread_id, 
                    "vector_search_tool",
                    {"query": query}, 
                    vector_results
                )
                
                if not vector_results:
                    logger.warning("No programs found in vector search")
                    # No programs found - generate a response asking for more information
                    no_results_prompt = f"""
                    The user asked: "{query}"
                    
                    We couldn't find specific programs matching this query. Please:
                    1. Let them know you don't have specific program matches
                    2. Ask for more details about their situation to help find appropriate programs
                    3. Suggest common categories of programs they might be interested in
                    4. Use a warm, friendly tone
                    """
                    
                    logger.info("Generating response for no program matches")
                    response = self.ollama.generate(self.system_prompt, no_results_prompt, thread_id)
                    
                    # Add assistant message to conversation history
                    self.mcp_server.update_conversation_history(thread_id, "assistant", response)
                    return response
                
                # 3. Get detailed program information
                program_ids = [result["id"] for result in vector_results]
                logger.info(f"Retrieving details for {len(program_ids)} programs: {program_ids}")
                program_details = self.tools.program_details_tool(program_ids)
                
                # Record tool execution
                self.mcp_server.record_tool_execution(
                    thread_id, 
                    "program_details_tool",
                    {"program_ids": program_ids}, 
                    program_details
                )
                
                # Check if we got any valid program details
                if not program_details:
                    logger.warning("No valid program details retrieved from database")
                    
                    # Generate a more informative response
                    no_details_prompt = f"""
                    The user asked: "{query}"
                    
                    We couldn't find specific program information in our database. Please:
                    1. Acknowledge their query about being a {context["user_profile"].get("age_group", "")} {context["user_profile"].get("marital_status", "")} {context["user_profile"].get("gender", "")}
                    2. Explain that you don't have specific program information available right now
                    3. Ask what types of benefits they're most interested in (healthcare, housing, financial assistance, etc.)
                    4. Use a warm, friendly tone
                    """
                    
                    logger.info("Generating response for missing program details")
                    response = self.ollama.generate(self.system_prompt, no_details_prompt, thread_id)
                    
                    # Add assistant message to conversation history
                    self.mcp_server.update_conversation_history(thread_id, "assistant", response)
                    return response
                
                # 4. Store retrieved programs in context
                self.mcp_server.update_retrieved_programs(thread_id, program_details)
                
                # 5. Analyze eligibility based on user profile
                logger.info("Analyzing eligibility based on user profile")
                eligibility_analysis = self.tools.analyze_eligibility_tool(
                    program_details,
                    context["user_profile"]
                )
                
                # Record tool execution
                self.mcp_server.record_tool_execution(
                    thread_id, 
                    "analyze_eligibility_tool",
                    {
                        "programs": program_details,
                        "user_profile": context["user_profile"]
                    }, 
                    eligibility_analysis
                )
                
                # 6. Format response in a conversational style
                logger.info("Formatting conversational response")
                response = self.tools.conversation_formatter_tool(
                    query,
                    program_details,
                    eligibility_analysis,
                    context["user_profile"],
                    context["persona"]
                )
                
                # Record tool execution
                self.mcp_server.record_tool_execution(
                    thread_id, 
                    "conversation_formatter_tool",
                    {
                        "query": query,
                        "programs": program_details,
                        "eligibility_analysis": eligibility_analysis,
                        "user_profile": context["user_profile"],
                        "persona": context["persona"]
                    }, 
                    response
                )
                
                # Log the generated response
                logger.info(f"Generated response length: {len(response)}")
                
                # Add assistant message to conversation history
                self.mcp_server.update_conversation_history(thread_id, "assistant", response)
                
                return response
                
            else:  # tool_decision == "CONTEXT"
                logger.info("Using existing context to answer follow-up question")
                
                # Get relevant context
                relevant_context = self.mcp_server.get_relevant_context(thread_id)
                
                # Create a prompt that includes existing information
                context_prompt = f"""
                USER QUERY: {query}
                
                USER PROFILE:
                {json.dumps(relevant_context["user_profile"], indent=2)}
                
                PREVIOUSLY RETRIEVED PROGRAMS:
                {json.dumps(relevant_context["retrieved_programs"], indent=2)}
                
                RECENT CONVERSATION:
                {json.dumps([{msg["role"]: msg["content"]} for msg in relevant_context["conversation_history"]], indent=2)}
                
                INSTRUCTIONS:
                1. This is a follow-up question about programs we've already discussed
                2. Use the existing program information to provide a helpful response
                3. Maintain a warm, conversational tone according to the persona
                4. Do not mention that you're using previously retrieved information
                5. Respond as naturally as a helpful friend would
                
                Your response should directly address their question using the information we already have.
                If they're asking about something we don't have information on, acknowledge that and offer
                to help find that information if they provide more details.
                """
                
                # Generate response using existing context
                logger.info("Generating response from existing context")
                response = self.ollama.generate(
                    self.system_prompt,
                    context_prompt,
                    thread_id
                )
                
                # Add assistant message to conversation history
                self.mcp_server.update_conversation_history(thread_id, "assistant", response)
                
                return response
                
        except Exception as e:
            logger.error(f"Error in process_query: {e}")
            logger.error(traceback.format_exc())
            
            # Return a friendly error message
            error_response = "I'm sorry, I seem to be having some technical difficulties right now. Could you try asking your question again, maybe phrasing it a bit differently?"
            
            # Add error response to conversation history
            self.mcp_server.update_conversation_history(thread_id, "assistant", error_response)
            
            return error_response
    
    def _process_grievance_query(self, query: str, thread_id: str, context: Dict) -> str:
        """Process a query in the grievance flow."""
        logger.info("Processing grievance query")
        
        # Determine current stage and next stage
        current_stage = context["grievance_context"]["stage"]
        
        # Special handling for USER ID in identification stage
        if current_stage == "identification":
            # Check if query matches USER ID pattern
            user_id_result = self.tools.identify_user_id_tool(query)
            
            # Record tool execution
            self.mcp_server.record_tool_execution(
                thread_id, 
                "identify_user_id_tool",
                {"query": query}, 
                user_id_result
            )
            
            if user_id_result["found"]:
                # Found a USER ID, save it and set stage to verification
                user_id = user_id_result["user_id"]
                logger.info(f"Extracted USER ID {user_id}, moving to verification stage")
                self.mcp_server.update_grievance_context(thread_id, {"user_id": user_id, "stage": "verification"})
                
                # Now handle verification directly without recursion
                return self._process_verification(user_id, thread_id, context)
            else:
                # No USER ID found, ask for it
                identification_prompt = """
                The user has indicated they have an issue or grievance with their benefits program.
                
                Please respond by:
                1. Acknowledging their concern
                2. Explaining that you'll need their USER ID to access their information
                3. Asking them to provide their USER ID in the format USER### (e.g., USER123)
                4. Being empathetic and reassuring
                
                Keep your response conversational and helpful.
                """
                
                logger.info("Generating identification response")
                response = self.ollama.generate(
                    self.system_prompt,
                    identification_prompt,
                    thread_id
                )
                
                # Add assistant message to conversation history
                self.mcp_server.update_conversation_history(thread_id, "assistant", response)
                return response
        
        # Special handling for "no" in complaint stage - direct transition to ticket creation
        if current_stage == "complaint" and query.lower().strip() in ["no", "none", "that's all", "no more", "that is all", "nothing else", "that's it", "all done"]:
            logger.info(f"User indicated they're done with complaint details: '{query}'")
            # Add this as another complaint part
            self.mcp_server.add_complaint_part(thread_id, query)
            # Move directly to ticket creation
            self.mcp_server.update_grievance_context(thread_id, {"stage": "ticket_creation"})
            # Process ticket creation
            return self._process_ticket_creation(thread_id, self.mcp_server.get_thread_context(thread_id))
        
        # For non-special cases, use the normal stage determination
        next_stage = self.mcp_server.determine_grievance_stage(thread_id, query)
        logger.info(f"Grievance flow: {current_stage} -> {next_stage}")
        
        # Update grievance stage
        self.mcp_server.update_grievance_context(thread_id, {"stage": next_stage})
        
        # Handle each stage appropriately (without recursion)
        if next_stage == "verification":
            # Get the user ID from context
            user_id = context["grievance_context"]["user_id"]
            return self._process_verification(user_id, thread_id, context)
            
        elif next_stage == "complaint":
            return self._process_complaint(query, thread_id, context)
            
        elif next_stage == "status_check":
            return self._process_status_check(thread_id, context)
            
        elif next_stage == "ticket_creation":
            return self._process_ticket_creation(thread_id, context)
            
        elif next_stage == "follow_up":
            return self._process_follow_up(query, thread_id, context)
        
        # Fallback for unexpected states
        logger.warning(f"Unexpected grievance stage: {next_stage}")
        
        # Reset grievance context
        self.mcp_server.update_grievance_context(thread_id, {"active": False, "stage": None})
        
        # Generate error response
        error_prompt = f"""
        There was an issue processing the user's grievance.
        
        Please respond by:
        1. Apologizing for the difficulty
        2. Explaining that there was a technical issue processing their request
        3. Asking them to try again
        4. Being empathetic and understanding
        
        Keep your response conversational and helpful.
        """
        
        logger.info("Generating error response for grievance handling")
        response = self.ollama.generate(
            self.system_prompt,
            error_prompt,
            thread_id
        )
        
        # Add assistant message to conversation history
        self.mcp_server.update_conversation_history(thread_id, "assistant", response)
        return response

    def _process_verification(self, user_id: str, thread_id: str, context: Dict) -> str:
        """Handle the verification stage of grievance processing."""
        # Verify the user
        verification_result = self.tools.verify_user_tool(user_id)
        
        # Record tool execution
        self.mcp_server.record_tool_execution(
            thread_id, 
            "verify_user_tool",
            {"user_id": user_id}, 
            verification_result
        )
        
        if verification_result["verified"]:
            # User verified, save details and move to complaint
            self.mcp_server.update_grievance_context(thread_id, {
                "user_details": verification_result["user_details"],
                "program_details": verification_result["program_details"],
                "stage": "complaint"
            })
            
            # Generate verification response
            response = self.tools.format_grievance_response_tool(
                "user_verification",
                verification_result["user_details"],
                verification_result["program_details"],
                persona=context["persona"]
            )
            
            # Record tool execution
            self.mcp_server.record_tool_execution(
                thread_id, 
                "format_grievance_response_tool",
                {
                    "response_type": "user_verification",
                    "user_details": verification_result["user_details"],
                    "program_details": verification_result["program_details"]
                }, 
                response
            )
        else:
            # User not verified
            verification_failed_prompt = f"""
            The user provided USER ID {user_id}, but we couldn't verify it in our system.
            
            Please respond by:
            1. Politely informing them that you couldn't find their USER ID in our system
            2. Asking them to double-check their USER ID and try again
            3. Suggesting they contact support directly if they continue to have issues
            4. Being empathetic and understanding
            
            Keep your response conversational and helpful.
            """
            
            logger.info("Generating verification failed response")
            response = self.ollama.generate(
                self.system_prompt,
                verification_failed_prompt,
                thread_id
            )
            
            # Return to identification stage
            self.mcp_server.update_grievance_context(thread_id, {"stage": "identification"})
        
        # Add assistant message to conversation history
        self.mcp_server.update_conversation_history(thread_id, "assistant", response)
        return response

    def _process_complaint(self, query: str, thread_id: str, context: Dict) -> str:
        """Handle the complaint collection stage of grievance processing."""
        # Check for "that's all" or similar phrases, including just "no"
        done_phrases = ["no", "none", "that's all", "no more", "that is all", "nothing else", "that's it", "all done"]
        if query.lower().strip() in done_phrases:
            logger.info(f"User indicated they're done with complaint details: '{query}'")
            # User is done providing details, update stage to ticket_creation
            self.mcp_server.update_grievance_context(thread_id, {"stage": "ticket_creation"})
            # Process ticket creation directly without recursion
            return self._process_ticket_creation(thread_id, self.mcp_server.get_thread_context(thread_id))
        
        # If this is a new complaint (not a follow-up), start fresh
        if not context["grievance_context"].get("complaint_parts"):
            # Add this as the first complaint part
            self.mcp_server.add_complaint_part(thread_id, query)
            
            # Process the complaint
            complaint_result = self.tools.process_complaint_tool(
                query, 
                [], 
                False
            )
            
            # Record tool execution
            self.mcp_server.record_tool_execution(
                thread_id, 
                "process_complaint_tool",
                {"complaint": query, "is_follow_up": False}, 
                complaint_result
            )
            
            # Update grievance context with complaint analysis
            self.mcp_server.update_grievance_context(thread_id, {
                "enough_detail": complaint_result["enough_detail"]
            })
            
            # Generate complaint collection response
            response = self.tools.format_grievance_response_tool(
                "complaint_collection",
                context["grievance_context"]["user_details"],
                context["grievance_context"]["program_details"],
                complaint=complaint_result["complaint"],
                complaint_analysis=complaint_result,
                persona=context["persona"]
            )
            
            # Record tool execution
            self.mcp_server.record_tool_execution(
                thread_id, 
                "format_grievance_response_tool",
                {
                    "response_type": "complaint_collection",
                    "complaint": complaint_result["complaint"]
                }, 
                response
            )
        else:
            # This is a follow-up to an existing complaint
            
            # Add this as another complaint part
            self.mcp_server.add_complaint_part(thread_id, query)
            
            # Get all complaint parts
            complaint_parts = context["grievance_context"]["complaint_parts"]
            
            # Process the complaint
            complaint_result = self.tools.process_complaint_tool(
                query, 
                complaint_parts[:-1] if len(complaint_parts) > 1 else [], 
                True
            )
            
            # Record tool execution
            self.mcp_server.record_tool_execution(
                thread_id, 
                "process_complaint_tool",
                {"complaint": query, "is_follow_up": True}, 
                complaint_result
            )
            
            # Update grievance context with complaint analysis
            self.mcp_server.update_grievance_context(thread_id, {
                "enough_detail": complaint_result["enough_detail"]
            })
            
            # Generate complaint collection response
            response = self.tools.format_grievance_response_tool(
                "complaint_collection",
                context["grievance_context"]["user_details"],
                context["grievance_context"]["program_details"],
                complaint=complaint_result["complaint"],
                complaint_analysis=complaint_result,
                persona=context["persona"]
            )
            
            # Record tool execution
            self.mcp_server.record_tool_execution(
                thread_id, 
                "format_grievance_response_tool",
                {
                    "response_type": "complaint_collection",
                    "complaint": complaint_result["complaint"]
                }, 
                response
            )
        
        # Add assistant message to conversation history
        self.mcp_server.update_conversation_history(thread_id, "assistant", response)
        return response

    def _process_status_check(self, thread_id: str, context: Dict) -> str:
        """Handle the status check stage of grievance processing."""
        # Get user details
        user_id = context["grievance_context"]["user_id"]
        user_details = context["grievance_context"]["user_details"]
        
        # Check status
        status_result = self.tools.check_status_tool(user_id)
        
        # Record tool execution
        self.mcp_server.record_tool_execution(
            thread_id, 
            "check_status_tool",
            {"user_id": user_id}, 
            status_result
        )
        
        # Generate status response
        if status_result["found"]:
            response = self.tools.format_grievance_response_tool(
                "status_check",
                user_details,
                status_result if status_result["type"] == "program" else None,
                persona=context["persona"]
            )
        else:
            # Status not found
            status_not_found_prompt = f"""
            The user asked about their status, but we couldn't retrieve it from our system.
            
            Please respond by:
            1. Politely informing them that you're having trouble retrieving their status information
            2. Assuring them that their USER ID ({user_id}) is valid in our system
            3. Asking if they'd like to report a different issue instead
            4. Being empathetic and apologetic about the technical difficulty
            
            Keep your response conversational and helpful.
            """
            
            response = self.ollama.generate(
                self.system_prompt,
                status_not_found_prompt,
                thread_id
            )
        
        # Return to complaint stage after status check
        self.mcp_server.update_grievance_context(thread_id, {"stage": "complaint"})
        
        # Add assistant message to conversation history
        self.mcp_server.update_conversation_history(thread_id, "assistant", response)
        return response

    def _process_ticket_creation(self, thread_id: str, context: Dict) -> str:
        """Handle the ticket creation stage of grievance processing."""
        # Create a ticket with the collected complaint
        user_id = context["grievance_context"]["user_id"]
        program_details = context["grievance_context"]["program_details"]
        program_id = program_details.get("program_id", 0) if program_details else 0
        complaint_parts = context["grievance_context"]["complaint_parts"]
        
        # Combine all complaint parts
        full_complaint = "\n".join(complaint_parts)
        
        # Create the ticket
        ticket_result = self.tools.create_ticket_tool(
            user_id,
            program_id,
            full_complaint
        )
        
        # Record tool execution
        self.mcp_server.record_tool_execution(
            thread_id, 
            "create_ticket_tool",
            {
                "user_id": user_id,
                "program_id": program_id,
                "complaint": full_complaint
            }, 
            ticket_result
        )
        
        # Update grievance context with ticket information
        self.mcp_server.update_grievance_context(thread_id, {
            "ticket_id": ticket_result.get("ticket_id"),
            "stage": "follow_up"
        })
        
        # Generate ticket creation response
        response = self.tools.format_grievance_response_tool(
            "ticket_creation",
            context["grievance_context"]["user_details"],
            context["grievance_context"]["program_details"],
            complaint=full_complaint,
            ticket_details=ticket_result,
            persona=context["persona"]
        )
        
        # Record tool execution
        self.mcp_server.record_tool_execution(
            thread_id, 
            "format_grievance_response_tool",
            {
                "response_type": "ticket_creation",
                "ticket_details": ticket_result
            }, 
            response
        )
        
        # Add assistant message to conversation history
        self.mcp_server.update_conversation_history(thread_id, "assistant", response)
        return response

    def _process_follow_up(self, query: str, thread_id: str, context: Dict) -> str:
        """Handle the follow-up stage after ticket creation."""
        # Check if user wants to report a new issue
        new_issue_phrases = ["new issue", "another problem", "different complaint", "yes", "another", "more"]
        if any(phrase in query.lower() for phrase in new_issue_phrases):
            # Reset grievance context but keep user information
            user_id = context["grievance_context"]["user_id"]
            user_details = context["grievance_context"]["user_details"]
            program_details = context["grievance_context"]["program_details"]
            
            # Update grievance context for a new complaint
            self.mcp_server.update_grievance_context(thread_id, {
                "active": True,
                "stage": "complaint",
                "user_id": user_id,
                "user_details": user_details,
                "program_details": program_details,
                "complaint_parts": [],
                "ticket_id": None,
                "enough_detail": False
            })
            
            # Generate new complaint prompt
            new_complaint_prompt = f"""
            The user wants to report a new issue after already submitting one complaint.
            
            Please respond by:
            1. Acknowledging that you're ready to help with another issue
            2. Asking them to describe their new issue or problem
            3. Being empathetic and supportive
            4. Mentioning that they can provide as much detail as possible
            
            Keep your response conversational and helpful.
            """
            
            logger.info("Generating new complaint prompt")
            response = self.ollama.generate(
                self.system_prompt,
                new_complaint_prompt,
                thread_id
            )
        else:
            # Generate follow-up response
            ticket_id = context["grievance_context"]["ticket_id"]
            
            follow_up_prompt = f"""
            The user has already submitted a complaint (Ticket: {ticket_id}) and is continuing the conversation.
            
            Please respond by:
            1. Acknowledging their message
            2. Reminding them that their ticket ({ticket_id}) is being processed
            3. Asking if there's anything else they need help with
            4. Mentioning they can check the status of their ticket later using their USER ID
            5. Being empathetic and supportive
            
            Keep your response conversational and helpful.
            """
            
            logger.info("Generating follow-up response")
            response = self.ollama.generate(
                self.system_prompt,
                follow_up_prompt,
                thread_id
            )
        
        # Add assistant message to conversation history
        self.mcp_server.update_conversation_history(thread_id, "assistant", response)
        return response
    
    def reset_conversation(self, thread_id: str = "default"):
        """Reset the conversation context."""
        logger.info(f"Resetting conversation for thread_id: {thread_id}")
        
        # Clear the MCP context
        self.mcp_server.clear_thread(thread_id)
        
        # Clear Ollama conversation histories
        self.ollama.clear_thread(thread_id)
        self.ollama.clear_thread(f"{thread_id}_classifier")
        self.ollama.clear_thread(f"{thread_id}_decision")
        self.ollama.clear_thread("eligibility_analysis")
        self.ollama.clear_thread("user_extraction")
        self.ollama.clear_thread("conversation_formatter")
        
        logger.info(f"Conversation reset complete for thread_id: {thread_id}")

def main():
    """Run the MCP-based social benefits assistant."""
    parser = argparse.ArgumentParser(description="MCP-based Social Benefits Assistant")
    parser.add_argument("--db", type=str, default="../program_db", help="Path to program database")
    parser.add_argument("--grievance-db", type=str, default="../grievance_db.sqlite", help="Path to grievance database")
    parser.add_argument("--index", type=str, default="../program_db_faiss/programs_index", help="Path to FAISS index")
    parser.add_argument("--model", type=str, default="deepseek-r1:8b", help="Ollama model name")
    parser.add_argument("--temp", type=float, default=0.1, help="Temperature for generation")
    parser.add_argument("--url", type=str, default="http://localhost:11434", help="Ollama API URL")
    
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