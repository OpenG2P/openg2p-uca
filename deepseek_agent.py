import json
import sqlite3
import threading
import random
import datetime
import requests
import os
from typing import Dict, List, Tuple, Optional, Any

# LangChain imports for FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS

# ------------------ Core Components ------------------

class OllamaClient:
    """Ollama API client with conversation history management.
    
    This client handles communication with the Ollama API server,
    maintains conversation history, and manages thread-specific contexts.
    """
    
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "deepseek-r1:8b", temperature: float = 0.1):
        """Initialize the Ollama client.
        
        Args:
            base_url: Base URL for the Ollama API
            model: Name of the model to use
            temperature: Temperature for response generation (0.0-1.0)
        """
        self.base_url = base_url
        self.model = model
        self.temperature = temperature
        self.conversations = {}  # Thread-specific conversation histories
        self._validate_connection()
    
    def _validate_connection(self):
        """Validate connection to the Ollama server and log status."""
        try:
            response = requests.get(f"{self.base_url}/api/version")
            if response.status_code == 200:
                print(f"Connected to Ollama server: {response.json().get('version', 'unknown')}")
            else:
                print(f"Warning: Ollama server returned status {response.status_code}")
        except Exception as e:
            print(f"Warning: Could not connect to Ollama server at {self.base_url}: {e}")
            print("Will attempt to use the server anyway when needed.")
    
    def _get_thread(self, thread_id: str) -> List[Dict[str, str]]:
        """Get or initialize a conversation thread.
        
        Args:
            thread_id: Unique identifier for the conversation thread
            
        Returns:
            List of message dictionaries for the thread
        """
        if thread_id not in self.conversations:
            self.conversations[thread_id] = []
        return self.conversations[thread_id]
    
    def generate(self, system_prompt: str, prompt: str, thread_id: str = "default") -> str:
        """Generate a response using the Ollama API with conversation history.
        
        Args:
            system_prompt: System instructions for the model
            prompt: User query
            thread_id: Unique identifier for the conversation thread
            
        Returns:
            Generated response text
        """
        try:
            # Get the conversation history for this thread
            messages = self._get_thread(thread_id)
            
            # Add the new user message
            messages.append({"role": "user", "content": prompt})
            
            # Prepare the full message list with system prompt
            full_messages = [
                {"role": "system", "content": system_prompt},
                *messages
            ]
            
            # Make the API call
            response = requests.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": full_messages,
                    "temperature": self.temperature,
                    "stream": False
                }
            )
            
            # Parse the response
            result = response.json()
            assistant_response = result["message"]["content"]
            
            # Add the assistant response to the conversation history
            messages.append({"role": "assistant", "content": assistant_response})
            
            return assistant_response
        except Exception as e:
            error_message = f"Error: {str(e)}"
            print(error_message)
            return error_message
    
    def clear_thread(self, thread_id: str):
        """Clear the conversation history for a specific thread.
        
        Args:
            thread_id: Unique identifier for the conversation thread
        """
        if thread_id in self.conversations:
            self.conversations[thread_id] = []

class SQLDatabaseTool:
    """SQLite database interface with connection pooling and error handling.
    
    This tool provides safe, thread-friendly access to the SQLite database
    containing program information and grievance tickets.
    """
    
    def __init__(self, db_path: str):
        """Initialize the SQL database tool.
        
        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = self._resolve_db_path(db_path)
        self.lock = threading.Lock()  # Thread safety for database operations
        
        # Validate database on initialization
        self._validate_database()
    
    def _resolve_db_path(self, db_path: str) -> str:
        """Resolve the database path, handling various formats.
        
        Args:
            db_path: Path to the SQLite database, possibly with sqlite:/// prefix
            
        Returns:
            Resolved database path
        """
        # Remove sqlite:/// prefix if present
        if db_path.startswith('sqlite:///'):
            db_path = db_path[10:]
        
        # Check if the path exists
        if not os.path.isfile(db_path):
            # Try current working directory
            cwd_path = os.path.join(os.getcwd(), db_path)
            if os.path.isfile(cwd_path):
                db_path = cwd_path
            else:
                print(f"Warning: Database file not found at {db_path}. Will attempt to create if needed.")
        
        print(f"Using database at: {db_path}")
        return db_path
    
    def _validate_database(self):
        """Validate database structure and create tables if needed."""
        try:
            with self.lock, sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Check for programs table
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='programs'")
                if not cursor.fetchone():
                    print("Creating programs table...")
                    cursor.execute("""
                    CREATE TABLE programs (
                        id INTEGER PRIMARY KEY,
                        name TEXT NOT NULL,
                        description TEXT,
                        eligibility_criteria TEXT,
                        benefits TEXT,
                        required_documents TEXT,
                        application_process TEXT
                    )
                    """)
                
                # Check for grievances table
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='grievances'")
                if not cursor.fetchone():
                    print("Creating grievances table...")
                    cursor.execute("""
                    CREATE TABLE grievances (
                        id INTEGER PRIMARY KEY,
                        ticket_number TEXT UNIQUE,
                        user_id TEXT,
                        program_id INTEGER,
                        description TEXT,
                        status TEXT,
                        created_at TEXT,
                        updated_at TEXT,
                        FOREIGN KEY (program_id) REFERENCES programs (id)
                    )
                    """)
                
                conn.commit()
                print("Database structure validated")
                
        except Exception as e:
            print(f"Error validating database: {e}")
    
    def get_program_details(self, program_id: int) -> Dict:
        """Get program details by ID.
        
        Args:
            program_id: ID of the program to retrieve
            
        Returns:
            Dictionary with program details
        """
        try:
            with self.lock, sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM programs WHERE id = ?", (program_id,))
                result = cursor.fetchone()
                return dict(result) if result else {}
        except Exception as e:
            print(f"Error getting program details: {e}")
            return {}
    
    def execute_query(self, query: str, params: tuple = ()) -> List[Dict]:
        """Execute an SQL query with parameters.
        
        Args:
            query: SQL query to execute
            params: Query parameters
            
        Returns:
            List of result dictionaries
        """
        try:
            with self.lock, sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(query, params)
                
                if query.strip().upper().startswith("SELECT"):
                    return [dict(row) for row in cursor.fetchall()]
                else:
                    conn.commit()
                    return [{"affected_rows": cursor.rowcount}]
        except Exception as e:
            print(f"Error executing query: {e}")
            return [{"error": str(e)}]
    
    def create_grievance_ticket(self, user_id: str, program_id: int, description: str) -> Dict:
        """Create a new grievance ticket.
        
        Args:
            user_id: User identifier
            program_id: ID of the program related to the grievance
            description: Description of the grievance
            
        Returns:
            Dictionary with ticket information
        """
        try:
            # Generate ticket number
            now = datetime.datetime.now()
            ticket_number = f"GRV-{now.strftime('%Y%m%d')}-{random.randint(1000, 9999)}"
            
            with self.lock, sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                created_at = now.isoformat()
                cursor.execute(
                    """
                    INSERT INTO grievances
                    (ticket_number, user_id, program_id, description, status, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (ticket_number, user_id, program_id, description, "OPEN", created_at, created_at)
                )
                
                conn.commit()
                
                return {
                    "ticket_number": ticket_number,
                    "status": "OPEN",
                    "created_at": created_at
                }
        except Exception as e:
            print(f"Error creating grievance ticket: {e}")
            # Return simulated ticket if database operation fails
            return {
                "ticket_number": f"GRV-{datetime.datetime.now().strftime('%Y%m%d')}-{random.randint(1000, 9999)}",
                "status": "PENDING",
                "created_at": datetime.datetime.now().isoformat(),
                "note": "Ticket created in memory only due to database error"
            }

# ------------------ Agent Implementations ------------------

class ProgramAgent:
    """Specialist agent for program eligibility inquiries using LangChain FAISS.
    
    This agent handles queries about programs, eligibility, and benefits by retrieving
    information from a FAISS vector store and SQL database.
    """
    
    def __init__(self, db_tool: SQLDatabaseTool, ollama: OllamaClient, 
                 faiss_index_path: str, embeddings_model: str = "all-MiniLM-L6-v2"):
        """Initialize the Program Agent.
        
        Args:
            db_tool: SQLDatabaseTool instance
            ollama: OllamaClient instance
            faiss_index_path: Path to the FAISS index
            embeddings_model: Name of the embeddings model
        """
        self.db_tool = db_tool
        self.ollama = ollama
        
        # Initialize LangChain components
        print(f"Loading FAISS index from {faiss_index_path}")
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
            
            print("FAISS index loaded successfully")
        except Exception as e:
            print(f"Error loading FAISS index: {e}")
            raise
        
        # Define the system prompt for this agent
        self.system_prompt = """You are a Program Information Agent specializing in social benefit programs. Your role is to provide accurate information about program eligibility, benefits, and application processes.

INSTRUCTIONS:
1. INFORMATION RETRIEVAL:
   - Use only information from the provided program details
   - Never invent program information or eligibility criteria
   - If you don't have certain information, acknowledge the limitation

2. ELIGIBILITY ASSESSMENT:
   - Carefully compare user circumstances against program requirements
   - Express eligibility as a probability (High/Medium/Low likelihood)
   - Request specific information if needed for better assessment

3. RESPONSE STRUCTURE:
   - Program name and brief description
   - Key eligibility criteria
   - Benefits provided
   - Application process and required documents
   - Next steps for the user

4. QUALITY STANDARDS:
   - Use plain language that anyone can understand
   - Be thorough but concise (2-3 paragraphs maximum)
   - For multiple programs, list in order of relevance
   - Include specific numerical values when available (e.g., income thresholds)

Remember: Your goal is to help users navigate complex benefit systems with clear, accurate information."""
    
    def process(self, query: str, thread_id: str) -> str:
        """Process a program information query.
        
        Args:
            query: User query
            thread_id: Thread identifier
            
        Returns:
            Generated response
        """
        try:
            # Use LangChain's retriever to get relevant documents
            print(f"Searching FAISS for: {query}")
            documents = self.retriever.get_relevant_documents(query)
            
            if not documents:
                print("No relevant documents found")
                return "I couldn't find any programs matching your query. Could you provide more details about what you're looking for?"
            
            # Extract program IDs and gather database information
            program_data = []
            for doc in documents:
                program_id = doc.metadata.get("id")
                if program_id:
                    # Get additional details from database
                    db_details = self.db_tool.get_program_details(program_id)
                    
                    program_data.append({
                        "id": program_id,
                        "description": doc.page_content,
                        "name": db_details.get("name", f"Program {program_id}"),
                        "eligibility_criteria": db_details.get("eligibility_criteria", "Not specified"),
                        "benefits": db_details.get("benefits", "Not specified"),
                        "required_documents": db_details.get("required_documents", "Not specified"),
                        "application_process": db_details.get("application_process", "Not specified")
                    })
            
            # Prepare the prompt for the LLM
            enriched_prompt = f"""
            User Query: {query}
            
            Retrieved Program Information:
            {json.dumps(program_data, indent=2)}
            
            Based on this information, please provide a helpful response about these programs
            and their eligibility criteria. If the query asks about eligibility for a specific
            situation, assess the likelihood of eligibility based on the criteria.
            """
            
            # Generate the response
            return self.ollama.generate(self.system_prompt, enriched_prompt, f"{thread_id}_program")
        
        except Exception as e:
            print(f"Error in ProgramAgent: {e}")
            return "I encountered an error while retrieving program information. Please try again or rephrase your question."

class GrievanceAgent:
    """Specialist agent for handling grievances and complaints.
    
    This agent processes user complaints about programs, creates support tickets,
    and provides guidance on the resolution process.
    """
    
    def __init__(self, db_tool: SQLDatabaseTool, ollama: OllamaClient):
        """Initialize the Grievance Agent.
        
        Args:
            db_tool: SQLDatabaseTool instance
            ollama: OllamaClient instance
        """
        self.db_tool = db_tool
        self.ollama = ollama
        
        # Define the system prompt for this agent
        self.system_prompt = """You are a Grievance Handling Agent specializing in processing complaints about social benefit programs. Your role is to collect relevant information, create support tickets, and guide users through the resolution process.

INSTRUCTIONS:
1. INFORMATION COLLECTION:
   - Identify which program the complaint relates to
   - Determine the nature of the issue (payment, eligibility, application, etc.)
   - Extract relevant details (dates, amounts, specific problems)
   - If information is missing, ask specific questions to gather it

2. TICKET CREATION:
   - Create a formal grievance ticket with a unique identifier
   - Record all relevant details about the complaint
   - Provide the ticket number to the user for reference

3. RESPONSE REQUIREMENTS:
   - Acknowledge the user's frustration or difficulty empathetically
   - Confirm the details you've understood from their complaint
   - Explain the next steps in the grievance process
   - Set clear expectations about timeframes for resolution (3-5 business days)
   - Provide contact options for urgent follow-up if needed

4. TONE AND APPROACH:
   - Be empathetic but professional
   - Avoid making promises about specific outcomes
   - Focus on the process and next steps rather than resolving the issue immediately
   - Maintain a solution-oriented approach throughout

Remember: Your goal is to ensure users feel heard and understood while providing a clear path forward for resolving their grievance."""
    
    def _analyze_complaint(self, complaint: str) -> Dict:
        """Analyze a complaint to extract key information.
        
        Args:
            complaint: User's complaint text
            
        Returns:
            Dictionary with extracted information
        """
        # Use LLM to extract program and issue information
        analysis_prompt = f"""
        Analyze this complaint and extract the following information:
        
        Complaint: {complaint}
        
        Extract these key details:
        1. Which program or benefit is the complaint about? (If unclear, say "Unspecified")
        2. What type of issue is it? (Payment, Eligibility, Application, Other)
        3. Are there specific dates mentioned? (Format: YYYY-MM-DD)
        4. Is there enough information to process this complaint? (Yes/No)
        5. If information is missing, what specifically should we ask about?
        
        Format your response as a JSON object with these fields:
        program, issue_type, dates, has_enough_info, missing_info
        """
        
        try:
            analysis_response = self.ollama.generate("You are a data extraction assistant. Extract information in the requested format.", analysis_prompt, "analysis")
            
            # Try to parse the JSON response
            # Extract JSON from the response (in case there's additional text)
            json_start = analysis_response.find('{')
            json_end = analysis_response.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_str = analysis_response[json_start:json_end]
                analysis = json.loads(json_str)
            else:
                # Fallback if JSON parsing fails
                analysis = {
                    "program": "Unspecified",
                    "issue_type": "Other",
                    "dates": [],
                    "has_enough_info": "No",
                    "missing_info": "Please provide more details about your complaint."
                }
            
            return analysis
            
        except Exception as e:
            print(f"Error analyzing complaint: {e}")
            return {
                "program": "Unspecified",
                "issue_type": "Other",
                "dates": [],
                "has_enough_info": "No",
                "missing_info": "Error analyzing complaint. Please provide more details."
            }
    
    def process(self, query: str, thread_id: str) -> str:
        """Process a grievance query.
        
        Args:
            query: User query
            thread_id: Thread identifier
            
        Returns:
            Generated response
        """
        try:
            # Analyze the complaint
            analysis = self._analyze_complaint(query)
            
            # If we don't have enough information, ask for more
            if analysis.get("has_enough_info") == "No":
                missing_info = analysis.get("missing_info", "more details about your issue")
                
                followup_prompt = f"""
                The user submitted this grievance: "{query}"
                
                We need more information: "{missing_info}"
                
                Please respond empathetically, acknowledging their frustration, and politely
                ask for the specific missing information. Explain that this will help us
                address their grievance more effectively.
                """
                
                return self.ollama.generate(self.system_prompt, followup_prompt, f"{thread_id}_grievance")
            
            # We have enough information to create a ticket
            # Try to find program ID if a program was mentioned
            program = analysis.get("program", "Unspecified")
            program_id = 0  # Default for unspecified
            
            if program != "Unspecified":
                # Simple search for program ID
                try:
                    results = self.db_tool.execute_query(
                        "SELECT id FROM programs WHERE name LIKE ?",
                        (f"%{program}%",)
                    )
                    if results and "id" in results[0]:
                        program_id = results[0]["id"]
                except Exception as e:
                    print(f"Error finding program ID: {e}")
            
            # Create a ticket
            ticket_info = self.db_tool.create_grievance_ticket(
                user_id=f"user_{thread_id}",
                program_id=program_id,
                description=query
            )
            
            # Generate response with ticket information
            response_prompt = f"""
            User Grievance: "{query}"
            
            Analysis:
            - Program: {program}
            - Issue Type: {analysis.get("issue_type", "Other")}
            
            Grievance Ticket Created:
            - Ticket Number: {ticket_info.get("ticket_number")}
            - Status: {ticket_info.get("status")}
            - Created At: {ticket_info.get("created_at")}
            
            Please generate a response that:
            1. Acknowledges the user's grievance empathetically
            2. Confirms that a ticket has been created
            3. Provides the ticket number for reference
            4. Explains the next steps (review within 24-48 hours, possible follow-up)
            5. Sets expectations for resolution timeframe (typically 3-5 business days)
            6. Offers to help with any other concerns
            """
            
            return self.ollama.generate(self.system_prompt, response_prompt, f"{thread_id}_grievance")
            
        except Exception as e:
            print(f"Error in GrievanceAgent: {e}")
            
            # Create a fallback ticket in case of error
            ticket_number = f"GRV-{datetime.datetime.now().strftime('%Y%m%d')}-{random.randint(1000, 9999)}"
            
            fallback_prompt = f"""
            The user submitted a grievance, but we encountered a system error.
            
            We've created an emergency ticket number: {ticket_number}
            
            Please generate a response that:
            1. Acknowledges their issue empathetically
            2. Explains that we've created a ticket despite technical difficulties
            3. Provides the ticket number
            4. Apologizes for the inconvenience
            5. Ensures them their case will be reviewed promptly
            """
            
            return self.ollama.generate(self.system_prompt, fallback_prompt, f"{thread_id}_grievance")

class MainAgent:
    """Main orchestrator agent that routes queries to specialized agents.
    
    This agent classifies user queries and directs them to the appropriate
    specialized agent (Program or Grievance) based on intent.
    """
    
    def __init__(self, program_agent: ProgramAgent, grievance_agent: GrievanceAgent, ollama: OllamaClient):
        """Initialize the Main Agent.
        
        Args:
            program_agent: ProgramAgent instance
            grievance_agent: GrievanceAgent instance
            ollama: OllamaClient instance
        """
        self.program_agent = program_agent
        self.grievance_agent = grievance_agent
        self.ollama = ollama
        
        # Define the classifier system prompt
        self.classifier_prompt = """You are a query classification system. Your task is to accurately categorize user messages into one of three categories:

1. PROGRAM_INFO: Questions about benefit programs, eligibility criteria, application processes, or available support.
   Examples: "What housing programs are available?", "Am I eligible for farmer subsidies?", "How do I apply for child support?"

2. GRIEVANCE: Complaints, reports of issues, or requests to resolve problems with benefits.
   Examples: "I haven't received my payment", "My application was rejected unfairly", "I need to file a complaint"

3. GENERAL: Greetings, casual conversation, or topics unrelated to benefit programs.
   Examples: "Hello", "How are you?", "What's the weather like?"

INSTRUCTIONS:
- Analyze the content, intent, and emotional tone of the message
- Look for keywords indicating program queries or complaints
- Consider context from any previous messages provided
- Choose the MOST appropriate category

RESPONSE FORMAT:
Respond with EXACTLY one category name: PROGRAM_INFO, GRIEVANCE, or GENERAL.
Do not include any other text in your response."""
        
        # Define the general query system prompt
        self.general_prompt = """You are a helpful assistant specializing in social benefit programs. For general queries, greetings, or topics outside your specialized knowledge:

1. Respond in a friendly, conversational manner
2. Keep responses concise (1-3 sentences for simple greetings)
3. For unclear queries, gently steer the conversation toward benefit programs
4. Mention that you can help with:
   - Finding appropriate benefit programs based on their situation
   - Checking eligibility for specific programs
   - Explaining application processes
   - Handling complaints about benefit programs

Avoid detailed explanations of your capabilities unless specifically asked."""
    
    def process(self, query: str, thread_id: str = "default") -> str:
        """Process a user query by routing to the appropriate agent."""
        try:
            # Get recent conversation context for better classification
            thread_messages = self.ollama._get_thread(thread_id)
            recent_context = thread_messages[-6:] if len(thread_messages) > 0 else []
            # Prepare context for classification
            context_str = ""
            if recent_context:
                context_str = "Previous messages:\n" + "\n".join([
                    f"{msg['role']}: {msg['content'][:100]}..." 
                    if len(msg['content']) > 100 else f"{msg['role']}: {msg['content']}"
                    for msg in recent_context
                ]) + "\n\n"
            classification_prompt = f"{context_str}Current message: {query}\n\nWhich category does this fall into?"
            # Classify the query with strict output parsing
            classification_result = self.ollama.generate(
                self.classifier_prompt, 
                classification_prompt, 
                f"{thread_id}_classifier"
            ).strip()
            print(f"Raw classification: {classification_result}")
            # Improved classification parsing
            query_type = "GENERAL"  # Default fallback
            clean_result = classification_result.split()[-1].strip(".").upper()
            if clean_result in ["PROGRAM_INFO", "GRIEVANCE", "GENERAL"]:
                query_type = clean_result
            else:
                # Fallback pattern matching
                if any(word in query.lower() for word in ["program", "scheme", "eligibility", "benefit"]):
                    query_type = "PROGRAM_INFO"
                elif any(word in query.lower() for word in ["complain", "grievance", "issue", "problem"]):
                    query_type = "GRIEVANCE"
            print(f"Final classification: {query_type}")
            # Route queries appropriately
            if query_type == "PROGRAM_INFO":
                print("Routing to Program Agent...")
                response = self.program_agent.process(query, thread_id)
            elif query_type == "GRIEVANCE":
                print("Routing to Grievance Agent...")
                response = self.grievance_agent.process(query, thread_id)
            else:
                print("Handling as general query...")
                # Direct response for greetings/smalltalk
                if any(word in query.lower() for word in ["hello", "hi", "hey"]):
                    response = "Hello! How can I assist you with social benefit programs today?"
                else:
                    response = self.ollama.generate(
                        self.general_prompt, 
                        query, 
                        thread_id
                    )
            return response
        except Exception as e:
            print(f"Error in MainAgent: {e}")
            return "I apologize for the confusion. Could you please rephrase your question?"

# ------------------ System Integration ------------------

class AgentSystem:
    """Integrated system that coordinates all agent components.
    
    This class provides a simple interface to initialize and use the
    hierarchical agent system.
    """
    
    def __init__(
        self,
        db_path: str,
        faiss_index_path: str,
        model: str = "deepseek-r1:8b",
        temperature: float = 0.1,
        ollama_url: str = "http://localhost:11434"
    ):
        """Initialize the agent system.
        
        Args:
            db_path: Path to the SQLite database
            faiss_index_path: Path to the FAISS index
            model: Name of the Ollama model
            temperature: Temperature for response generation
            ollama_url: Base URL for the Ollama API
        """
        print(f"Initializing Agent System with model: {model}")
        
        # Initialize shared components
        self.ollama = OllamaClient(base_url=ollama_url, model=model, temperature=temperature)
        self.db_tool = SQLDatabaseTool(db_path)
        
        # Initialize specialized agents
        print("Initializing Program Agent...")
        self.program_agent = ProgramAgent(
            db_tool=self.db_tool,
            ollama=self.ollama,
            faiss_index_path=faiss_index_path
        )
        
        print("Initializing Grievance Agent...")
        self.grievance_agent = GrievanceAgent(
            db_tool=self.db_tool,
            ollama=self.ollama
        )
        
        # Initialize main router agent
        print("Initializing Main Agent...")
        self.main_agent = MainAgent(
            program_agent=self.program_agent,
            grievance_agent=self.grievance_agent,
            ollama=self.ollama
        )
        
        print("Agent System initialization complete")
    
    def process_query(self, query: str, thread_id: str = "default") -> str:
        """Process a user query.
        
        Args:
            query: User query
            thread_id: Thread identifier
            
        Returns:
            Generated response
        """
        print(f"Processing query: {query}")
        response = self.main_agent.process(query, thread_id)
        print(f"Generated response: {response[:100]}..." if len(response) > 100 else f"Generated response: {response}")
        return response
    
    def reset_conversation(self, thread_id: str = "default"):
        """Reset the conversation history for a thread.
        
        Args:
            thread_id: Thread identifier
        """
        self.ollama.clear_thread(thread_id)
        self.ollama.clear_thread(f"{thread_id}_classifier")
        self.ollama.clear_thread(f"{thread_id}_program")
        self.ollama.clear_thread(f"{thread_id}_grievance")
        print(f"Conversation reset for thread: {thread_id}")

# ------------------ Main Function ------------------

def main():
    """Run the agent system with a command-line interface."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Hierarchical Agent System")
    parser.add_argument("--db", type=str, default="program_db.sqlite", help="Path to SQLite database")
    parser.add_argument("--index", type=str, default="program_db_faiss/programs_index", help="Path to FAISS index")
    parser.add_argument("--model", type=str, default="deepseek-r1:8b", help="Ollama model name")
    parser.add_argument("--temp", type=float, default=0.1, help="Temperature for generation")
    parser.add_argument("--url", type=str, default="http://localhost:11434", help="Ollama API URL")
    
    args = parser.parse_args()
    
    print("\n==== Hierarchical Agent System ====\n")
    print("Initializing system components...")
    
    # Initialize the agent system
    agent_system = AgentSystem(
        db_path=args.db,
        faiss_index_path=args.index,
        model=args.model,
        temperature=args.temp,
        ollama_url=args.url
    )
    
    print("\nAgent System Ready!")
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
                print("\nThank you for using the Hierarchical Agent System. Goodbye!")
                break
                
            if user_input.lower() == "reset":
                agent_system.reset_conversation(session_id)
                print("Conversation history has been reset.")
                continue
            
            # Process the query
            print("Processing...")
            response = agent_system.process_query(user_input, session_id)
            
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
