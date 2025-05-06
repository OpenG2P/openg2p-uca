"""
Grievance Subsystem for the Social Benefits Assistant.

This subsystem is responsible for:
1. Processing user grievances
2. User verification
3. Ticket creation and management
4. Status checking
"""

import json
import re
import logging
import datetime
import random
from typing import Dict, List, Any, Optional

# Set up logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('SocialBenefits-GrievanceSubsystem')

class GrievanceSubsystem:
    """
    Subsystem for handling user grievances and complaints.
    
    Responsible for:
    - User identification and verification
    - Complaint collection
    - Ticket creation and management
    - Status checking
    """
    
    def __init__(self, db_tool, ollama_client, conversation_manager):
        """Initialize the grievance subsystem."""
        self.db_tool = db_tool
        self.ollama_client = ollama_client
        self.conversation_manager = conversation_manager
        logger.info("GrievanceSubsystem initialized")
    
    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> str:
        """Call a tool provided by this subsystem."""
        logger.info(f"Calling grievance subsystem tool: {name}")
        
        if name == "identify_user_id":
            return await self.identify_user_id(arguments["query"])
        elif name == "verify_user":
            return await self.verify_user(arguments["user_id"])
        elif name == "process_complaint":
            previous_parts = arguments.get("previous_parts", [])
            is_follow_up = arguments.get("is_follow_up", False)
            return await self.process_complaint(arguments["complaint"], previous_parts, is_follow_up)
        elif name == "create_ticket":
            program_id = arguments.get("program_id", 0)
            return await self.create_ticket(arguments["user_id"], program_id, arguments["complaint"])
        elif name == "check_status":
            ticket_id = arguments.get("ticket_id")
            return await self.check_status(arguments["user_id"], ticket_id)
        else:
            logger.error(f"Unknown tool: {name}")
            return json.dumps({"error": f"Unknown tool: {name}"})
    
    async def identify_user_id(self, query: str) -> str:
        """Identify if a user input contains a valid USER ID format."""
        try:
            logger.info(f"Checking if query contains USER ID: '{query}'")
            
            # Check for USER### format using regex
            user_id_match = re.search(r'USER\d{3}', query, re.IGNORECASE)
            
            if user_id_match:
                user_id = user_id_match.group(0).upper()  # Normalize to uppercase
                logger.info(f"Found USER ID: {user_id}")
                return json.dumps({
                    "found": True,
                    "user_id": user_id
                })
            else:
                logger.info("No USER ID found in query")
                return json.dumps({
                    "found": False,
                    "user_id": None
                })
                
        except Exception as e:
            logger.error(f"Error in identify_user_id: {e}")
            return json.dumps({
                "found": False,
                "user_id": None,
                "error": str(e)
            })
    
    async def verify_user(self, user_id: str) -> str:
        """Verify if a user ID exists and retrieve user and program information."""
        try:
            logger.info(f"Verifying user ID: {user_id}")
            
            # Query the program_membership table
            user_result = self.db_tool.execute_query(
                "SELECT * FROM program_membership WHERE user_id = ?",
                (user_id,)
            )
            
            if not user_result or len(user_result) == 0:
                logger.warning(f"User ID not found: {user_id}")
                return json.dumps({
                    "verified": False,
                    "user_details": None,
                    "program_details": None
                })
            
            user_details = user_result[0]
            logger.info(f"Found user: {user_details.get('user_name')}")
            
            # Get program details if available
            program_id = user_details.get("program_id")
            if program_id:
                program_result = self.db_tool.execute_query(
                    "SELECT * FROM registry WHERE program_id = ?",
                    (program_id,)
                )
                
                if program_result and len(program_result) > 0:
                    program_details = program_result[0]
                    logger.info(f"Found program: {program_details.get('program_name')}")
                else:
                    logger.warning(f"Program ID {program_id} not found for user {user_id}")
                    program_details = {"program_id": program_id, "program_name": "Unknown Program"}
            else:
                logger.warning(f"No program ID associated with user {user_id}")
                program_details = None
            
            return json.dumps({
                "verified": True,
                "user_details": user_details,
                "program_details": program_details
            })
            
        except Exception as e:
            logger.error(f"Error in verify_user: {e}")
            return json.dumps({
                "verified": False,
                "user_details": None,
                "program_details": None,
                "error": str(e)
            })
    
    async def process_complaint(self, complaint: str, previous_complaints: List[str], is_follow_up: bool) -> str:
        """Process a complaint and determine if enough information has been collected."""
        try:
            logger.info(f"Processing complaint: '{complaint[:50]}...' (length: {len(complaint)})")
            
            # Combine with previous complaints if this is a follow-up
            if is_follow_up and previous_complaints:
                all_complaints = "\n".join(previous_complaints + [complaint])
                logger.info(f"Combined with {len(previous_complaints)} previous complaint parts")
            else:
                all_complaints = complaint
            
            # Use LLM to analyze the complaint
            analysis_prompt = f"""
            Analyze this complaint about a government benefits program:
            
            COMPLAINT: {all_complaints}
            
            Please determine:
            1. Is there enough detail to create a support ticket? (Yes/No)
            2. What specific program or benefit is mentioned? (If none, say "Unspecified")
            3. What category does this issue fall into? (Payment, Eligibility, Application, Technical, Other)
            4. What additional information would be helpful to collect?
            
            Respond with JSON in this format:
            {{
                "enough_detail": true/false,
                "program_mentioned": "Program name or Unspecified",
                "issue_category": "Category",
                "missing_information": ["List", "of", "missing", "details"]
            }}
            """
            
            logger.info("Sending complaint analysis prompt to LLM")
            
            analysis_response = self.ollama_client.generate(
                "You are a complaint analysis system. Respond with JSON only.",
                analysis_prompt,
                "complaint_analysis"
            )
            
            # Try to extract JSON from the response
            try:
                json_match = re.search(r'\{.*\}', analysis_response, re.DOTALL)
                if json_match:
                    analysis = json.loads(json_match.group(0))
                    logger.info(f"Successfully parsed complaint analysis: {analysis}")
                else:
                    # Default analysis if no JSON found
                    logger.warning("Could not extract JSON from complaint analysis")
                    analysis = {
                        "enough_detail": False,
                        "program_mentioned": "Unspecified",
                        "issue_category": "Other",
                        "missing_information": ["Nature of the issue", "When the issue occurred", "Impact of the issue"]
                    }
                
                return json.dumps({
                    "complaint": all_complaints,
                    "enough_detail": analysis.get("enough_detail", False),
                    "program_mentioned": analysis.get("program_mentioned", "Unspecified"),
                    "issue_category": analysis.get("issue_category", "Other"),
                    "missing_information": analysis.get("missing_information", [])
                })
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse complaint analysis JSON: {e}")
                return json.dumps({
                    "complaint": all_complaints,
                    "enough_detail": False,
                    "program_mentioned": "Unspecified",
                    "issue_category": "Other",
                    "missing_information": ["Nature of the issue", "When the issue occurred", "Impact of the issue"],
                    "error": str(e)
                })
            
        except Exception as e:
            logger.error(f"Error in process_complaint: {e}")
            return json.dumps({
                "complaint": complaint,
                "enough_detail": False,
                "error": str(e)
            })
    
    async def create_ticket(self, user_id: str, program_id: int, complaint: str) -> str:
        """Create a ticket in the database for a grievance."""
        try:
            logger.info(f"Creating ticket for user {user_id}, program {program_id}")
            
            # Generate a ticket number
            ticket_id = f"TKT-{datetime.datetime.now().strftime('%Y%m%d')}-{random.randint(1000, 9999)}"
            now = datetime.datetime.now().isoformat()
            
            # Insert ticket into database
            try:
                self.db_tool.execute_query(
                    """
                    INSERT INTO ticket 
                    (ticket_id, user_id, program_id, description, status, priority, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (ticket_id, user_id, program_id, complaint, 'OPEN', 'MEDIUM', now, now)
                )
                
                logger.info(f"Successfully created ticket: {ticket_id}")
                
                return json.dumps({
                    "success": True,
                    "ticket_id": ticket_id,
                    "created_at": now,
                    "status": "OPEN"
                })
                
            except Exception as db_error:
                logger.error(f"Database error creating ticket: {db_error}")
                
                # Return a simulated ticket for graceful failure
                fallback_ticket_id = f"SIM-{datetime.datetime.now().strftime('%Y%m%d')}-{random.randint(1000, 9999)}"
                logger.info(f"Providing simulated ticket: {fallback_ticket_id}")
                
                return json.dumps({
                    "success": False,
                    "simulated": True,
                    "ticket_id": fallback_ticket_id,
                    "created_at": now,
                    "status": "PENDING",
                    "error": str(db_error)
                })
                
        except Exception as e:
            logger.error(f"Error in create_ticket: {e}")
            return json.dumps({
                "success": False,
                "error": str(e)
            })
    
    async def check_status(self, user_id: str, ticket_id: Optional[str] = None) -> str:
        """Check status of a program enrollment or specific ticket."""
        try:
            logger.info(f"Checking status for user: {user_id}, ticket: {ticket_id}")
            
            # If ticket_id is provided, check ticket status
            if ticket_id:
                ticket_result = self.db_tool.execute_query(
                    "SELECT * FROM ticket WHERE ticket_id = ?",
                    (ticket_id,)
                )
                
                if ticket_result and len(ticket_result) > 0:
                    ticket = ticket_result[0]
                    logger.info(f"Found ticket {ticket_id} with status: {ticket.get('status')}")
                    
                    return json.dumps({
                        "found": True,
                        "type": "ticket",
                        "ticket_id": ticket_id,
                        "status": ticket.get("status"),
                        "description": ticket.get("description"),
                        "created_at": ticket.get("created_at"),
                        "updated_at": ticket.get("updated_at"),
                        "resolution_notes": ticket.get("resolution_notes")
                    })
                else:
                    logger.warning(f"Ticket not found: {ticket_id}")
                    return json.dumps({
                        "found": False,
                        "type": "ticket",
                        "ticket_id": ticket_id
                    })
            
            # Check for user's tickets
            tickets_result = self.db_tool.execute_query(
                "SELECT * FROM ticket WHERE user_id = ? ORDER BY created_at DESC LIMIT 5",
                (user_id,)
            )
            
            # Check user's program enrollment status
            user_result = self.db_tool.execute_query(
                "SELECT * FROM program_membership WHERE user_id = ?",
                (user_id,)
            )
            
            if user_result and len(user_result) > 0:
                user = user_result[0]
                
                # Get program details
                program_id = user.get("program_id")
                if program_id:
                    program_result = self.db_tool.execute_query(
                        "SELECT * FROM registry WHERE program_id = ?",
                        (program_id,)
                    )
                    program = program_result[0] if program_result and len(program_result) > 0 else None
                else:
                    program = None
                
                logger.info(f"Found user {user_id} with status: {user.get('status')}")
                
                # Format the response
                response = {
                    "found": True,
                    "type": "program",
                    "user_id": user_id,
                    "status": user.get("status"),
                    "enrollment_date": user.get("enrollment_date"),
                    "program_id": program_id,
                    "program_name": program.get("program_name") if program else "Unknown Program"
                }
                
                # Add tickets if found
                if tickets_result and len(tickets_result) > 0:
                    response["tickets"] = tickets_result
                    logger.info(f"Found {len(tickets_result)} tickets for user {user_id}")
                
                return json.dumps(response)
            else:
                logger.warning(f"User not found: {user_id}")
                return json.dumps({
                    "found": False,
                    "type": "program",
                    "user_id": user_id
                })
                
        except Exception as e:
            logger.error(f"Error in check_status: {e}")
            return json.dumps({
                "found": False,
                "error": str(e)
            })
    
    async def get_user_verification(self, user_id: str) -> Dict:
        """Get user verification data."""
        try:
            # Query for user data
            user_result = self.db_tool.execute_query(
                "SELECT * FROM program_membership WHERE user_id = ?",
                (user_id,)
            )
            
            if user_result and len(user_result) > 0:
                user_data = user_result[0]
                return user_data
            else:
                return {"error": "User not found"}
        except Exception as e:
            logger.error(f"Error getting user verification: {e}")
            return {"error": str(e)}
    
    async def get_user_programs(self, user_id: str) -> Dict:
        """Get programs associated with a user."""
        try:
            # Query for program membership
            membership_result = self.db_tool.execute_query(
                "SELECT * FROM program_membership WHERE user_id = ?",
                (user_id,)
            )
            
            if not membership_result or len(membership_result) == 0:
                return {"user_id": user_id, "programs": []}
            
            programs = []
            for membership in membership_result:
                program_id = membership.get("program_id")
                if program_id:
                    program_result = self.db_tool.execute_query(
                        "SELECT * FROM registry WHERE program_id = ?",
                        (program_id,)
                    )
                    
                    if program_result and len(program_result) > 0:
                        program = program_result[0]
                        programs.append({
                            "program_id": program_id,
                            "program_name": program.get("program_name", "Unknown"),
                            "enrollment_status": membership.get("status", "Unknown"),
                            "enrollment_date": membership.get("enrollment_date")
                        })
            
            return {
                "user_id": user_id,
                "user_name": membership_result[0].get("user_name"),
                "programs": programs
            }
        except Exception as e:
            logger.error(f"Error getting user programs: {e}")
            return {"user_id": user_id, "error": str(e)}
    
    async def get_user_tickets(self, user_id: str) -> Dict:
        """Get tickets associated with a user."""
        try:
            # Query for tickets
            ticket_result = self.db_tool.execute_query(
                "SELECT * FROM ticket WHERE user_id = ? ORDER BY created_at DESC",
                (user_id,)
            )
            
            if ticket_result and len(ticket_result) > 0:
                return {
                    "user_id": user_id,
                    "tickets": ticket_result
                }
            else:
                return {
                    "user_id": user_id,
                    "tickets": []
                }
        except Exception as e:
            logger.error(f"Error getting user tickets: {e}")
            return {"user_id": user_id, "error": str(e)}
    
    async def get_ticket_details(self, ticket_id: str) -> Dict:
        """Get details for a specific ticket."""
        try:
            # Query for ticket
            ticket_result = self.db_tool.execute_query(
                "SELECT * FROM ticket WHERE ticket_id = ?",
                (ticket_id,)
            )
            
            if ticket_result and len(ticket_result) > 0:
                ticket = ticket_result[0]
                
                # Get user details
                user_id = ticket.get("user_id")
                user_result = None
                if user_id:
                    user_result = self.db_tool.execute_query(
                        "SELECT * FROM program_membership WHERE user_id = ?",
                        (user_id,)
                    )
                
                return {
                    "ticket_id": ticket_id,
                    "user_id": user_id,
                    "user_name": user_result[0].get("user_name") if user_result and len(user_result) > 0 else "Unknown",
                    "program_id": ticket.get("program_id"),
                    "description": ticket.get("description"),
                    "status": ticket.get("status"),
                    "priority": ticket.get("priority"),
                    "created_at": ticket.get("created_at"),
                    "updated_at": ticket.get("updated_at"),
                    "resolution_notes": ticket.get("resolution_notes")
                }
            else:
                return {"ticket_id": ticket_id, "error": "Ticket not found"}
        except Exception as e:
            logger.error(f"Error getting ticket details: {e}")
            return {"ticket_id": ticket_id, "error": str(e)}