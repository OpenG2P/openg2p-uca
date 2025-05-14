"""
Eligibility subsystem for the Social Benefits Assistant.

This module implements a FastMCP server for handling program eligibility queries.
"""

import json
import logging
import sqlite3
from pathlib import Path
from typing import Dict, List, Any, Optional, Literal

import anyio
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from pydantic import BaseModel, Field
import aiosqlite

from mcp.server.fastmcp import FastMCP, Context

# Set up logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('SocialBenefits-EligibilityServer')

# Models for request/response structures
class UserProfile(BaseModel):
    """Model representing user profile information extracted from conversation."""
    income_level: Optional[str] = None
    family_size: Optional[int] = None
    location: Optional[str] = None
    housing_status: Optional[str] = None
    employment_status: Optional[str] = None
    age: Optional[int] = None
    age_group: Optional[str] = None
    marital_status: Optional[str] = None
    gender: Optional[str] = None
    disabilities: Optional[List[str]] = None
    other_factors: Optional[Dict[str, Any]] = None

class ProgramInfo(BaseModel):
    """Model representing program information."""
    id: int
    name: str
    description: str = "No description available"
    eligibility_criteria: str = "Not specified"
    benefits: str = "Benefits information not available"
    application_process: str = "Application process information not available"

class EligibilityAnalysis(BaseModel):
    """Model representing eligibility analysis results."""
    program_id: int
    program_name: str
    eligibility_likelihood: Literal["High", "Medium", "Low", "Unknown"]
    matching_criteria: List[str] = Field(default_factory=list)
    missing_information: List[str] = Field(default_factory=list)

class EligibilityResult(BaseModel):
    """Model representing eligibility analysis results for multiple programs."""
    programs: List[ProgramInfo]
    analysis: List[EligibilityAnalysis]

# Set up FastMCP server
eligibility_server = FastMCP(
    name="EligibilityServer",
    instructions="Eligibility subsystem for Social Benefits Assistant. Handles program search, user profile extraction, and eligibility analysis."
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
    """Lifespan context for the eligibility server."""
    # Initialize database and FAISS index paths
    db_path = "program_db.sqlite"
    faiss_index_path = "program_db_faiss/programs_index"
    
    # Initialize embeddings for semantic search
    try:
        logger.info(f"Loading FAISS index from {faiss_index_path}")
        embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        
        # Load the FAISS index
        vector_store = FAISS.load_local(
            faiss_index_path, 
            embeddings,
            allow_dangerous_deserialization=True
        )
        
        # Create a retriever
        retriever = vector_store.as_retriever(
            search_type="similarity", 
            search_kwargs={"k": 3}
        )
        
        # Set up context for services to use
        context = {
            "db_path": db_path,
            "retriever": retriever
        }
        
        logger.info("Server initialized successfully")
        yield context
    except Exception as e:
        logger.error(f"Error initializing server: {e}")
        raise

# Register server lifespan
eligibility_server.settings.lifespan = server_lifespan

# ----- Tool Implementations -----

@eligibility_server.tool(description="Extract user profile details from query and conversation history")
async def extract_user_details(query: str, ctx: Context) -> UserProfile:
    """
    Extract user profile information from a query and conversation history.
    
    Args:
        query: The user query to analyze
        ctx: The FastMCP context
        
    Returns:
        A UserProfile object with extracted user details
    """
    try:
        logger.info(f"Extracting user details from query: '{query}'")
        
        # Example logic to extract user profile from query
        # In a real implementation, this would use more sophisticated NLP
        user_profile = UserProfile()
        
        # Simple pattern matching for income
        if "$" in query:
            import re
            income_matches = re.findall(r'\$(\d+),?(\d+)?', query)
            if income_matches:
                income_str = ''.join(income_matches[0])
                if income_str:
                    income = int(income_str)
                    user_profile.income_level = str(income)
        
        # Simple pattern matching for family size
        if "family" in query.lower() or "people" in query.lower():
            import re
            size_matches = re.findall(r'(\d+)\s+(person|people|family|members)', query.lower())
            if size_matches:
                user_profile.family_size = int(size_matches[0][0])
        
        # Extract location if mentioned
        location_indicators = ["in ", "live in ", "from ", "resident of "]
        for indicator in location_indicators:
            if indicator in query.lower():
                location_start = query.lower().find(indicator) + len(indicator)
                location_end = min(
                    (query.find(" ", location_start) if query.find(" ", location_start) != -1 else len(query)),
                    (query.find(",", location_start) if query.find(",", location_start) != -1 else len(query)),
                    (query.find(".", location_start) if query.find(".", location_start) != -1 else len(query))
                )
                if location_end > location_start:
                    user_profile.location = query[location_start:location_end]
        
        return user_profile
    
    except Exception as e:
        logger.error(f"Error in extract_user_details: {e}")
        return UserProfile()

@eligibility_server.tool(description="Search for relevant programs based on query")
async def search_programs(query: str, ctx: Context) -> List[int]:
    """
    Search for programs matching the user's query.
    
    Args:
        query: The search query
        ctx: The FastMCP context
        
    Returns:
        A list of program IDs that match the query
    """
    try:
        logger.info(f"Searching for programs matching: '{query}'")
        
        lifespan_context = ctx.request_context.lifespan_context
        retriever = lifespan_context["retriever"]
        
        # Use FAISS vector search
        try:
            documents = await anyio.to_thread.run_sync(retriever.get_relevant_documents, query)
        except Exception as e:
            logger.error(f"Error in vector search: {e}")
            documents = []
        
        if not documents:
            logger.warning("No relevant documents found in FAISS search")
            return []
        
        # Extract program IDs
        program_ids = []
        for doc in documents:
            program_id = doc.metadata.get("id")
            if program_id and program_id not in program_ids:
                program_ids.append(program_id)
        
        logger.info(f"Found {len(program_ids)} relevant programs: {program_ids}")
        return program_ids
    
    except Exception as e:
        logger.error(f"Error in search_programs: {e}")
        return []

@eligibility_server.tool(description="Analyze program eligibility based on user profile")
async def analyze_eligibility(
    program_ids: List[int], 
    user_profile: Optional[UserProfile] = None,
    ctx: Context = None
) -> EligibilityResult:
    """
    Analyze user eligibility for specified programs.
    
    Args:
        program_ids: List of program IDs to analyze
        user_profile: Optional user profile information
        ctx: The FastMCP context
        
    Returns:
        Eligibility analysis results for the programs
    """
    try:
        logger.info(f"Analyzing eligibility for {len(program_ids)} programs")
        
        lifespan_context = ctx.request_context.lifespan_context
        db_path = lifespan_context["db_path"]
        
        programs = []
        analysis = []
        
        async with get_db_connection(db_path) as conn:
            # Get program details from database
            for program_id in program_ids:
                # Query program_info table
                query = "SELECT * FROM program_info WHERE id = ?"
                cursor = await conn.execute(query, (program_id,))
                program_row = await cursor.fetchone()
                
                if program_row:
                    # Create a clean program object
                    program_info = ProgramInfo(
                        id=program_id,
                        name=program_row["name"] if "name" in program_row else f"Program {program_id}",
                        description=program_row["description"] if "description" in program_row else "No description available",
                        eligibility_criteria=program_row["criteria"] if "criteria" in program_row else "Not specified",
                        benefits=program_row["benefits"] if "benefits" in program_row else "Benefits information not available",
                        application_process=program_row["application"] if "application" in program_row else "Application process information not available"
                    )
                    
                    programs.append(program_info)
                    
                    # Basic eligibility analysis
                    eligibility_likelihood = "Unknown"
                    matching_criteria = []
                    missing_information = []
                    
                    if user_profile:
                        # Example: Simple income-based eligibility check
                        if user_profile.income_level:
                            try:
                                income = int(user_profile.income_level.replace("$", "").replace(",", ""))
                                # Check eligibility criteria for income mentions
                                criteria_lower = program_info.eligibility_criteria.lower()
                                
                                # Very simple rule-based analysis
                                if "low income" in criteria_lower or "low-income" in criteria_lower:
                                    if income < 30000:
                                        eligibility_likelihood = "High"
                                        matching_criteria.append("Income level meets low-income requirement")
                                    elif income < 50000:
                                        eligibility_likelihood = "Medium"
                                        matching_criteria.append("Income level may meet low-income requirement")
                                    else:
                                        eligibility_likelihood = "Low"
                                        matching_criteria.append("Income level may be too high for this program")
                            except (ValueError, TypeError):
                                missing_information.append("Precise income information")
                        else:
                            missing_information.append("Income level")
                        
                        # Check for family size
                        if user_profile.family_size:
                            matching_criteria.append(f"Family size: {user_profile.family_size}")
                        else:
                            missing_information.append("Family size")
                            
                        # Check for location
                        if user_profile.location:
                            matching_criteria.append(f"Location: {user_profile.location}")
                        else:
                            missing_information.append("Location information")
                    else:
                        missing_information.append("User profile information")
                    
                    analysis.append(EligibilityAnalysis(
                        program_id=program_id,
                        program_name=program_info.name,
                        eligibility_likelihood=eligibility_likelihood,
                        matching_criteria=matching_criteria,
                        missing_information=missing_information
                    ))
        
        logger.info(f"Completed eligibility analysis for {len(programs)} programs")
        return EligibilityResult(programs=programs, analysis=analysis)
    
    except Exception as e:
        logger.error(f"Error in analyze_eligibility: {e}")
        return EligibilityResult(programs=[], analysis=[])

@eligibility_server.tool(description="Get detailed information about a specific program")
async def get_program_details(program_id: int, ctx: Context) -> ProgramInfo:
    """
    Get detailed information about a specific program.
    
    Args:
        program_id: The ID of the program to retrieve
        ctx: The FastMCP context
        
    Returns:
        Detailed information about the program
    """
    try:
        logger.info(f"Getting details for program ID: {program_id}")
        
        lifespan_context = ctx.request_context.lifespan_context
        db_path = lifespan_context["db_path"]
        
        async with get_db_connection(db_path) as conn:
            # Query program_info table
            query = "SELECT * FROM program_info WHERE id = ?"
            cursor = await conn.execute(query, (program_id,))
            program_row = await cursor.fetchone()
            
            if program_row:
                # Create a clean program object
                program_info = ProgramInfo(
                    id=program_id,
                    name=program_row["name"] if "name" in program_row else f"Program {program_id}",
                    description=program_row["description"] if "description" in program_row else "No description available",
                    eligibility_criteria=program_row["criteria"] if "criteria" in program_row else "Not specified",
                    benefits=program_row["benefits"] if "benefits" in program_row else "Benefits information not available",
                    application_process=program_row["application"] if "application" in program_row else "Application process information not available"
                )
                
                return program_info
            else:
                return ProgramInfo(
                    id=program_id,
                    name=f"Program {program_id}",
                    description="Program not found"
                )
    
    except Exception as e:
        logger.error(f"Error in get_program_details: {e}")
        return ProgramInfo(
            id=program_id,
            name=f"Program {program_id}",
            description=f"Error retrieving program: {e}"
        )

# ----- Prompts for Response Generation -----

@eligibility_server.prompt()
def eligibility_response(programs: List[Dict], analysis: List[Dict], user_profile: Dict) -> List:
    """
    Generate a response about program eligibility.
    
    Args:
        programs: List of program information
        analysis: Eligibility analysis for each program
        user_profile: User profile information
    
    Returns:
        A list of formatted messages for the response
    """
    from mcp.server.fastmcp.prompts.base import AssistantMessage
    
    if not programs:
        return [AssistantMessage(
            "I searched our database but couldn't find specific programs matching your criteria. "
            "Could you provide more details about your situation? For example, your income level, "
            "family size, or specific needs you're looking for assistance with."
        )]
    
    # Create a helpful response with the program information
    response_text = "Based on what you've shared, I found these programs that might be relevant:\n\n"
    
    for i, (program, eligibility) in enumerate(zip(programs, analysis)):
        likelihood = eligibility.get("eligibility_likelihood", "Unknown")
        likelihood_emoji = {
            "High": "✅",
            "Medium": "⚠️",
            "Low": "❓",
            "Unknown": "ℹ️"
        }.get(likelihood, "ℹ️")
        
        response_text += f"{i+1}. {likelihood_emoji} **{program.get('name')}**\n"
        response_text += f"   {program.get('description')}\n"
        response_text += f"   **Eligibility**: {likelihood} likelihood of qualification\n"
        
        if eligibility.get("matching_criteria"):
            response_text += "   **Matching criteria**: " + ", ".join(eligibility.get("matching_criteria")) + "\n"
        
        if eligibility.get("missing_information"):
            response_text += "   **For better assessment, please provide**: " + ", ".join(eligibility.get("missing_information")) + "\n"
        
        response_text += f"   **Benefits**: {program.get('benefits')}\n"
        response_text += f"   **How to apply**: {program.get('application_process')}\n\n"
    
    response_text += "Would you like more specific information about any of these programs?"
    
    return [AssistantMessage(response_text)]

# ----- Resources for Program Information -----

@eligibility_server.resource("program://{program_id}/eligibility")
async def program_eligibility_resource(program_id: int) -> str:
    """
    Provide eligibility information for a specific program.
    
    Args:
        program_id: The ID of the program
    
    Returns:
        Formatted eligibility information
    """
    try:
        # Use sqlite directly for this simple resource
        conn = sqlite3.connect("program_db.sqlite")
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM program_info WHERE id = ?", (program_id,))
        program = cursor.fetchone()
        
        if program:
            eligibility_info = {
                "id": program_id,
                "name": program["name"],
                "eligibility_criteria": program["criteria"] if "criteria" in program else "Not specified"
            }
            return json.dumps(eligibility_info, indent=2)
        else:
            return json.dumps({"error": "Program not found"})
    except Exception as e:
        return json.dumps({"error": str(e)})
    finally:
        conn.close()

# Main entry point
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Eligibility MCP Server")
    parser.add_argument("--transport", type=str, default="stdio", choices=["stdio", "sse"], help="Transport protocol to use")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host for SSE transport")
    parser.add_argument("--port", type=int, default=8000, help="Port for SSE transport")
    
    args = parser.parse_args()
    
    if args.transport == "sse":
        eligibility_server.settings.host = args.host
        eligibility_server.settings.port = args.port
    
    eligibility_server.run(args.transport)