"""
Eligibility subsystem for the Social Benefits Assistant.

This subsystem is responsible for:
1. Finding relevant programs
2. Extracting user details
3. Analyzing program eligibility
"""

import json
import logging
import re
from typing import Dict, List, Any, Optional

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS

# Set up logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('SocialBenefits-EligibilitySubsystem')

class EligibilitySubsystem:
    """
    Subsystem for program eligibility analysis.
    
    Responsible for:
    - Extracting user details from conversation
    - Searching for relevant programs
    - Analyzing program eligibility
    """
    
    def __init__(self, db_tool, ollama_client, faiss_index_path, conversation_manager):
        """Initialize the eligibility subsystem."""
        self.db_tool = db_tool
        self.ollama_client = ollama_client
        self.conversation_manager = conversation_manager
        
        # Initialize embeddings and FAISS components
        logger.info(f"Loading FAISS index from {faiss_index_path}")
        try:
            # Initialize the embeddings model
            self.embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
            
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
    
    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict:
        """Call a tool provided by this subsystem."""
        logger.info(f"Calling eligibility subsystem tool: {name}")
        
        if name == "extract_user_details":
            return await self.extract_user_details(arguments["query"], arguments["thread_id"])
        elif name == "search_programs":
            return await self.search_programs(arguments["query"])
        elif name == "analyze_eligibility":
            return await self.analyze_eligibility(arguments["program_ids"], arguments.get("user_profile"))
        else:
            logger.error(f"Unknown tool: {name}")
            return json.dumps({"error": f"Unknown tool: {name}"})
    
    async def extract_user_details(self, query: str, thread_id: str) -> str:
        """Extract user profile details from query and conversation history."""
        try:
            logger.info(f"Extracting user details from query: '{query}'")
            
            # Get conversation history
            context = self.conversation_manager.get_thread_context(thread_id)
            conversation_history = context.get("conversation_history", [])
            
            # Create context from conversation history - get last 5 messages
            history_text = "\n".join([
                f"{msg['role']}: {msg['content']}" 
                for msg in conversation_history[-5:]
            ])
            
            extraction_prompt = f"""
            Extract user profile information from this conversation:
            
            CURRENT QUERY: "{query}"
            
            CONVERSATION HISTORY:
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
            
            extraction_response = self.ollama_client.generate(
                "You are a user information extraction system. Respond with JSON only.",
                extraction_prompt,
                f"{thread_id}_user_extraction"
            )
            
            # Try to extract JSON from the response
            try:
                json_match = re.search(r'\{.*\}', extraction_response, re.DOTALL)
                if json_match:
                    user_data = json.loads(json_match.group(0))
                    logger.info(f"Successfully extracted user profile: {user_data}")
                    return json.dumps(user_data)
                else:
                    # Return empty object if no JSON found
                    logger.warning("Could not extract JSON from user extraction response")
                    return json.dumps({})
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse user details JSON: {e}")
                return json.dumps({})
                
        except Exception as e:
            logger.error(f"Error in extract_user_details_tool: {e}")
            return json.dumps({})
    
    async def search_programs(self, query: str) -> str:
        """Search for relevant programs based on query."""
        try:
            logger.info(f"Searching for programs matching: '{query}'")
            
            # Use FAISS vector search
            try:
                documents = self.retriever.invoke(query)
            except AttributeError:
                # Fallback for older LangChain versions
                documents = self.retriever.get_relevant_documents(query)
            
            if not documents:
                logger.warning("No relevant documents found in FAISS search")
                return json.dumps([])
            
            # Extract program IDs
            program_ids = []
            for doc in documents:
                program_id = doc.metadata.get("id")
                if program_id and program_id not in program_ids:
                    program_ids.append(program_id)
            
            logger.info(f"Found {len(program_ids)} relevant programs: {program_ids}")
            return json.dumps(program_ids)
            
        except Exception as e:
            logger.error(f"Error in search_programs: {e}")
            return json.dumps([])
    
    async def analyze_eligibility(self, program_ids: List[int], user_profile: Optional[Dict] = None) -> str:
        """Analyze program eligibility based on user profile."""
        try:
            logger.info(f"Analyzing eligibility for {len(program_ids)} programs")
            
            # Get program details from database
            programs = []
            for program_id in program_ids:
                # Query program_info table
                query_result = self.db_tool.execute_query(
                    "SELECT * FROM program_info WHERE id = ?", 
                    (program_id,)
                )
                
                if query_result and len(query_result) > 0:
                    program = query_result[0]
                    
                    # Create a clean program object
                    program_info = {
                        "id": program_id,
                        "name": program.get("name", f"Program {program_id}"),
                        "description": program.get("description", "No description available"),
                        "eligibility_criteria": program.get("criteria", "Not specified"),
                        "benefits": program.get("benefits", "Benefits information not available"),
                        "application_process": program.get("application", "Application process information not available")
                    }
                    
                    programs.append(program_info)
            
            logger.info(f"Retrieved {len(programs)} programs from database")
            
            # If no programs or no user profile, return basic result
            if not programs:
                return json.dumps({
                    "programs": [],
                    "analysis": []
                })
            
            if not user_profile or len(user_profile) == 0:
                # Basic analysis without user profile
                return json.dumps({
                    "programs": programs,
                    "analysis": [
                        {
                            "program_id": p["id"],
                            "program_name": p["name"],
                            "eligibility_likelihood": "Unknown",
                            "matching_criteria": [],
                            "missing_information": ["User details required for assessment"]
                        }
                        for p in programs
                    ]
                })
            
            # Use LLM to analyze eligibility
            analysis_prompt = f"""
            Analyze eligibility for these programs based on user profile:
            
            PROGRAMS:
            {json.dumps(programs, indent=2)}
            
            USER PROFILE:
            {json.dumps(user_profile, indent=2)}
            
            For each program, determine:
            1. Eligibility likelihood (High/Medium/Low/Unknown)
            2. Key matching criteria
            3. Any missing information needed for better assessment
            
            Return a JSON array with one object per program, each containing:
            - program_id
            - program_name
            - eligibility_likelihood
            - matching_criteria (array of strings)
            - missing_information (array of strings)
            """
            
            logger.info("Sending eligibility analysis prompt to LLM")
            
            analysis_response = self.ollama_client.generate(
                "You are an eligibility analysis system. Respond with valid JSON only.",
                analysis_prompt,
                "eligibility_analysis"
            )
            
            # Try to extract JSON from the response
            try:
                json_match = re.search(r'\[.*\]', analysis_response, re.DOTALL)
                if json_match:
                    analysis = json.loads(json_match.group(0))
                    logger.info(f"Successfully parsed eligibility analysis for {len(analysis)} programs")
                else:
                    # Fallback to simple analysis
                    logger.warning("Could not extract JSON from analysis response, using fallback")
                    analysis = [
                        {
                            "program_id": p["id"],
                            "program_name": p["name"],
                            "eligibility_likelihood": "Medium",
                            "matching_criteria": ["Basic criteria may match user profile"],
                            "missing_information": ["Detailed user circumstances"]
                        }
                        for p in programs
                    ]
                
                # Return combined result
                return json.dumps({
                    "programs": programs,
                    "analysis": analysis
                })
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse eligibility analysis JSON: {e}")
                
                # Fallback analysis
                simple_analysis = [
                    {
                        "program_id": p["id"],
                        "program_name": p["name"],
                        "eligibility_likelihood": "Unknown",
                        "matching_criteria": [],
                        "missing_information": ["Detailed eligibility assessment failed"]
                    }
                    for p in programs
                ]
                
                return json.dumps({
                    "programs": programs,
                    "analysis": simple_analysis
                })
                
        except Exception as e:
            logger.error(f"Error in analyze_eligibility: {e}")
            return json.dumps({
                "programs": [],
                "analysis": [],
                "error": str(e)
            })
    
    async def get_program_details(self, program_id: int) -> Dict:
        """Get detailed information about a specific program."""
        try:
            # Query program_info table
            query_result = self.db_tool.execute_query(
                "SELECT * FROM program_info WHERE id = ?", 
                (program_id,)
            )
            
            if query_result and len(query_result) > 0:
                program = query_result[0]
                
                # Create a clean program object
                program_info = {
                    "id": program_id,
                    "name": program.get("name", f"Program {program_id}"),
                    "description": program.get("description", "No description available"),
                    "eligibility_criteria": program.get("criteria", "Not specified"),
                    "benefits": program.get("benefits", "Benefits information not available"),
                    "application_process": program.get("application", "Application process information not available")
                }
                
                return program_info
            else:
                return {"id": program_id, "error": "Program not found"}
        except Exception as e:
            logger.error(f"Error retrieving program details: {e}")
            return {"id": program_id, "error": str(e)}