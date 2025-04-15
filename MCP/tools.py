import json
import datetime
import random
import re
from typing import Dict, List, Any, Optional
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('SocialBenefits-Tools')

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS

class Tools:
    """Collection of tools for the social benefits assistant."""
    
    def __init__(self, db_tool, ollama, faiss_index_path, grievance_db_tool=None, embeddings_model="all-MiniLM-L6-v2"):
        """Initialize the tools with shared dependencies."""
        self.db_tool = db_tool
        self.ollama = ollama
        # Store grievance_db_tool if provided, otherwise use main db_tool
        self.grievance_db_tool = grievance_db_tool if grievance_db_tool else db_tool
        
        # Initialize embeddings and FAISS components
        logger.info(f"Loading FAISS index from {faiss_index_path}")
        try:
            # Initialize the embeddings model
            self.embeddings = HuggingFaceEmbeddings(model_name=embeddings_model)
            
            # Load the FAISS index
            self.vector_store = FAISS.load_local(
                faiss_index_path, 
                self.embeddings,
                allow_dangerous_deserialization=True
            )
            
            # Create a retriever
            self.retriever = self.vector_store.as_retriever(
                search_type="similarity", 
                search_kwargs={"k": 3}
            )
            
            logger.info("FAISS index loaded successfully")
        except Exception as e:
            logger.error(f"Error loading FAISS index: {e}")
            raise
            
        # Define grievance-related prompts
        self.grievance_prompts = {
            "user_verification": """
You are a helpful government benefits assistant. The user has been identified with a USER ID.

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
4. Keep your response conversational and helpful
""",

            "status_check": """
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
4. Be helpful and conversational
""",

            "complaint_collection": """
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
5. Keep your response conversational
""",

            "ticket_creation": """
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
"""
        }
    
    # === PROGRAM INFO TOOLS ===
    
    def vector_search_tool(self, query: str) -> List[Dict]:
        """Search FAISS for relevant programs based on query."""
        try:
            logger.info(f"Searching FAISS for: '{query}'")
            
            # Use invoke() instead of deprecated get_relevant_documents()
            try:
                documents = self.retriever.invoke(query)
            except AttributeError:
                # Fallback if invoke doesn't work
                logger.warning("Using deprecated get_relevant_documents method")
                documents = self.retriever.get_relevant_documents(query)
            
            if not documents:
                logger.warning("No relevant documents found in FAISS search")
                return []
            
            # Extract document content and metadata
            results = []
            for doc in documents:
                program_id = doc.metadata.get("id")
                if program_id:
                    results.append({
                        "id": program_id,
                        "content": doc.page_content,
                        "metadata": doc.metadata
                    })
            
            logger.info(f"FAISS search returned {len(results)} results: {[r['id'] for r in results]}")
            return results
        except Exception as e:
            logger.error(f"Error in vector_search_tool: {e}")
            return []
    
    def program_details_tool(self, program_ids: List[int]) -> List[Dict]:
        """Get detailed program information from the database."""
        try:
            logger.info(f"Getting program details for IDs: {program_ids}")
            program_data = []
            
            # IMPORTANT CHANGE: Query program_info table instead of programs
            for program_id in program_ids:
                # Try to get program details from the program_info table
                query_result = self.db_tool.execute_query(
                    "SELECT * FROM program_info WHERE id = ?", 
                    (program_id,)
                )
                
                if query_result and len(query_result) > 0:
                    db_details = query_result[0]
                    
                    # Extract the name from the first column
                    name = db_details.get("name", f"Program {program_id}")
                    
                    # Parse the criteria and SQL from the text fields
                    eligibility_criteria = db_details.get("criteria", "Not specified")
                    # Try to make the criteria more readable
                    try:
                        if isinstance(eligibility_criteria, str) and eligibility_criteria.startswith("["):
                            eligibility_criteria = json.loads(eligibility_criteria)
                            eligibility_criteria = str(eligibility_criteria)
                    except:
                        pass
                        
                    # Extract other fields as needed
                    description = db_details.get("description", "No description available")
                    if not description:
                        # Try to extract description from name
                        description = name
                        
                    program_info = {
                        "id": program_id,
                        "name": name,
                        "eligibility_criteria": eligibility_criteria,
                        "description": description,
                        "benefits": "Benefits information not available in database",
                        "required_documents": "Required documents information not available in database",
                        "application_process": "Application process information not available in database"
                    }
                    program_data.append(program_info)
                    logger.info(f"Retrieved program {program_id}: {name}")
                else:
                    logger.warning(f"No details found for program ID {program_id}")
            
            logger.info(f"Retrieved details for {len(program_data)} out of {len(program_ids)} programs")
            return program_data
        except Exception as e:
            logger.error(f"Error in program_details_tool: {e}")
            return []
    
    def analyze_eligibility_tool(self, programs: List[Dict], user_profile: Dict) -> List[Dict]:
        """Analyze program eligibility based on user profile."""
        try:
            logger.info(f"Analyzing eligibility for {len(programs)} programs with user profile: {user_profile}")
            
            # If no programs, return empty analysis
            if not programs:
                logger.warning("No programs available for eligibility analysis")
                return [{"error": "No Programs Available", "matching_criteria": ["Insufficient Information"]}]
            
            # If user profile is empty, return basic analysis
            if not user_profile or all(not val for val in user_profile.values() if val is not None):
                logger.warning("User profile is empty, cannot perform detailed eligibility analysis")
                return [
                    {
                        "program_id": p["id"],
                        "program_name": p["name"],
                        "eligibility_likelihood": "Unknown", 
                        "matching_criteria": [],
                        "missing_information": ["User details required for assessment"]
                    } 
                    for p in programs
                ]
            
            # Use LLM to analyze eligibility
            eligibility_prompt = f"""
            Analyze eligibility for these programs based on user profile:
            
            Programs:
            {json.dumps(programs, indent=2)}
            
            User Profile:
            {json.dumps(user_profile, indent=2)}
            
            For each program, determine:
            1. Eligibility likelihood (High/Medium/Low)
            2. Key matching criteria
            3. Any missing information needed for better assessment
            
            Return a JSON array with one object per program, each containing:
            - program_id
            - program_name
            - eligibility_likelihood
            - matching_criteria
            - missing_information
            """
            
            logger.info("Sending eligibility analysis prompt to LLM")
            
            # Generate eligibility analysis
            analysis_response = self.ollama.generate(
                "You are a program eligibility analysis system. Respond with JSON only.",
                eligibility_prompt,
                "eligibility_analysis"
            )
            
            logger.info(f"Received eligibility analysis response (length: {len(analysis_response)})")
            
            # Try to extract JSON from the response
            try:
                # Find JSON in the response (may be surrounded by text)
                import re
                json_match = re.search(r'\[.*\]', analysis_response, re.DOTALL)
                if json_match:
                    analysis_data = json.loads(json_match.group(0))
                    logger.info(f"Successfully parsed eligibility analysis for {len(analysis_data)} programs")
                else:
                    # Fallback to simple analysis
                    logger.warning("Could not extract JSON from LLM response, using fallback analysis")
                    analysis_data = []
                    for program in programs:
                        analysis_data.append({
                            "program_id": program["id"],
                            "program_name": program["name"],
                            "eligibility_likelihood": "Medium",
                            "matching_criteria": ["Basic criteria may match user profile"],
                            "missing_information": ["Detailed user circumstances"]
                        })
                
                return analysis_data
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse eligibility analysis JSON: {e}")
                # Return basic analysis as fallback
                return [
                    {
                        "program_id": p["id"],
                        "program_name": p["name"],
                        "eligibility_likelihood": "Medium", 
                        "matching_criteria": [],
                        "missing_information": ["Detailed user circumstances"]
                    } 
                    for p in programs
                ]
                
        except Exception as e:
            logger.error(f"Error in analyze_eligibility_tool: {e}")
            return []
    
    def extract_user_details_tool(self, query: str, conversation_history: List[Dict]) -> Dict:
        """Extract user profile details from query and conversation history."""
        try:
            logger.info(f"Extracting user details from query: '{query}'")
            
            # Create context from conversation history
            history_text = "\n".join([
                f"{msg['role']}: {msg['content']}" 
                for msg in conversation_history[-5:]  # Last 5 messages
            ])
            
            extraction_prompt = f"""
            Extract user profile information from this conversation:
            
            Current Query: {query}
            
            Conversation History:
            {history_text}
            
            Extract the following information if present (respond with JSON):
            - income_level: (e.g., low, medium, high, or specific amount)
            - family_size: (number of people)
            - location: (any location information)
            - housing_status: (e.g., renting, homeowner, homeless)
            - employment_status: (e.g., employed, unemployed, part-time)
            - age: (age of the person)
            - age_group: (e.g., senior, adult, youth)
            - marital_status: (e.g., single, married, divorced)
            - gender: (if mentioned)
            - disabilities: (any mentioned disabilities)
            - other_factors: (other relevant eligibility factors)
            
            Only include fields that are explicitly mentioned or can be confidently inferred.
            """
            
            logger.info("Sending user information extraction prompt to LLM")
            
            extraction_response = self.ollama.generate(
                "You are a user information extraction system. Respond with JSON only.",
                extraction_prompt,
                "user_extraction"
            )
            
            logger.info(f"Received user extraction response (length: {len(extraction_response)})")
            
            # Try to extract JSON from the response
            try:
                # Find JSON in the response
                import re
                json_match = re.search(r'\{.*\}', extraction_response, re.DOTALL)
                if json_match:
                    user_data = json.loads(json_match.group(0))
                    logger.info(f"Successfully extracted user profile: {user_data}")
                else:
                    # Return empty object if no JSON found
                    logger.warning("Could not extract JSON from user extraction response")
                    user_data = {}
                
                return user_data
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse user details JSON: {e}")
                return {}
                
        except Exception as e:
            logger.error(f"Error in extract_user_details_tool: {e}")
            return {}
    
    def conversation_formatter_tool(self, 
                                    query: str, 
                                    programs: List[Dict], 
                                    eligibility_analysis: List[Dict],
                                    user_profile: Dict,
                                    persona: Dict) -> str:
        """Format analytical results into conversational, human-like responses."""
        try:
            logger.info(f"Formatting conversational response for {len(programs)} programs")
            logger.info(f"User profile for conversation: {user_profile}")
            
            # Log program names for debugging
            if programs:
                program_names = [p.get("name", f"Program {p.get('id', 'unknown')}") for p in programs]
                logger.info(f"Programs to discuss: {program_names}")
            else:
                logger.info("No programs available for conversation formatting")
            
            # Create a comprehensive prompt for the LLM
            formatter_prompt = f"""
            USER QUERY: {query}
            
            PROGRAM INFORMATION:
            {json.dumps(programs, indent=2)}
            
            ELIGIBILITY ANALYSIS:
            {json.dumps(eligibility_analysis, indent=2)}
            
            USER PROFILE:
            {json.dumps(user_profile, indent=2)}
            
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
            
            logger.info("Sending conversation formatting prompt to LLM")
            
            # Generate the conversational response
            response = self.ollama.generate(
                "You are a helpful and friendly social benefits assistant. Respond conversationally.",
                formatter_prompt,
                "conversation_formatter"
            )
            
            logger.info(f"Generated conversational response (length: {len(response)})")
            
            return response
            
        except Exception as e:
            logger.error(f"Error in conversation_formatter_tool: {e}")
            return "I'm sorry, I'm having trouble finding information about that program right now. Could you tell me more about what kind of assistance you're looking for?"

    # === GRIEVANCE HANDLING TOOLS ===
    
    def identify_user_id_tool(self, query: str) -> Dict:
        """Identify if the user input contains a valid USER ID format."""
        try:
            logger.info(f"Checking if query contains USER ID: '{query}'")
            
            # Check for USER### format
            user_id_match = re.search(r'USER\d{3}', query)
            
            if user_id_match:
                user_id = user_id_match.group(0)
                logger.info(f"Found USER ID: {user_id}")
                return {
                    "found": True,
                    "user_id": user_id
                }
            else:
                logger.info("No USER ID found in query")
                return {
                    "found": False,
                    "user_id": None
                }
                
        except Exception as e:
            logger.error(f"Error in identify_user_id_tool: {e}")
            return {
                "found": False,
                "user_id": None,
                "error": str(e)
            }
    
    def verify_user_tool(self, user_id: str) -> Dict:
        """Verify if a user ID exists and retrieve user and program information."""
        try:
            logger.info(f"Verifying user ID: {user_id}")
            
            # Query the program_membership table
            user_result = self.grievance_db_tool.execute_query(
                "SELECT * FROM program_membership WHERE user_id = ?",
                (user_id,)
            )
            
            if not user_result or len(user_result) == 0:
                logger.warning(f"User ID not found: {user_id}")
                return {
                    "verified": False,
                    "user_details": None,
                    "program_details": None
                }
            
            user_details = user_result[0]
            logger.info(f"Found user: {user_details.get('user_name')}")
            
            # Get program details if available
            program_id = user_details.get("program_id")
            if program_id:
                program_result = self.grievance_db_tool.execute_query(
                    "SELECT * FROM registry WHERE program_id = ?",
                    (program_id,)
                )
                
                if program_result and len(program_result) > 0:
                    program_details = program_result[0]
                    logger.info(f"Found program: {program_details.get('program_name')}")
                else:
                    logger.warning(f"Program ID {program_id} not found for user {user_id}")
                    program_details = None
            else:
                logger.warning(f"No program ID associated with user {user_id}")
                program_details = None
            
            return {
                "verified": True,
                "user_details": user_details,
                "program_details": program_details
            }
            
        except Exception as e:
            logger.error(f"Error in verify_user_tool: {e}")
            return {
                "verified": False,
                "user_details": None,
                "program_details": None,
                "error": str(e)
            }
    
    def process_complaint_tool(self, complaint: str, previous_complaints: List[str], is_follow_up: bool) -> Dict:
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
            
            analysis_response = self.ollama.generate(
                "You are a complaint analysis system. Respond with JSON only.",
                analysis_prompt,
                "complaint_analysis"
            )
            
            logger.info(f"Received complaint analysis response (length: {len(analysis_response)})")
            
            # Try to extract JSON from the response
            try:
                import re
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
                
                return {
                    "complaint": all_complaints,
                    "enough_detail": analysis.get("enough_detail", False),
                    "program_mentioned": analysis.get("program_mentioned", "Unspecified"),
                    "issue_category": analysis.get("issue_category", "Other"),
                    "missing_information": analysis.get("missing_information", [])
                }
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse complaint analysis JSON: {e}")
                return {
                    "complaint": all_complaints,
                    "enough_detail": False,
                    "program_mentioned": "Unspecified",
                    "issue_category": "Other",
                    "missing_information": ["Nature of the issue", "When the issue occurred", "Impact of the issue"],
                    "error": str(e)
                }
            
        except Exception as e:
            logger.error(f"Error in process_complaint_tool: {e}")
            return {
                "complaint": complaint,
                "enough_detail": False,
                "error": str(e)
            }
    
    def create_ticket_tool(self, user_id: str, program_id: int, complaint: str) -> Dict:
        """Create a ticket in the database for a grievance."""
        try:
            logger.info(f"Creating ticket for user {user_id}, program {program_id}")
            
            # Generate a ticket number
            ticket_id = f"TKT-{datetime.datetime.now().strftime('%Y%m%d')}-{random.randint(1000, 9999)}"
            now = datetime.datetime.now().isoformat()
            
            # Insert ticket into database
            try:
                self.grievance_db_tool.execute_query(
                    """
                    INSERT INTO ticket 
                    (ticket_id, user_id, program_id, description, status, priority, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (ticket_id, user_id, program_id, complaint, 'OPEN', 'MEDIUM', now, now)
                )
                
                logger.info(f"Successfully created ticket: {ticket_id}")
                
                return {
                    "success": True,
                    "ticket_id": ticket_id,
                    "created_at": now,
                    "status": "OPEN"
                }
                
            except Exception as db_error:
                logger.error(f"Database error creating ticket: {db_error}")
                
                # Return a simulated ticket for graceful failure
                fallback_ticket_id = f"SIM-{datetime.datetime.now().strftime('%Y%m%d')}-{random.randint(1000, 9999)}"
                logger.info(f"Providing simulated ticket: {fallback_ticket_id}")
                
                return {
                    "success": False,
                    "simulated": True,
                    "ticket_id": fallback_ticket_id,
                    "created_at": now,
                    "status": "PENDING",
                    "error": str(db_error)
                }
                
        except Exception as e:
            logger.error(f"Error in create_ticket_tool: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def check_status_tool(self, user_id: str, ticket_id: str = None) -> Dict:
        """Check status of a program enrollment or specific ticket."""
        try:
            logger.info(f"Checking status for user: {user_id}, ticket: {ticket_id}")
            
            # If ticket_id is provided, check ticket status
            if ticket_id:
                ticket_result = self.grievance_db_tool.execute_query(
                    "SELECT * FROM ticket WHERE ticket_id = ?",
                    (ticket_id,)
                )
                
                if ticket_result and len(ticket_result) > 0:
                    ticket = ticket_result[0]
                    logger.info(f"Found ticket {ticket_id} with status: {ticket.get('status')}")
                    
                    return {
                        "found": True,
                        "type": "ticket",
                        "ticket_id": ticket_id,
                        "status": ticket.get("status"),
                        "description": ticket.get("description"),
                        "created_at": ticket.get("created_at"),
                        "updated_at": ticket.get("updated_at"),
                        "resolution_notes": ticket.get("resolution_notes")
                    }
                else:
                    logger.warning(f"Ticket not found: {ticket_id}")
                    return {
                        "found": False,
                        "type": "ticket",
                        "ticket_id": ticket_id
                    }
            
            # Otherwise, check program enrollment status
            user_result = self.grievance_db_tool.execute_query(
                "SELECT * FROM program_membership WHERE user_id = ?",
                (user_id,)
            )
            
            if user_result and len(user_result) > 0:
                user = user_result[0]
                
                # Get program details
                program_id = user.get("program_id")
                if program_id:
                    program_result = self.grievance_db_tool.execute_query(
                        "SELECT * FROM registry WHERE program_id = ?",
                        (program_id,)
                    )
                    program = program_result[0] if program_result and len(program_result) > 0 else None
                else:
                    program = None
                
                logger.info(f"Found user {user_id} with status: {user.get('status')}")
                
                return {
                    "found": True,
                    "type": "program",
                    "user_id": user_id,
                    "status": user.get("status"),
                    "enrollment_date": user.get("enrollment_date"),
                    "program_id": program_id,
                    "program_name": program.get("program_name") if program else "Unknown Program"
                }
            else:
                logger.warning(f"User not found: {user_id}")
                return {
                    "found": False,
                    "type": "program",
                    "user_id": user_id
                }
                
        except Exception as e:
            logger.error(f"Error in check_status_tool: {e}")
            return {
                "found": False,
                "error": str(e)
            }
    
    def format_grievance_response_tool(self, 
                                      response_type: str, 
                                      user_details: Dict, 
                                      program_details: Dict = None,
                                      complaint: str = None,
                                      complaint_analysis: Dict = None,
                                      ticket_details: Dict = None,
                                      persona: Dict = None) -> str:
        """Format a conversational response for grievance handling."""
        try:
            logger.info(f"Formatting grievance response type: {response_type}")
            
            # Select the appropriate template based on response_type
            if response_type == "user_verification":
                template = self.grievance_prompts["user_verification"]
                prompt = template.format(
                    user_name=user_details.get("user_name", "User"),
                    program_name=program_details.get("program_name", "Unknown Program") if program_details else "Unknown Program",
                    enrollment_date=user_details.get("enrollment_date", "Unknown"),
                    status=user_details.get("status", "Unknown"),
                    program_description=program_details.get("description", "No program description available") if program_details else "No program description available"
                )
            
            elif response_type == "status_check":
                template = self.grievance_prompts["status_check"]
                prompt = template.format(
                    user_name=user_details.get("user_name", "User"),
                    program_name=user_details.get("program_name", program_details.get("program_name", "Unknown Program") if program_details else "Unknown Program"),
                    enrollment_date=user_details.get("enrollment_date", "Unknown"),
                    status=user_details.get("status", "Unknown")
                )
            
            elif response_type == "complaint_collection":
                template = self.grievance_prompts["complaint_collection"]
                prompt = template.format(
                    user_name=user_details.get("user_name", "User"),
                    program_name=program_details.get("program_name", "Unknown Program") if program_details else "Unknown Program",
                    complaint=complaint
                )
                
                if complaint_analysis and complaint_analysis.get("missing_information"):
                    missing_info = complaint_analysis.get("missing_information")
                    prompt += f"\n\nSpecific information that would be helpful:\n{json.dumps(missing_info)}"
            
            elif response_type == "ticket_creation":
                template = self.grievance_prompts["ticket_creation"]
                prompt = template.format(
                    user_name=user_details.get("user_name", "User"),
                    program_name=program_details.get("program_name", "Unknown Program") if program_details else "Unknown Program",
                    ticket_id=ticket_details.get("ticket_id", "Unknown"),
                    created_at=ticket_details.get("created_at", datetime.datetime.now().strftime("%Y-%m-%d %H:%M")),
                    complaint=complaint
                )
                
                if ticket_details.get("simulated"):
                    prompt += "\n\nNOTE: Due to a technical issue, this ticket has been created in our temporary system. A customer service representative will transfer this to our main system."
            
            else:
                logger.warning(f"Unknown response type: {response_type}")
                prompt = f"The user has asked about a grievance. Please provide a helpful response regarding their {response_type}."
            
            # Add persona information if provided
            if persona:
                persona_str = json.dumps(persona, indent=2)
                prompt += f"\n\nPERSONA TO USE:\n{persona_str}\n\nKeep your response conversational and aligned with this persona."
            
            logger.info("Sending grievance formatting prompt to LLM")
            
            # Generate the response
            response = self.ollama.generate(
                "You are a helpful government benefits assistant. Respond conversationally.",
                prompt,
                "grievance_formatter"
            )
            
            logger.info(f"Generated grievance response (length: {len(response)})")
            
            return response
            
        except Exception as e:
            logger.error(f"Error in format_grievance_response_tool: {e}")
            return "I'm sorry, but I'm having technical difficulties processing your request. Please try again or contact our support team directly for assistance with your issue."