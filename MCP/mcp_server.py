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



    def identify_query_intent(self, query: str, thread_id: str, ollama_client) -> Dict:
        """Identify the intent and key entities in a user query using the LLM."""
        intent_prompt = f"""
        Analyze this user query: "{query}"
        
        Extract the following information (respond in JSON format):
        
        1. primary_intent: ONE of ["greeting", "program_info", "status_check", "grievance", "unclear"]
        
        2. confidence: number between 0-1 indicating how confident you are in this classification
        
        3. entities: {{
        "user_id": USER### format if present,
        "program_id": any program ID mentioned,
        "reference_number": any application reference numbers,
        "status_keywords": any words indicating status tracking,
        "grievance_keywords": any words indicating problems or complaints,
        "demographic_info": {{
            "age_group": any age group mentioned (child, adult, senior, etc.),
            "marital_status": any marital status mentioned (single, married, divorced, etc.),
            "gender": any gender mentioned (male, female, etc.),
            "income": any income amount mentioned,
            "employment": any employment status mentioned,
            "location": any location mentioned,
            "disabilities": any disabilities mentioned,
            "household_size": any household size or dependents mentioned
        }}
        }}
        
        4. recommendations: {{
        "needs_clarification": true/false,
        "suggested_flow": one of ["program_search", "program_info_collection", "status_check", "grievance", "ask_clarification"],
        "has_sufficient_demographics": true/false
        }}
        
        Examples of status tracking phrases: "track application", "check status", "follow up", "where is my application"
        Examples of grievance phrases: "issue with", "problem", "not working", "wrong information", "complaint"
        
        If you detect a USER ID in format USER### (like USER123), this is likely a grievance or status check.
        If the query is about program eligibility and includes at least age/age_group and one other demographic detail, set has_sufficient_demographics to true.
        """

        
        # Generate entity analysis
        analysis_response = ollama_client.generate(
            "You are an intent analysis system that extracts structured information. Respond with valid JSON only.",
            intent_prompt,
            f"{thread_id}_intent_analysis"
        )
        
        # Extract JSON
        try:
            import re
            json_match = re.search(r'\{.*\}', analysis_response, re.DOTALL)
            if json_match:
                intent_data = json.loads(json_match.group(0))
                logger.info(f"Query intent analysis: {intent_data}")
                return intent_data
            else:
                logger.warning("Could not extract JSON from intent analysis")
                return {
                    "primary_intent": "unclear",
                    "confidence": 0.3,
                    "entities": {},
                    "recommendations": {
                        "needs_clarification": True,
                        "suggested_flow": "ask_clarification"
                    }
                }
        except Exception as e:
            logger.error(f"Error parsing intent analysis: {e}")
            return {
                "primary_intent": "unclear",
                "confidence": 0.0,
                "entities": {},
                "recommendations": {
                    "needs_clarification": True,
                    "suggested_flow": "ask_clarification"
                }
            }
    
    
    def should_call_tools(self, thread_id: str, query: str, ollama_client) -> str:
        """Determine if tools should be called for a given query using enhanced prompt-based classification."""
        context = self.get_thread_context(thread_id)
        
        # Log the current state for debugging
        logger.info(f"Evaluating whether to call tools for query: '{query}'")
        logger.info(f"Thread has {len(context['tool_execution_history'])} previous tool executions")
        logger.info(f"User profile has {len(context['user_profile'])} attributes")
        logger.info(f"Context has {len(context['retrieved_programs'])} programs")
        
        # If active grievance context, we should call tools
        if context["grievance_context"]["active"]:
            logger.info("Decision: CALL TOOLS - Active grievance context")
            return "GRIEVANCE"
        
        # Use the enhanced intent analysis
        intent_data = self.identify_query_intent(query, thread_id, ollama_client)
        
        # Log the detailed intent analysis
        logger.info(f"Intent analysis for query '{query}': {intent_data}")
        
        # Check for explicitly mentioned program IDs
        program_id = intent_data.get("entities", {}).get("program_id")
        if program_id:
            logger.info(f"Explicit program ID mentioned: {program_id}")
            # Store program ID in context for use by tools
            if "current_query" not in context:
                context["current_query"] = {}
            context["current_query"]["explicit_program_id"] = program_id
            
            # If program info is being requested for a specific ID, always call tools
            if intent_data.get("primary_intent") == "program_info":
                logger.info("Decision: CALL TOOLS - Specific program ID mentioned")
                return "TOOLS"
        
        # Extract and update demographic information
        demographic_info = intent_data.get("entities", {}).get("demographic_info", {})
        profile_updated = False
        
        if demographic_info:
            # Transform demographic info into user profile format
            profile_updates = {}
            
            if demographic_info.get("age_group"):
                profile_updates["age_group"] = demographic_info["age_group"]
            
            if demographic_info.get("marital_status"):
                profile_updates["marital_status"] = demographic_info["marital_status"]
                
            if demographic_info.get("gender"):
                profile_updates["gender"] = demographic_info["gender"]
                
            if demographic_info.get("income"):
                profile_updates["income_level"] = demographic_info["income"]
                
            if demographic_info.get("employment"):
                profile_updates["employment_status"] = demographic_info["employment"]
                
            if demographic_info.get("location"):
                profile_updates["location"] = demographic_info["location"]
                
            if demographic_info.get("disabilities"):
                profile_updates["disabilities"] = demographic_info["disabilities"]
                
            if demographic_info.get("household_size"):
                profile_updates["family_size"] = demographic_info["household_size"]
            
            # Update the user profile if we have any new information
            if profile_updates:
                self.update_user_profile(thread_id, profile_updates)
                logger.info(f"Updated user profile with demographic info: {profile_updates}")
                profile_updated = True
        
        # IMPORTANT: Check profile updates BEFORE confidence check
        # If profile was updated AND we have programs in context, call tools
        if profile_updated and len(context["retrieved_programs"]) > 0:
            logger.info("Decision: CALL TOOLS - Demographic follow-up to previous program search")
            return "TOOLS"
        
        # Extract user ID if present and activate grievance flow
        user_id = intent_data.get("entities", {}).get("user_id")
        if user_id:
            logger.info(f"Found USER ID: {user_id}")
            self.update_grievance_context(thread_id, {
                "active": True, 
                "stage": "identification",
                "user_id": user_id
            })
            return "GRIEVANCE"
        
        # Check if we have sufficient demographic info for program search
        has_sufficient_demographics = intent_data.get("recommendations", {}).get("has_sufficient_demographics", False)
        
        # If the profile now has demographic info, we should consider that sufficient
        if len(context["user_profile"]) >= 2 or has_sufficient_demographics:
            # Override the decision to TOOLS if we have enough demographic info for program_info intent
            if intent_data.get("primary_intent") == "program_info":
                logger.info("Decision: CALL TOOLS - Sufficient demographic information for program search")
                return "TOOLS"
        
        # Handle based on primary intent and confidence
        primary_intent = intent_data.get("primary_intent", "unclear")
        confidence = intent_data.get("confidence", 0.0)
        suggested_flow = intent_data.get("recommendations", {}).get("suggested_flow", "ask_clarification")
        
        # If low confidence but we updated profile info and have programs in context
        if (primary_intent == "unclear" or confidence < 0.6) and profile_updated and context["retrieved_programs"]:
            logger.info("Decision: CALL TOOLS - Low confidence query with demographic updates in program context")
            return "TOOLS"
        
        if confidence < 0.6 or primary_intent == "unclear":
            # Handle low confidence or unclear intent
            logger.info(f"Decision: CLARIFICATION - Low confidence ({confidence}) or unclear intent")
            
            # Create detailed clarification prompt based on what we detected
            entities = intent_data.get("entities", {})
            suggested_flow = intent_data.get("recommendations", {}).get("suggested_flow", "ask_clarification")
            
            clarification_prompt = f"""
            The user said: "{query}"
            
            Based on my analysis:
            - Detected status keywords: {entities.get("status_keywords", [])}
            - Detected grievance keywords: {entities.get("grievance_keywords", [])}
            - Detected reference numbers: {entities.get("reference_number", "None")}
            - Suggested flow: {suggested_flow}
            - Current user profile: {json.dumps(context["user_profile"], indent=2)}
            - Retrieved programs: {[p.get("name", f"Program {p.get('id')}") for p in context["retrieved_programs"]]}
            
            {f"Previous program search performed: {len(context['retrieved_programs'])} programs found." if context["retrieved_programs"] else "No previous program search performed."}
            
            I need to create a response that:
            
            1. Acknowledges the information they just provided (especially if demographic details)
            2. If they've provided new demographic information and we have programs in context, I should offer to refine their program search with the new details
            3. Otherwise, suggest options like:
            - Finding benefit programs they might qualify for
            - Checking application status (mentioning they'll need their USER ID)
            - Filing a complaint about an existing benefit
            4. Asks them to clarify what they'd like to do next
            
            Keep the response conversational and helpful, not overly formal.
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
        
        elif primary_intent == "grievance" or primary_intent == "status_check":
            # Activate grievance context for both grievances and status checks
            logger.info(f"Decision: GRIEVANCE - Detected {primary_intent} intent")
            self.update_grievance_context(thread_id, {"active": True, "stage": "identification"})
            return "GRIEVANCE"
        
        elif primary_intent == "program_info":
            # Check if we need to collect more user information before searching
            # Only do this if we don't already have enough profile information
            if (suggested_flow == "program_info_collection" and len(context["user_profile"]) < 2 
                and not has_sufficient_demographics):
                # Not enough user information yet - we should collect more
                logger.info("Decision: COLLECT_INFO - Need more user demographic information")
                return "COLLECT_INFO"
            
            # Continue with existing TOOLS vs CONTEXT decision for program info
            logger.info("Decision: Program info intent detected, determining if tools needed")
            
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
            4. If the user provided new demographic information, call tools
            
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
        
        elif primary_intent == "greeting":
            # Only skip tools for greeting if we have short conversation history
            # If we're deep in conversation, treat casual comments as follow-ups
            if len(context["conversation_history"]) <= 2:
                logger.info("Decision: CONTEXT - Message is a greeting in new conversation")
                return "CONTEXT"
            else:
                # In established conversations, use existing context for greeting
                logger.info("Decision: CONTEXT - Greeting in existing conversation")
                return "CONTEXT"
        
        # Default to calling tools if we can't determine intent
        logger.info("Decision: CALL TOOLS - Default decision due to unclassified intent")
        return "TOOLS"


    def determine_grievance_stage(self, thread_id: str, query: str) -> str:
        """Determine the current stage of the grievance process with enhanced understanding."""
        context = self.get_thread_context(thread_id)
        grievance_context = context["grievance_context"]
        current_stage = grievance_context["stage"]
        
        # If no stage is set, start with identification
        if not current_stage:
            return "identification"
        
        # Use LLM to understand the user's intent within the grievance flow
        grievance_stage_prompt = f"""
        CURRENT GRIEVANCE STAGE: {current_stage}
        USER MESSAGE: "{query}"
        
        Based on the user's message and the current grievance stage, determine the appropriate next stage.
        
        Current available stages:
        - identification: User needs to provide USER ID
        - verification: System needs to verify user identity
        - complaint: User is describing their issue/complaint
        - status_check: User wants to check status of existing grievance
        - ticket_creation: System should create a ticket
        - follow_up: Grievance has been addressed, handling follow-up
        
        Special cases to watch for:
        1. If current stage is "complaint" and user says anything like "no", "that's all", "nothing else" - move to ticket_creation
        2. If current stage is "complaint" and user asks about status - move to status_check
        3. If user explicitly asks to check status - move to status_check regardless of current stage
        4. If user ID is mentioned (format USER###) - move to verification
        
        Respond with just the name of the appropriate next stage.
        """
        
        try:
            # Get grievance stage recommendation from LLM
            next_stage_response = self.ollama.generate(
                "You are a grievance flow controller. Respond with only the recommended stage name.",
                grievance_stage_prompt,
                f"{thread_id}_grievance_stage"
            ).strip().lower()
            
            # Extract just the stage name
            import re
            stage_match = re.search(r'(identification|verification|complaint|status_check|ticket_creation|follow_up)', next_stage_response)
            if stage_match:
                next_stage = stage_match.group(1)
                logger.info(f"LLM determined next grievance stage: {next_stage}")
            else:
                # If LLM doesn't return a valid stage, use fallback logic
                logger.warning(f"Could not determine next stage from LLM response: '{next_stage_response}'")
                
                # Check if we're in complaint collection and user is done
                if current_stage == "complaint":
                    done_phrases = ["no", "none", "that's all", "no more", "that is all", "nothing else", "that's it", "all done"]
                    if any(phrase == query.lower().strip() for phrase in done_phrases):
                        next_stage = "ticket_creation"
                        logger.info(f"Fallback logic: User indicated done with complaint '{query}' - moving to ticket_creation")
                    else:
                        next_stage = "complaint"  # Stay in complaint stage
                else:
                    next_stage = current_stage  # Stay in current stage
            
            # Override with direct checks for critical patterns
            # Check for USER ID format if in identification stage
            if current_stage == "identification" or not grievance_context.get("user_id"):
                user_id_match = re.search(r'USER\d{3}', query)
                if user_id_match:
                    user_id = user_id_match.group(0)
                    # Store the user_id in context
                    self.update_grievance_context(thread_id, {"user_id": user_id})
                    next_stage = "verification"
                    logger.info(f"Pattern match override: Found USER ID {user_id} - moving to verification")
            
            # Status check override
            status_phrases = ["status", "check status", "what is my status", "what's happening", "any updates", "progress"]
            if any(phrase in query.lower() for phrase in status_phrases):
                next_stage = "status_check"
                logger.info(f"Pattern match override: Status check requested - moving to status_check")
            
            return next_stage
                
        except Exception as e:
            logger.error(f"Error determining grievance stage: {e}")
            # Default to current stage on error
            return current_stage or "identification"
    
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