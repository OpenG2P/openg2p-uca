import json
import datetime
import logging
import re  # Explicitly import re module at the top
from typing import Dict, List, Any, Optional

# Set up logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('SocialBenefits-MCP')

class MCPServer:
    """Model Context Protocol (MCP) server for managing context in conversations."""
    
    def __init__(self):
        """Initialize the MCP Server."""
        # Thread contexts store
        self.thread_contexts = {}
        logger.info("MCP Server initialized")
    
    def get_thread_context(self, thread_id: str) -> Dict:
        """Get or initialize a thread context."""
        if thread_id not in self.thread_contexts:
            # Initialize a new thread context with the persona
            logger.info(f"Creating new thread context for thread_id: {thread_id}")
            self.thread_contexts[thread_id] = {
                "conversation_history": [],
                "retrieved_programs": [],
                "user_profile": {},
                "tool_execution_history": [],
                "persona": {
                    "tone": "friendly and supportive",
                    "speech_patterns": ["uses contractions", "asks occasional questions", "expresses empathy"],
                    "personality_traits": ["helpful", "encouraging", "warm"]
                },
                # Add grievance context
                "grievance_context": {
                    "active": False,
                    "stage": None,
                    "user_id": None,
                    "user_details": None,
                    "program_details": None,
                    "complaint_parts": [],
                    "ticket_id": None,
                    "enough_detail": False
                }
            }
        return self.thread_contexts[thread_id]
    
    def update_conversation_history(self, thread_id: str, role: str, content: str):
        """Add a message to the conversation history."""
        context = self.get_thread_context(thread_id)
        context["conversation_history"].append({
            "role": role,
            "content": content,
            "timestamp": datetime.datetime.now().isoformat()
        })
        logger.info(f"Added {role} message to conversation history for thread_id: {thread_id}")
    
    def record_tool_execution(self, thread_id: str, tool_name: str, inputs: Dict, outputs: Any):
        """Record a tool execution in the thread context."""
        context = self.get_thread_context(thread_id)
        context["tool_execution_history"].append({
            "tool": tool_name,
            "inputs": inputs,
            "outputs": outputs,
            "timestamp": datetime.datetime.now().isoformat()
        })
        logger.info(f"Recorded execution of tool '{tool_name}' for thread_id: {thread_id}")
        
        # Log a summary of the outputs
        if isinstance(outputs, list):
            logger.info(f"Tool output summary: {len(outputs)} items")
        elif isinstance(outputs, dict):
            logger.info(f"Tool output keys: {list(outputs.keys())}")
        else:
            logger.info(f"Tool output type: {type(outputs)}")
    
    def update_retrieved_programs(self, thread_id: str, programs: List[Dict]):
        """Store retrieved program information in the thread context."""
        context = self.get_thread_context(thread_id)
        
        # Add new programs while avoiding duplicates
        existing_program_ids = [p["id"] for p in context["retrieved_programs"]]
        new_programs = []
        for program in programs:
            if program["id"] not in existing_program_ids:
                context["retrieved_programs"].append(program)
                new_programs.append(program["id"])
        
        logger.info(f"Updated retrieved programs for thread_id: {thread_id}")
        logger.info(f"Added {len(new_programs)} new programs: {new_programs}")
        logger.info(f"Total programs in context: {len(context['retrieved_programs'])}")
    
    def update_user_profile(self, thread_id: str, profile_data: Dict):
        """Update user profile information in the thread context."""
        context = self.get_thread_context(thread_id)
        
        # Track what's being updated
        new_keys = []
        updated_keys = []
        
        for key, value in profile_data.items():
            if key not in context["user_profile"]:
                new_keys.append(key)
            elif context["user_profile"][key] != value:
                updated_keys.append(key)
        
        # Update the profile
        context["user_profile"].update(profile_data)
        
        logger.info(f"Updated user profile for thread_id: {thread_id}")
        if new_keys:
            logger.info(f"New profile attributes: {new_keys}")
        if updated_keys:
            logger.info(f"Updated profile attributes: {updated_keys}")
        logger.info(f"Current user profile: {context['user_profile']}")
    
    def update_grievance_context(self, thread_id: str, updates: Dict):
        """Update the grievance context in the thread context."""
        context = self.get_thread_context(thread_id)
        
        # Track what's being updated
        grievance_context = context["grievance_context"]
        new_keys = []
        updated_keys = []
        
        for key, value in updates.items():
            if key not in grievance_context or grievance_context[key] is None:
                new_keys.append(key)
            elif grievance_context[key] != value:
                updated_keys.append(key)
        
        # Update the grievance context
        grievance_context.update(updates)
        
        logger.info(f"Updated grievance context for thread_id: {thread_id}")
        if new_keys:
            logger.info(f"New grievance attributes: {new_keys}")
        if updated_keys:
            logger.info(f"Updated grievance attributes: {updated_keys}")
        logger.info(f"Current grievance state: {grievance_context['stage']}")
    
    def add_complaint_part(self, thread_id: str, complaint: str):
        """Add a part to the complaint in the grievance context."""
        context = self.get_thread_context(thread_id)
        context["grievance_context"]["complaint_parts"].append(complaint)
        logger.info(f"Added complaint part for thread_id: {thread_id}")
    
    def should_call_tools(self, thread_id: str, query: str, ollama_client) -> str:
        """Determine if tools should be called for a given query using prompt-based classification.
        
        Returns:
            str: "TOOLS", "CONTEXT", or "CLARIFICATION"
        """
        context = self.get_thread_context(thread_id)
        
        # Log the current state for debugging
        logger.info(f"Evaluating whether to call tools for query: '{query}'")
        logger.info(f"Thread has {len(context['tool_execution_history'])} previous tool executions")
        logger.info(f"User profile has {len(context['user_profile'])} attributes")
        logger.info(f"Context has {len(context['retrieved_programs'])} programs")
        
        # If active grievance context, we should call tools
        if context["grievance_context"]["active"]:
            logger.info("Decision: CALL TOOLS - Active grievance context")
            return "TOOLS"
        
        # Check for USER ID format which indicates a grievance
        user_id_match = re.search(r'USER\d{3}', query)
        if user_id_match:
            logger.info(f"Decision: CALL TOOLS - Found USER ID format: {user_id_match.group(0)}")
            # Activate grievance context
            self.update_grievance_context(thread_id, {"active": True, "stage": "identification"})
            return "TOOLS"
        
        # For EVERY message, run full classification
        classification_prompt = f"""
        Please classify this user message: "{query}"
        
        Analyze the user's intent carefully. Which of these categories best describes it:
        
        1. GREETING: Simple greetings or pleasantries (hello, hi, thanks, etc.)
        2. CASUAL: General questions not about benefits (how are you, what can you do, etc.)
        3. SUBSTANTIVE: Questions about benefit programs, eligibility, or application processes
        4. GRIEVANCE: Complaints, problems with benefits, issues with applications, or requests to report problems
        
        Respond with EXACTLY ONE of these words: GREETING, CASUAL, SUBSTANTIVE, or GRIEVANCE
        """
        
        classification_system_prompt = """You are a message classifier for a benefits assistance system.
        Focus on accurately determining if users need program information (SUBSTANTIVE) or are reporting problems (GRIEVANCE).
        Pay special attention to complaints, issues with applications, or mentions of problems with benefits."""
        
        try:
            classification = ollama_client.generate(
                classification_system_prompt, 
                classification_prompt,
                f"{thread_id}_classifier"
            ).strip().upper()
            
            logger.info(f"Message classification result: {classification}")
            
            # Extract just the classification word using more robust approach
            classification_match = re.search(r'(?:^|\n)\s*(GREETING|CASUAL|SUBSTANTIVE|GRIEVANCE)\s*(?:$|\n)', classification)
            if classification_match:
                classification = classification_match.group(1).strip()
                logger.info(f"Found explicit classification: {classification}")
            # Fallback: look for any of the words anywhere in the text
            elif "GREETING" in classification:
                classification = "GREETING"
            elif "CASUAL" in classification:
                classification = "CASUAL"
            elif "SUBSTANTIVE" in classification:
                classification = "SUBSTANTIVE"
            elif "GRIEVANCE" in classification:
                classification = "GRIEVANCE"
            else:
                # Unclear classification - ask for clarification
                logger.warning(f"Could not determine classification: '{classification}'")
                
                # Create a clarification prompt
                clarification_prompt = f"""
                I'm not quite sure what you're asking about. The user said: "{query}"
                
                Please respond by:
                1. Politely acknowledging that you're not sure if they're asking about benefit programs, reporting an issue, or something else
                2. Asking them to clarify if they want to:
                - Check eligibility for benefit programs
                - Report a problem or file a complaint
                - Check the status of an application or benefit
                3. Being helpful and friendly in your request for clarification
                
                Your response should be brief and conversational.
                """
                
                # Generate clarification response
                clarification_response = ollama_client.generate(
                    "You are a helpful social benefits assistant. Respond conversationally.",
                    clarification_prompt,
                    f"{thread_id}_clarification"
                )
                
                # Add this as an assistant message to the conversation history
                self.update_conversation_history(thread_id, "assistant", clarification_response)
                
                return "CLARIFICATION"
            
            logger.info(f"Final classification: {classification}")
            
            # Make sure we're using exact string comparison, not substring matching
            if classification == "GREETING" or classification == "CASUAL":
                # Only skip tools for greeting/casual if we have short conversation history
                # If we're deep in conversation, treat casual comments as follow-ups
                if len(context["conversation_history"]) <= 2:
                    logger.info("Decision: DON'T CALL TOOLS - Message is a greeting or casual question")
                    return "CONTEXT"
                else:
                    # In established conversations, use existing context for greeting/casual
                    logger.info("Decision: USE CONTEXT - Casual comment in existing conversation")
                    return "CONTEXT"
            elif classification == "SUBSTANTIVE":
                # For substantive queries, we might still use existing context
                # If no programs have been retrieved yet, call tools
                if not context["retrieved_programs"]:
                    logger.info("Decision: CALL TOOLS - No programs in context")
                    return "TOOLS"
                    
                # Use the LLM to decide if this query needs tools
                decision_prompt = f"""
                USER QUERY: "{query}"
                
                CONTEXT:
                - Programs already in context: {[p.get('name', f"Program {p.get('id')}") for p in context['retrieved_programs']]}
                - User profile: {json.dumps(context['user_profile'])}
                - Previous conversation: {[msg['content'] for msg in context['conversation_history'][-3:] if msg['role'] == 'user']}
                
                QUESTION: Should I call tools to get new information, or use existing context?
                
                Consider these factors:
                1. If the query is about programs we already have information on, use existing context
                2. If the query is asking for completely new information, call tools
                3. If the query is a simple follow-up or clarification, use existing context
                
                Respond with EXACTLY ONE WORD: "TOOLS" or "CONTEXT"
                """
                
                decision_system_prompt = "You are a decision support system. Make careful decisions about when to use tools vs. existing context."
                
                try:
                    decision = ollama_client.generate(
                        decision_system_prompt, 
                        decision_prompt,
                        f"{thread_id}_decision"
                    ).strip().upper()
                    
                    logger.info(f"Tool call decision: {decision}")
                    
                    if "CONTEXT" in decision:
                        logger.info("Decision: USE CONTEXT - LLM determined existing context is sufficient")
                        return "CONTEXT"
                    else:
                        logger.info("Decision: CALL TOOLS - LLM determined new information is needed")
                        return "TOOLS"
                except Exception as e:
                    logger.error(f"Error in decision making: {e}")
                    # Default to calling tools if decision fails
                    logger.info("Decision: CALL TOOLS - Decision making failed, defaulting to safety")
                    return "TOOLS"
            elif classification == "GRIEVANCE":
                logger.info("Decision: CALL TOOLS - Message is a grievance")
                # Activate grievance context
                self.update_grievance_context(thread_id, {"active": True, "stage": "identification"})
                return "TOOLS"
            else:
                # This code path should never be reached due to our handling above,
                # but keeping it as a safety check
                logger.warning(f"Unexpected classification value: '{classification}'. Asking user to clarify intent.")
                
                # Create a clarification prompt
                clarification_prompt = f"""
                I'm not quite sure what you're asking about. The user said: "{query}"
                
                Please respond by:
                1. Politely acknowledging that you're not sure if they're asking about benefit programs, reporting an issue, or something else
                2. Asking them to clarify if they want to:
                - Check eligibility for benefit programs
                - Report a problem or file a complaint
                - Check the status of an application or benefit
                3. Being helpful and friendly in your request for clarification
                
                Your response should be brief and conversational.
                """
                
                # Generate clarification response
                clarification_response = ollama_client.generate(
                    "You are a helpful social benefits assistant. Respond conversationally.",
                    clarification_prompt,
                    f"{thread_id}_clarification"
                )
                
                # Add this as an assistant message to the conversation history
                self.update_conversation_history(thread_id, "assistant", clarification_response)
                
                return "CLARIFICATION"
                
        except Exception as e:
            logger.error(f"Error in classification: {e}")
            # Generate clarification response for classification failures
            clarification_prompt = f"""
            I'm having trouble understanding your request. The user said: "{query}"
            
            Please respond by:
            1. Politely apologizing for not understanding their request clearly
            2. Asking them to rephrase their question, specifying if they want to:
            - Learn about benefit programs they might qualify for
            - Report a problem with their benefits
            - Check their application status
            3. Being helpful and friendly in your request for clarification
            
            Your response should be brief and conversational.
            """
            
            # Generate clarification response
            clarification_response = ollama_client.generate(
                "You are a helpful social benefits assistant. Respond conversationally.",
                clarification_prompt,
                f"{thread_id}_clarification"
            )
            
            # Add this as an assistant message to the conversation history
            self.update_conversation_history(thread_id, "assistant", clarification_response)
            
            return "CLARIFICATION"
    
    def determine_grievance_stage(self, thread_id: str, query: str) -> str:
        """Determine the current stage of the grievance process."""
        context = self.get_thread_context(thread_id)
        grievance_context = context["grievance_context"]
        current_stage = grievance_context["stage"]
        
        # If no stage is set, start with identification
        if not current_stage:
            return "identification"
        
        # Handle specific stages
        if current_stage == "identification":
            # Check if query contains a USER ID
            user_id_match = re.search(r'USER\d{3}', query)
            if user_id_match:
                # Found USER ID in the query
                user_id = user_id_match.group(0)
                # Store the user_id in context
                self.update_grievance_context(thread_id, {"user_id": user_id})
                # User provided ID, move to verification
                return "verification"
            else:
                # Stay in identification
                return "identification"
                
        elif current_stage == "verification":
            # Always progress to complaint after verification
            # But only if user_id exists in context
            if grievance_context.get("user_id"):
                return "complaint"
            else:
                # If somehow we're in verification without a user_id, go back to identification
                return "identification"
                
        elif current_stage == "complaint":
            # Check for status inquiry
            if any(phrase in query.lower() for phrase in ["status", "check status", "what is my status"]):
                return "status_check"
                
            # Check if user indicates they're done providing details
            # This is the critical part that needs fixing - properly recognize "no" as a signal to create a ticket
            done_phrases = ["no", "none", "that's all", "no more", "that is all", "nothing else", "that's it", "all done"]
            if any(phrase == query.lower().strip() for phrase in done_phrases):
                # Move to ticket creation regardless of enough_detail flag
                # This matches the behavior in the original GrievanceAgent
                return "ticket_creation"
            
            # Stay in complaint collection stage
            return "complaint"
            
        elif current_stage == "ticket_creation":
            # After ticket creation, we move to the follow-up stage
            return "follow_up"
            
        elif current_stage == "follow_up":
            # Check if user wants to report a new issue
            if any(phrase in query.lower() for phrase in ["new issue", "another problem", "different complaint", "yes", "another", "more"]):
                return "complaint"
            else:
                # Stay in follow-up
                return "follow_up"
                
        # Default to identification for any unexpected state
        return "identification"
    
    def get_relevant_context(self, thread_id: str) -> Dict:
        """Get the most relevant context for the current conversation."""
        context = self.get_thread_context(thread_id)
        
        # Create a compact version of context for the LLM
        relevant_context = {
            "conversation_history": context["conversation_history"][-5:],  # Last 5 exchanges
            "retrieved_programs": context["retrieved_programs"],
            "user_profile": context["user_profile"],
            "recent_tool_executions": context["tool_execution_history"][-3:],  # Last 3 tool executions
            "persona": context["persona"],
            "grievance_context": context["grievance_context"]
        }
        
        logger.info(f"Returning relevant context for thread_id: {thread_id}")
        logger.info(f"Context includes: {len(relevant_context['conversation_history'])} conversation messages")
        logger.info(f"Context includes: {len(relevant_context['retrieved_programs'])} programs")
        logger.info(f"Grievance active: {context['grievance_context']['active']}")
        
        return relevant_context
    
    def clear_thread(self, thread_id: str):
        """Clear a thread context."""
        if thread_id in self.thread_contexts:
            del self.thread_contexts[thread_id]
            logger.info(f"Cleared thread context for thread_id: {thread_id}")