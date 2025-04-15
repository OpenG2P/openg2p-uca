"""
Original Grievance Agent - For handling user grievances with multi-turn conversations
"""

import os
import json
import sqlite3
import random
import datetime
import re
import requests
from typing import Dict, List, Optional, Any, Tuple

class SimpleMemory:
    """Simple in-memory state management"""
    
    def __init__(self):
        self.state = {
            "stage": "identification",
            "user_id": None,
            "user_details": None,
            "programs": None,
            "selected_program": None,
            "complaint": None,
            "collecting_details": False,
            "ticket_id": None
        }
    
    def get(self, key, default=None):
        """Get a value from memory with optional default"""
        return self.state.get(key, default)
    
    def set(self, key, value):
        """Set a value in memory"""
        self.state[key] = value
    
    def update(self, updates):
        """Update multiple values at once"""
        self.state.update(updates)
    
    def reset(self):
        """Reset the memory to initial state"""
        self.__init__()

class GrievanceDB:
    """Database interface for grievance system"""
    
    def __init__(self, db_path):
        self.db_path = db_path
    
    def verify_user(self, user_id):
        """Verify user exists and get their program"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # Get user details
                cursor.execute(
                    "SELECT * FROM program_membership WHERE user_id = ?", 
                    (user_id,)
                )
                user = cursor.fetchone()
                
                if not user:
                    return False, None, None
                
                user_dict = dict(user)
                
                # Get program details
                program_id = user_dict.get('program_id')
                cursor.execute(
                    "SELECT * FROM registry WHERE program_id = ?",
                    (program_id,)
                )
                program = cursor.fetchone()
                program_dict = dict(program) if program else None
                
                return True, user_dict, program_dict
        except Exception as e:
            print(f"Database error: {e}")
            return False, None, None
    
    def create_ticket(self, user_id, program_id, description):
        """Create a ticket in the database"""
        try:
            ticket_id = f"TKT-{datetime.datetime.now().strftime('%Y%m%d')}-{random.randint(1000, 9999)}"
            now = datetime.datetime.now().isoformat()
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO ticket 
                    (ticket_id, user_id, program_id, description, status, priority, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (ticket_id, user_id, program_id, description, 'OPEN', 'MEDIUM', now, now)
                )
                conn.commit()
                return True, ticket_id
        except Exception as e:
            print(f"Ticket creation error: {e}")
            return False, None

class LLMClient:
    """Simple client for LLM API"""
    
    def __init__(self, model="deepseek-r1:8b"):
        self.model = model
        self.url = "http://localhost:11434/api/chat"
    
    def generate(self, system_prompt, user_prompt):
        try:
            response = requests.post(
                self.url,
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    "temperature": 0.2,
                    "stream": False
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get("message", {}).get("content", "")
            else:
                return f"Error: Status code {response.status_code}"
        except Exception as e:
            return f"Error generating response: {str(e)}"

class GrievanceAgent:
    """Main grievance agent class with enhanced multi-turn support"""
    
    def __init__(self, db_path="grievance_db.sqlite"):
        self.memory = SimpleMemory()
        self.db = GrievanceDB(db_path)
        self.llm = LLMClient()
        
        # Define prompts
        self.program_prompt = """
You are a helpful government benefits assistant. The user has a question or concern about their program.

USER INFORMATION:
- Name: {user_name}
- Program: {program_name}
- Enrollment Date: {enrollment_date}
- Status: {status}

PROGRAM DETAILS:
{program_description}

INSTRUCTIONS:
1. Acknowledge that you can see their enrollment information
2. Ask them to describe what issue they're having with their program
3. Be empathetic and professional
4. Keep your response concise

***********************Final-Response******************
"""

        self.status_prompt = """
You are a helpful government benefits assistant. The user has asked about their status in a program.

USER INFORMATION:
- Name: {user_name}
- Program: {program_name}
- Enrollment Date: {enrollment_date}
- Status: {status}

INSTRUCTIONS:
1. Provide clear information about their current status
2. Explain what this status means (if ACTIVE, PENDING, etc.)
3. Ask if they have any concerns about their status
4. Be helpful and concise

***********************Final-Response******************
"""

        self.follow_up_prompt = """
You are a helpful government benefits assistant. The user has provided information about their issue, and you need to gather any additional details.

USER INFORMATION:
- Name: {user_name}
- Program: {program_name}

CURRENT ISSUE DESCRIPTION:
{complaint}

INSTRUCTIONS:
1. Thank them for the information provided so far
2. Ask if they have any additional details they'd like to add
3. Let them know they can say "no" or "that's all" if they've shared everything
4. Be empathetic and supportive
5. Keep your response concise

***********************Final-Response******************
"""

        self.ticket_prompt = """
You are a helpful government benefits assistant. The user has reported an issue with their program and you need to confirm their ticket has been created.

TICKET INFORMATION:
- Ticket ID: {ticket_id}
- Status: OPEN
- Created: {created_at}

USER INFORMATION:
- Name: {user_name}
- Program: {program_name}

ISSUE DESCRIPTION:
{complaint}

INSTRUCTIONS:
1. Thank the user for reporting their issue
2. Inform them that a ticket has been created with the ticket ID
3. Tell them a support agent will review their case within 3-5 business days
4. Express that you were glad to help them today
5. Ask if there's anything else they need assistance with
6. Be empathetic and friendly but professional

***********************Final-Response******************
"""
    
    def process(self, message):
        """Process a user message based on current stage with multi-turn support"""
        stage = self.memory.get("stage")
        
        # STAGE 1: Identification - Get USER ID
        if stage == "identification":
            # Check if input is exactly a USER ID (USER followed by 3 digits)
            if re.match(r'^USER\d{3}$', message.strip()):
                user_id = message.strip()
                self.memory.set("user_id", user_id)
                self.memory.set("stage", "verification")
                return self.process("") # Continue to verification stage
            else:
                return "Please enter your USER ID (format: USER###)."
        
        # STAGE 2: Verification - Verify user exists in database
        elif stage == "verification":
            user_id = self.memory.get("user_id")
            verified, user_details, program = self.db.verify_user(user_id)
            
            if verified and user_details and program:
                # Store user and program details
                self.memory.update({
                    "user_details": user_details,
                    "program": program,
                    "stage": "complaint"
                })
                
                # Generate response with program information using LLM
                user_prompt = self.program_prompt.format(
                    user_name=user_details.get("user_name"),
                    program_name=program.get("program_name"),
                    enrollment_date=user_details.get("enrollment_date"),
                    status=user_details.get("status"),
                    program_description=program.get("description")
                )
                
                return self.llm.generate(
                    "You are a helpful government benefits assistant.",
                    user_prompt
                )
            else:
                self.memory.set("stage", "identification")
                return f"I couldn't find any records for {user_id}. Please check your USER ID and try again."
        
        # STAGE 3: Complaint - Collect issue details with multi-turn support
        elif stage == "complaint":
            # Check for status inquiries
            if message.lower().strip() in ["status", "what is my status", "what's my status", 
                                          "check status", "program status", "what is the status", 
                                          "application status", "what is the status of the application"]:
                user_details = self.memory.get("user_details", {})
                program = self.memory.get("program", {})
                
                # Generate status information using LLM
                user_prompt = self.status_prompt.format(
                    user_name=user_details.get("user_name"),
                    program_name=program.get("program_name"),
                    enrollment_date=user_details.get("enrollment_date"),
                    status=user_details.get("status")
                )
                
                return self.llm.generate(
                    "You are a helpful government benefits assistant.",
                    user_prompt
                )
            
            # Handle empty message (like after verification)
            if not message.strip():
                return ""
            
            # Check if we're already collecting details
            if self.memory.get("collecting_details"):
                # Check if user wants to end collection
                if message.lower() in ["no", "none", "that's all", "no more", "no more questions", 
                                      "that is all", "nothing else", "that's it"]:
                    # Ready to create a ticket
                    self.memory.set("collecting_details", False)
                    self.memory.set("stage", "ticket")
                    return self._create_ticket()
                else:
                    # Append this message to existing complaint
                    current_complaint = self.memory.get("complaint", "")
                    updated_complaint = f"{current_complaint}\nAdditional details: {message}"
                    self.memory.set("complaint", updated_complaint)
                    
                    # Ask if they have more to add using LLM
                    user_details = self.memory.get("user_details", {})
                    program = self.memory.get("program", {})
                    
                    user_prompt = self.follow_up_prompt.format(
                        user_name=user_details.get("user_name"),
                        program_name=program.get("program_name"),
                        complaint=updated_complaint
                    )
                    
                    return self.llm.generate(
                        "You are a helpful government benefits assistant.",
                        user_prompt
                    )
            else:
                # First complaint message
                self.memory.set("complaint", message)
                self.memory.set("collecting_details", True)
                
                # Ask if they have more to add
                user_details = self.memory.get("user_details", {})
                program = self.memory.get("program", {})
                
                user_prompt = self.follow_up_prompt.format(
                    user_name=user_details.get("user_name"),
                    program_name=program.get("program_name"),
                    complaint=message
                )
                
                return self.llm.generate(
                    "You are a helpful government benefits assistant.",
                    user_prompt
                )
        
        # STAGE 4: Ticket created - Handle follow-up
        elif stage == "ticket":
            # If user wants to discuss something else
            if any(word in message.lower() for word in ["yes", "another", "more", "new issue", "different"]):
                # Reset but keep user information
                user_id = self.memory.get("user_id")
                user_details = self.memory.get("user_details")
                program = self.memory.get("program")
                
                self.memory.reset()
                self.memory.update({
                    "stage": "complaint",
                    "user_id": user_id,
                    "user_details": user_details,
                    "program": program
                })
                
                return "What new issue would you like to report about your program?"
            
            # Simple response for any other follow-up messages
            ticket_id = self.memory.get("ticket_id", "Unknown")
            return f"Your ticket {ticket_id} is being processed. Is there anything else I can help you with today?"
        
        # Fallback for any unexpected state
        else:
            self.memory.reset()
            return "Please enter your USER ID (format: USER###)."
    
    def _create_ticket(self):
        """Helper method to create a ticket and generate confirmation"""
        user_id = self.memory.get("user_id")
        program = self.memory.get("program", {})
        program_id = program.get("program_id") if program else 0
        complaint = self.memory.get("complaint", "")
        
        success, ticket_id = self.db.create_ticket(user_id, program_id, complaint)
        
        if success:
            self.memory.set("ticket_id", ticket_id)
            
            # Generate ticket confirmation using LLM
            user_details = self.memory.get("user_details", {})
            
            user_prompt = self.ticket_prompt.format(
                ticket_id=ticket_id,
                created_at=datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                user_name=user_details.get("user_name"),
                program_name=program.get("program_name"),
                complaint=complaint
            )
            
            return self.llm.generate(
                "You are a helpful government benefits assistant.",
                user_prompt
            )
        else:
            return "I'm sorry, but I couldn't create a ticket for your issue. Please try again later."