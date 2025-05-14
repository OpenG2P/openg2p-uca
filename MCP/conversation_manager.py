"""
Conversation context management for the Social Benefits Assistant.

Handles thread context, conversation history, and state management.
"""

import datetime
import logging
from typing import Dict, List, Any, Optional

# Set up logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('SocialBenefits-ConversationManager')

class ConversationManager:
    """
    Manages conversation context for the MCP-based Social Benefits Assistant.
    
    Responsible for:
    - Managing thread contexts
    - Tracking conversation history
    - Maintaining user profiles
    - Managing grievance state machine
    """
    
    def __init__(self):
        """Initialize the conversation manager."""
        # Thread contexts store
        self.thread_contexts = {}
        logger.info("ConversationManager initialized")
    
    def get_thread_context(self, thread_id: str) -> Dict:
        """Get or initialize a thread context."""
        if thread_id not in self.thread_contexts:
            # Initialize a new thread context
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
                # Grievance context with state machine
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
    
    def get_conversation_history(self, thread_id: str) -> List[Dict]:
        """Get the conversation history for a thread."""
        context = self.get_thread_context(thread_id)
        return context.get("conversation_history", [])
    
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
    
    def get_retrieved_programs(self, thread_id: str) -> List[Dict]:
        """Get the retrieved programs for a thread."""
        context = self.get_thread_context(thread_id)
        return context.get("retrieved_programs", [])
    
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
    
    def get_user_profile(self, thread_id: str) -> Dict:
        """Get the user profile for a thread."""
        context = self.get_thread_context(thread_id)
        return context.get("user_profile", {})
    
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
        
        # Ensure complaint_parts exists
        if "complaint_parts" not in context["grievance_context"]:
            context["grievance_context"]["complaint_parts"] = []
            
        context["grievance_context"]["complaint_parts"].append(complaint)
        logger.info(f"Added complaint part for thread_id: {thread_id}")
    
    def store_decision(self, thread_id: str, decision: Dict):
        """Store a decision about query intent and routing."""
        context = self.get_thread_context(thread_id)
        context["last_decision"] = decision
        logger.info(f"Stored decision for thread_id: {thread_id}: {decision}")
    
    def get_persona(self, thread_id: str) -> Dict:
        """Get the conversation persona for a thread."""
        context = self.get_thread_context(thread_id)
        return context.get("persona", {
            "tone": "friendly and supportive",
            "speech_patterns": ["uses contractions", "asks occasional questions", "expresses empathy"],
            "personality_traits": ["helpful", "encouraging", "warm"]
        })
    
    def clear_thread(self, thread_id: str):
        """Clear a thread context."""
        if thread_id in self.thread_contexts:
            del self.thread_contexts[thread_id]
            logger.info(f"Cleared thread context for thread_id: {thread_id}")