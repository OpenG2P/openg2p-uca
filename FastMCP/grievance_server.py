"""
Grievance subsystem for the Social Benefits Assistant.

This module implements a FastMCP server for handling grievances and complaints.
"""

import json
import logging
import re
import datetime
import random
from pathlib import Path
from typing import Dict, List, Any, Optional, Literal

import anyio
from pydantic import BaseModel, Field
import aiosqlite

from mcp.server.fastmcp import FastMCP, Context

# Set up logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('SocialBenefits-GrievanceServer')

# Models for request/response structures
class UserDetails(BaseModel):
    """Model representing user details."""
    user_id: str
    user_name: str
    status: Optional[str] = None
    enrollment_date: Optional[str] = None
    program_id: Optional[int] = None

class ProgramDetails(BaseModel):
    """Model representing program details."""
    program_id: int
    program_name: str
    description: Optional[str] = None

class UserVerificationResult(BaseModel):
    """Model representing user verification result."""
    verified: bool
    user_details: Optional[UserDetails] = None
    program_details: Optional[ProgramDetails] = None

class UserIdResult(BaseModel):
    """Model representing user ID identification result."""
    found: bool
    user_id: Optional[str] = None

class ComplaintAnalysis(BaseModel):
    """Model representing complaint analysis result."""
    complaint: str
    enough_detail: bool = False
    program_mentioned: str = "Unspecified"
    issue_category: str = "Other"
    missing_information: List[str] = Field(default_factory=list)

class TicketDetails(BaseModel):
    """Model representing ticket details."""
    success: bool
    ticket_id: str
    created_at: str
    status: str = "OPEN"
    simulated: bool = False

class StatusCheckResult(BaseModel):
    """Model representing status check result."""
    found: bool
    type: str  # "program" or "ticket"
    user_id: Optional[str] = None
    ticket_id: Optional[str] = None
    status: Optional[str] = None
    enrollment_date: Optional[str] = None
    program_id: Optional[int] = None
    program_name: Optional[str] = None
    tickets: Optional[List[Dict[str, Any]]] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    resolution_notes: Optional[str] = None
    description: Optional[str] = None

# Set up FastMCP server
grievance_server = FastMCP(
    name="GrievanceServer",
    instructions="Grievance subsystem for Social Benefits Assistant. Handles user verification, complaint processing, ticket creation, and status checking."
)

# Database connection context
@asynccontextmanager
async def get_db_connection(db_path: str):
    """Async context manager for database connections."""
    conn = await aiosqlite.connect(db_path)
    conn.row_factory = aiosqlite.Row
    try:
        yield conn
    finally:
        await conn.close()

# Server lifespan context
@asynccontextmanager
async def server_lifespan(app: FastMCP):
    """Lifespan context for the grievance server."""
    # Initialize database path
    db_path = "grievance_db.sqlite"
    
    # Set up context for services to use
    context = {
        "db_path": db_path
    }
    
    logger.info("Grievance server initialized successfully")
    yield context

# Register server lifespan
grievance_server.settings.lifespan = server_lifespan

# ----- Tool Implementations -----

@grievance_server.tool(description="Identify if a user input contains a valid USER ID format")
async def identify_user_id(query: str, ctx: Context) -> UserIdResult:
    """
    Identify if a user input contains a valid USER ID format.
    
    Args:
        query: The user query to analyze
        ctx: The FastMCP context
        
    Returns:
        A UserIdResult object indicating if a USER ID was found
    """
    try:
        logger.info(f"Checking if query contains USER ID: '{query}'")
        
        # Check for USER### format using regex
        user_id_match = re.search(r'USER\d{3}', query, re.IGNORECASE)
        
        if user_id_match:
            user_id = user_id_match.group(0).upper()  # Normalize to uppercase
            logger.info(f"Found USER ID: {user_id}")
            return UserIdResult(found=True, user_id=user_id)
        else:
            logger.info("No USER ID found in query")
            return UserIdResult(found=False, user_id=None)
            
    except Exception as e:
        logger.error(f"Error in identify_user_id: {e}")
        return UserIdResult(found=False, user_id=None)

@grievance_server.tool(description="Verify if a user ID exists and retrieve user information")
async def verify_user(user_id: str, ctx: Context) -> UserVerificationResult:
    """
    Verify if a user ID exists and retrieve user and program information.
    
    Args:
        user_id: User ID to verify (in format USER###)
        ctx: The FastMCP context
        
    Returns:
        A UserVerificationResult with verification status and user details
    """
    try:
        logger.info(f"Verifying user ID: {user_id}")
        
        lifespan_context = ctx.request_context.lifespan_context
        db_path = lifespan_context["db_path"]
        
        async with get_db_connection(db_path) as conn:
            # Query the program_membership table
            cursor = await conn.execute(
                "SELECT * FROM program_membership WHERE user_id = ?",
                (user_id,)
            )
            user_row = await cursor.fetchone()
            
            if not user_row:
                logger.warning(f"User ID not found: {user_id}")
                return UserVerificationResult(verified=False)
            
            # Create user details object
            user_details = UserDetails(
                user_id=user_id,
                user_name=user_row["user_name"],
                status=user_row["status"] if "status" in user_row else None,
                enrollment_date=user_row["enrollment_date"] if "enrollment_date" in user_row else None,
                program_id=user_row["program_id"] if "program_id" in user_row else None
            )
            
            logger.info(f"Found user: {user_details.user_name}")
            
            # Get program details if available
            program_details = None
            if user_details.program_id:
                cursor = await conn.execute(
                    "SELECT * FROM registry WHERE program_id = ?",
                    (user_details.program_id,)
                )
                program_row = await cursor.fetchone()
                
                if program_row:
                    program_details = ProgramDetails(
                        program_id=user_details.program_id,
                        program_name=program_row["program_name"],
                        description=program_row["description"] if "description" in program_row else None
                    )
                    logger.info(f"Found program: {program_details.program_name}")
                else:
                    logger.warning(f"Program ID {user_details.program_id} not found for user {user_id}")
                    program_details = ProgramDetails(
                        program_id=user_details.program_id,
                        program_name="Unknown Program"
                    )
            
            return UserVerificationResult(
                verified=True,
                user_details=user_details,
                program_details=program_details
            )
        
    except Exception as e:
        logger.error(f"Error in verify_user: {e}")
        return UserVerificationResult(verified=False)

@grievance_server.tool(description="Process a complaint and determine if enough information has been collected")
async def process_complaint(
    complaint: str, 
    previous_parts: Optional[List[str]] = None,
    is_follow_up: bool = False,
    ctx: Context = None
) -> ComplaintAnalysis:
    """
    Process a complaint and determine if enough information has been collected.
    
    Args:
        complaint: The complaint text
        previous_parts: Previous parts of the complaint (if any)
        is_follow_up: Whether this is a follow-up to an existing complaint
        ctx: The FastMCP context
        
    Returns:
        Analysis of the complaint including whether enough detail has been provided
    """
    try:
        logger.info(f"Processing complaint: '{complaint[:50]}...' (length: {len(complaint)})")
        
        # Combine with previous complaints if this is a follow-up
        if is_follow_up and previous_parts:
            all_complaints = "\n".join(previous_parts + [complaint])
            logger.info(f"Combined with {len(previous_parts)} previous complaint parts")
        else:
            all_complaints = complaint
        
        # Simple rule-based analysis to determine if enough detail has been collected
        # In a real-world application, this would involve NLP or be delegated to an LLM
        
        words = all_complaints.split()
        word_count = len(words)
        
        # Check for issue category keywords
        payment_keywords = ["payment", "money", "funds", "deposit", "late", "missing"]
        eligibility_keywords = ["eligible", "qualify", "qualification", "rejected", "denied"]
        application_keywords = ["application", "apply", "form", "submitted", "paperwork"]
        technical_keywords = ["website", "online", "error", "system", "login", "account"]
        
        issue_counts = {
            "Payment": sum(1 for word in words if word.lower() in payment_keywords),
            "Eligibility": sum(1 for word in words if word.lower() in eligibility_keywords),
            "Application": sum(1 for word in words if word.lower() in application_keywords),
            "Technical": sum(1 for word in words if word.lower() in technical_keywords),
            "Other": 0
        }
        
        # Determine issue category with the most matches
        issue_category = max(issue_counts.items(), key=lambda x: x[1])[0]
        if issue_counts[issue_category] == 0:
            issue_category = "Other"
        
        # Simple program mention detection
        program_mentioned = "Unspecified"
        program_keywords = ["housing", "medical", "food", "unemployment", "disability", "childcare"]
        for keyword in program_keywords:
            if keyword in all_complaints.lower():
                program_mentioned = f"{keyword.capitalize()} assistance"
                break
        
        # Check if complaint has enough detail
        enough_detail = word_count >= 20
        
        # Determine what information might be missing
        missing_information = []
        
        if "when" not in all_complaints.lower() and "date" not in all_complaints.lower():
            missing_information.append("When the issue occurred")
        
        if "impact" not in all_complaints.lower() and "affect" not in all_complaints.lower():
            missing_information.append("How this issue affects you")
        
        if not any(keyword in all_complaints.lower() for keyword in ["tried", "attempt", "contacted"]):
            missing_information.append("Steps you've already taken to resolve the issue")
        
        if issue_category == "Payment" and not any(amount_word in all_complaints.lower() for amount_word in ["$", "dollar", "amount"]):
            missing_information.append("Payment amount details")
        
        return ComplaintAnalysis(
            complaint=all_complaints,
            enough_detail=enough_detail,
            program_mentioned=program_mentioned,
            issue_category=issue_category,
            missing_information=missing_information
        )
        
    except Exception as e:
        logger.error(f"Error in process_complaint: {e}")
        return ComplaintAnalysis(
            complaint=complaint,
            enough_detail=False,
            issue_category="Other",
            missing_information=["Error processing complaint"]
        )

@grievance_server.tool(description="Create a ticket in the database for a grievance")
async def create_ticket(
    user_id: str, 
    complaint: str, 
    program_id: Optional[int] = 0,
    ctx: Context = None
) -> TicketDetails:
    """
    Create a ticket in the database for a grievance.
    
    Args:
        user_id: User ID in format USER###
        complaint: The complaint text
        program_id: Optional program ID
        ctx: The FastMCP context
        
    Returns:
        Details of the created ticket
    """
    try:
        logger.info(f"Creating ticket for user {user_id}, program {program_id}")
        
        lifespan_context = ctx.request_context.lifespan_context
        db_path = lifespan_context["db_path"]
        
        # Generate a ticket number
        ticket_id = f"TKT-{datetime.datetime.now().strftime('%Y%m%d')}-{random.randint(1000, 9999)}"
        now = datetime.datetime.now().isoformat()
        
        async with get_db_connection(db_path) as conn:
            # Insert ticket into database
            try:
                await conn.execute(
                    """
                    INSERT INTO ticket 
                    (ticket_id, user_id, program_id, description, status, priority, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (ticket_id, user_id, program_id, complaint, 'OPEN', 'MEDIUM', now, now)
                )
                
                await conn.commit()
                logger.info(f"Successfully created ticket: {ticket_id}")
                
                return TicketDetails(
                    success=True,
                    ticket_id=ticket_id,
                    created_at=now,
                    status="OPEN"
                )
                
            except Exception as db_error:
                logger.error(f"Database error creating ticket: {db_error}")
                
                # Return a simulated ticket for graceful failure
                fallback_ticket_id = f"SIM-{datetime.datetime.now().strftime('%Y%m%d')}-{random.randint(1000, 9999)}"
                logger.info(f"Providing simulated ticket: {fallback_ticket_id}")
                
                return TicketDetails(
                    success=False,
                    simulated=True,
                    ticket_id=fallback_ticket_id,
                    created_at=now,
                    status="PENDING"
                )
                
    except Exception as e:
        logger.error(f"Error in create_ticket: {e}")
        # Generate emergency fallback ticket ID
        fallback_ticket_id = f"ERR-{datetime.datetime.now().strftime('%Y%m%d')}-{random.randint(1000, 9999)}"
        return TicketDetails(
            success=False,
            ticket_id=fallback_ticket_id,
            created_at=datetime.datetime.now().isoformat(),
            status="ERROR"
        )

@grievance_server.tool(description="Check status of a program enrollment or specific ticket")
async def check_status(
    user_id: str, 
    ticket_id: Optional[str] = None,
    ctx: Context = None
) -> StatusCheckResult:
    """
    Check status of a program enrollment or specific ticket.
    
    Args:
        user_id: User ID in format USER###
        ticket_id: Optional ticket ID to check
        ctx: The FastMCP context
        
    Returns:
        Status check result
    """
    try:
        logger.info(f"Checking status for user: {user_id}, ticket: {ticket_id}")
        
        lifespan_context = ctx.request_context.lifespan_context
        db_path = lifespan_context["db_path"]
        
        async with get_db_connection(db_path) as conn:
            # If ticket_id is provided, check ticket status
            if ticket_id:
                cursor = await conn.execute(
                    "SELECT * FROM ticket WHERE ticket_id = ?",
                    (ticket_id,)
                )
                ticket_row = await cursor.fetchone()
                
                if ticket_row:
                    logger.info(f"Found ticket {ticket_id} with status: {ticket_row['status']}")
                    
                    return StatusCheckResult(
                        found=True,
                        type="ticket",
                        ticket_id=ticket_id,
                        status=ticket_row["status"],
                        description=ticket_row["description"],
                        created_at=ticket_row["created_at"],
                        updated_at=ticket_row["updated_at"],
                        resolution_notes=ticket_row["resolution_notes"] if "resolution_notes" in ticket_row else None
                    )
                else:
                    logger.warning(f"Ticket not found: {ticket_id}")
                    return StatusCheckResult(
                        found=False,
                        type="ticket",
                        ticket_id=ticket_id
                    )
            
            # Check for user's program enrollment status
            cursor = await conn.execute(
                "SELECT * FROM program_membership WHERE user_id = ?",
                (user_id,)
            )
            user_row = await cursor.fetchone()
            
            if user_row:
                program_id = user_row["program_id"] if "program_id" in user_row else None
                program_name = "Unknown Program"
                
                # Get program details
                if program_id:
                    cursor = await conn.execute(
                        "SELECT * FROM registry WHERE program_id = ?",
                        (program_id,)
                    )
                    program_row = await cursor.fetchone()
                    if program_row and "program_name" in program_row:
                        program_name = program_row["program_name"]
                
                # Get user's tickets
                cursor = await conn.execute(
                    "SELECT * FROM ticket WHERE user_id = ? ORDER BY created_at DESC LIMIT 5",
                    (user_id,)
                )
                ticket_rows = await cursor.fetchall()
                
                tickets = []
                if ticket_rows:
                    for row in ticket_rows:
                        ticket_dict = {}
                        for key in row.keys():
                            ticket_dict[key] = row[key]
                        tickets.append(ticket_dict)
                
                logger.info(f"Found user {user_id} with status: {user_row['status']}")
                
                return StatusCheckResult(
                    found=True,
                    type="program",
                    user_id=user_id,
                    status=user_row["status"] if "status" in user_row else None,
                    enrollment_date=user_row["enrollment_date"] if "enrollment_date" in user_row else None,
                    program_id=program_id,
                    program_name=program_name,
                    tickets=tickets if tickets else None
                )
            else:
                logger.warning(f"User not found: {user_id}")
                return StatusCheckResult(
                    found=False,
                    type="program",
                    user_id=user_id
                )
                
    except Exception as e:
        logger.error(f"Error in check_status: {e}")
        return StatusCheckResult(
            found=False,
            type="unknown",
            user_id=user_id
        )

# ----- Prompts for Response Generation -----

@grievance_server.prompt()
def user_verification_response(user_details: Dict, program_details: Dict) -> List:
    """
    Generate a response for successful user verification.
    
    Args:
        user_details: User details
        program_details: Program details
    
    Returns:
        A list of formatted messages for the response
    """
    from mcp.server.fastmcp.prompts.base import AssistantMessage
    
    user_name = user_details.get("user_name", "there")
    program_name = program_details.get("program_name", "the program") if program_details else "our program"
    
    response_text = f"""
Thank you for providing your information. I can see your enrollment details, {user_name}.

I see you're enrolled in {program_name}. I'd like to help address any issues you're experiencing. 

Could you please describe the problem you're having in detail? The more specific information you can provide, the better I can assist you. For example:
- What specific issue are you encountering?
- When did you first notice this problem?
- How is this affecting you?
- Have you already taken steps to try to resolve this?
"""
    
    return [AssistantMessage(response_text)]

@grievance_server.prompt()
def verification_failed_response(user_id: str) -> List:
    """
    Generate a response for failed user verification.
    
    Args:
        user_id: The user ID that failed verification
    
    Returns:
        A list of formatted messages for the response
    """
    from mcp.server.fastmcp.prompts.base import AssistantMessage
    
    response_text = f"""
I'm sorry, but I couldn't find any records associated with the ID {user_id} in our system.

This could be because:
- The ID might have been entered incorrectly
- The account might be too new or not yet registered
- There might be a technical issue with our database

Please double-check your ID and try again. If you're sure the ID is correct, you might need to contact our support team directly at 1-800-BENEFITS for further assistance.
"""
    
    return [AssistantMessage(response_text)]

@grievance_server.prompt()
def ticket_creation_response(ticket_details: Dict, user_details: Dict, complaint: str) -> List:
    """
    Generate a response for ticket creation.
    
    Args:
        ticket_details: Ticket details
        user_details: User details
        complaint: The complaint text
    
    Returns:
        A list of formatted messages for the response
    """
    from mcp.server.fastmcp.prompts.base import AssistantMessage
    
    user_name = user_details.get("user_name", "there") if user_details else "there"
    ticket_id = ticket_details.get("ticket_id", "Unknown")
    status = ticket_details.get("status", "OPEN")
    
    response_text = f"""
Thank you {user_name} for reporting this issue. I've created a support ticket for you.

**Ticket Information:**
- Ticket ID: {ticket_id}
- Status: {status}
- Created: {ticket_details.get("created_at", "Just now")}

A support agent will review your case within 3-5 business days. You can check the status of your ticket at any time by providing your ticket ID.

Is there anything else you'd like me to help you with today?
"""
    
    return [AssistantMessage(response_text)]

@grievance_server.prompt()
def status_check_response(status_data: Dict) -> List:
    """
    Generate a response for status check.
    
    Args:
        status_data: Status check data
    
    Returns:
        A list of formatted messages for the response
    """
    from mcp.server.fastmcp.prompts.base import AssistantMessage
    
    if not status_data.get("found", False):
        response_text = f"""
I'm sorry, but I couldn't find any information for the ID you provided.

Please make sure you're using the correct ID format:
- For checking your program enrollment status: USER### (e.g., USER123)
- For checking a specific ticket: TKT-YYYYMMDD-#### (e.g., TKT-20250405-1234)

If you're sure you're using the correct ID, please contact our support team directly at 1-800-BENEFITS.
"""
        return [AssistantMessage(response_text)]
    
    check_type = status_data.get("type", "unknown")
    
    if check_type == "ticket":
        ticket_id = status_data.get("ticket_id", "Unknown")
        status = status_data.get("status", "Unknown")
        
        status_descriptions = {
            "OPEN": "Your ticket has been recorded in our system and is waiting to be assigned to a support agent.",
            "IN_PROGRESS": "A support agent is currently working on your case.",
            "PENDING": "We're waiting for additional information or actions before proceeding.",
            "RESOLVED": "Your issue has been resolved according to our records.",
            "CLOSED": "This ticket has been closed."
        }
        
        status_description = status_descriptions.get(status, "The current status of your ticket.")
        
        response_text = f"""
I've found the information for ticket {ticket_id}:

**Current Status:** {status}
**What This Means:** {status_description}
**Last Updated:** {status_data.get("updated_at", "Not available")}

"""
        if status_data.get("resolution_notes"):
            response_text += f"**Resolution Notes:** {status_data.get('resolution_notes')}\n\n"
            
        response_text += "Is there anything else you'd like to know about this ticket?"
        
    else:  # program enrollment status
        user_id = status_data.get("user_id", "Unknown")
        status = status_data.get("status", "Unknown")
        program_name = status_data.get("program_name", "Unknown program")
        
        status_descriptions = {
            "ACTIVE": "You are currently enrolled and eligible for benefits.",
            "PENDING": "Your application is still being processed.",
            "INACTIVE": "Your enrollment is currently inactive.",
            "SUSPENDED": "Your benefits have been temporarily suspended.",
            "DENIED": "Your application was not approved."
        }
        
        status_description = status_descriptions.get(status, "The current status of your enrollment.")
        
        response_text = f"""
I've found your enrollment information:

**Program:** {program_name}
**Current Status:** {status}
**What This Means:** {status_description}
**Enrollment Date:** {status_data.get("enrollment_date", "Not available")}

"""
        if status_data.get("tickets"):
            response_text += "**Recent Tickets:**\n"
            for i, ticket in enumerate(status_data.get("tickets", [])[:3]):
                response_text += f"- Ticket {ticket.get('ticket_id')}: {ticket.get('status')} (Created: {ticket.get('created_at')})\n"
            
        response_text += "\nIs there anything specific about your enrollment that you'd like to know?"
    
    return [AssistantMessage(response_text)]

# ----- Resources for Grievance Information -----

@grievance_server.resource("grievance://{user_id}/status")
async def user_status_resource(user_id: str) -> str:
    """
    Provide status information for a user.
    
    Args:
        user_id: The ID of the user
    
    Returns:
        Formatted user status information
    """
    try:
        # Direct database connection for this simple resource
        conn = sqlite3.connect("grievance_db.sqlite")
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM program_membership WHERE user_id = ?", (user_id,))
        user = cursor.fetchone()
        
        if user:
            program_id = user["program_id"] if "program_id" in user else None
            program_name = "Unknown Program"
            
            if program_id:
                cursor.execute("SELECT * FROM registry WHERE program_id = ?", (program_id,))
                program = cursor.fetchone()
                if program and "program_name" in program:
                    program_name = program["program_name"]
            
            status_info = {
                "user_id": user_id,
                "user_name": user["user_name"] if "user_name" in user else "Unknown",
                "status": user["status"] if "status" in user else "Unknown",
                "enrollment_date": user["enrollment_date"] if "enrollment_date" in user else None,
                "program_id": program_id,
                "program_name": program_name
            }
            return json.dumps(status_info, indent=2)
        else:
            return json.dumps({"error": "User not found"})
    except Exception as e:
        return json.dumps({"error": str(e)})
    finally:
        conn.close()

@grievance_server.resource("grievance://{ticket_id}/details")
async def ticket_details_resource(ticket_id: str) -> str:
    """
    Provide details for a specific ticket.
    
    Args:
        ticket_id: The ID of the ticket
    
    Returns:
        Formatted ticket details
    """
    try:
        # Direct database connection for this simple resource
        conn = sqlite3.connect("grievance_db.sqlite")
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM ticket WHERE ticket_id = ?", (ticket_id,))
        ticket = cursor.fetchone()
        
        if ticket:
            ticket_info = {}
            for key in ticket.keys():
                ticket_info[key] = ticket[key]
            return json.dumps(ticket_info, indent=2)
        else:
            return json.dumps({"error": "Ticket not found"})
    except Exception as e:
        return json.dumps({"error": str(e)})
    finally:
        conn.close()

# Main entry point
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Grievance MCP Server")
    parser.add_argument("--transport", type=str, default="stdio", choices=["stdio", "sse"], help="Transport protocol to use")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host for SSE transport")
    parser.add_argument("--port", type=int, default=8001, help="Port for SSE transport")
    
    args = parser.parse_args()
    
    if args.transport == "sse":
        grievance_server.settings.host = args.host
        grievance_server.settings.port = args.port
    
    grievance_server.run(args.transport)