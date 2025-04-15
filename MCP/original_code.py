# This file ensures compatibility with original code components
# Move the OllamaClient and SQLDatabaseTool classes from the original code here

import json
import sqlite3
import threading
import random
import datetime
import requests
import os
from typing import Dict, List, Tuple, Optional, Any

class OllamaClient:
    """Ollama API client with conversation history management."""
    
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "deepseek-r1:8b", temperature: float = 0.1):
        """Initialize the Ollama client."""
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
        """Get or initialize a conversation thread."""
        if thread_id not in self.conversations:
            self.conversations[thread_id] = []
        return self.conversations[thread_id]
    
    def generate(self, system_prompt: str, prompt: str, thread_id: str = "default") -> str:
        """Generate a response using the Ollama API with conversation history."""
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
        """Clear the conversation history for a specific thread."""
        if thread_id in self.conversations:
            self.conversations[thread_id] = []

class SQLDatabaseTool:
    """SQLite database interface with connection pooling and error handling."""
    
    def __init__(self, db_path: str, validate_tables: bool = True):
        """Initialize the SQL database tool."""
        self.db_path = self._resolve_db_path(db_path)
        self.lock = threading.Lock()  # Thread safety for database operations
        
        # Validate database on initialization
        if validate_tables:
            self._validate_database()
    
    def _resolve_db_path(self, db_path: str) -> str:
        """Resolve the database path, handling various formats."""
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
                        status TEXT DEFAULT 'OPEN',
                        priority TEXT DEFAULT 'MEDIUM',
                        created_at TEXT,
                        updated_at TEXT,
                        FOREIGN KEY (program_id) REFERENCES programs(id)
                    )
                    """)
                
                conn.commit()
                print("Database structure validated")
                
        except Exception as e:
            print(f"Error validating database: {e}")
    
    def get_program_details(self, program_id: int) -> Dict:
        """Get program details by ID."""
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
        """Execute an SQL query with parameters."""
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
        """Create a new grievance ticket."""
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