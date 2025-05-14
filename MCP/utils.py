"""
Utility functions and classes for the Social Benefits Assistant.

Contains:
- OllamaClient: Client for interacting with Ollama LLMs
- SQLDatabaseTool: Utility for working with SQLite databases
"""

import json
import logging
import sqlite3
import requests
from typing import Dict, List, Any, Optional, Tuple

# Set up logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('SocialBenefits-Utils')

class OllamaClient:
    """Client for interacting with Ollama LLMs."""
    
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "deepseek-r1:8b", temperature: float = 0.1):
        """Initialize the Ollama client."""
        self.base_url = base_url
        self.model = model
        self.temperature = temperature
        # self.thread_histories = {}
        logger.info(f"OllamaClient initialized with model: {model}, temperature: {temperature}")
    
    def generate(self, system_prompt: str, prompt: str, thread_id: str = "default") -> str:
        """Generate a response using the Ollama API."""
        try:
            # Initialize thread history if it doesn't exist
            # if thread_id not in self.thread_histories:
            #     self.thread_histories[thread_id] = []
            
            # Prepare the request
            url = f"{self.base_url}/api/chat"
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    # *self.thread_histories[thread_id],
                    {"role": "user", "content": prompt}
                ],
                "temperature": self.temperature,
                "stream": False
            }
            
            # Send the request
            logger.debug(f"Sending request to Ollama API for thread {thread_id}")
            response = requests.post(url, json=payload)
            response.raise_for_status()
            
            # Parse the response
            result = response.json()
            assistant_message = result["message"]["content"]
            
            # Update thread history
            # self.thread_histories[thread_id].append({"role": "user", "content": prompt})
            # self.thread_histories[thread_id].append({"role": "assistant", "content": assistant_message})
            
            # Keep history manageable
            # if len(self.thread_histories[thread_id]) > 10:
            #     self.thread_histories[thread_id] = self.thread_histories[thread_id][-10:]
            
            logger.debug(f"Generated response for thread {thread_id} (length: {len(assistant_message)})")
            return assistant_message
            
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return f"Error: {e}"
    
    # def clear_thread(self, thread_id: str):
    #     """Clear the conversation history for a thread."""
    #     if thread_id in self.thread_histories:
    #         self.thread_histories[thread_id] = []
    #         logger.info(f"Cleared thread history for {thread_id}")

class SQLDatabaseTool:
    """Utility for working with SQLite databases."""
    
    def __init__(self, db_path: str, validate_tables: bool = True):
        """Initialize the database tool."""
        self.db_path = db_path
        
        # Check if database exists and has required tables
        if validate_tables:
            self._validate_database()
            
        logger.info(f"SQLDatabaseTool initialized with database: {db_path}")
    
    def _validate_database(self):
        """Validate that the database exists and has required tables."""
        try:
            # Connect to the database
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check for required tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [table[0] for table in cursor.fetchall()]
            
            required_tables = ["program_info", "program_membership", "registry", "ticket"]
            missing_tables = [table for table in required_tables if table not in tables]
            
            if missing_tables:
                logger.warning(f"Database is missing tables: {missing_tables}")
                
                # Create missing tables
                if "program_info" in missing_tables:
                    cursor.execute('''
                    CREATE TABLE program_info (
                        id INTEGER PRIMARY KEY,
                        name TEXT,
                        description TEXT,
                        criteria TEXT,
                        benefits TEXT,
                        application TEXT
                    )
                    ''')
                
                if "program_membership" in missing_tables:
                    cursor.execute('''
                    CREATE TABLE program_membership (
                        id INTEGER PRIMARY KEY,
                        user_id TEXT,
                        user_name TEXT,
                        program_id INTEGER,
                        status TEXT,
                        enrollment_date TEXT
                    )
                    ''')
                
                if "registry" in missing_tables:
                    cursor.execute('''
                    CREATE TABLE registry (
                        id INTEGER PRIMARY KEY,
                        program_id INTEGER,
                        program_name TEXT,
                        description TEXT
                    )
                    ''')
                
                if "ticket" in missing_tables:
                    cursor.execute('''
                    CREATE TABLE ticket (
                        id INTEGER PRIMARY KEY,
                        ticket_id TEXT,
                        user_id TEXT,
                        program_id INTEGER,
                        description TEXT,
                        status TEXT,
                        priority TEXT,
                        created_at TEXT,
                        updated_at TEXT,
                        resolution_notes TEXT
                    )
                    ''')
                
                conn.commit()
                logger.info("Created missing tables")
            
            conn.close()
            
        except Exception as e:
            logger.error(f"Error validating database: {e}")
    
    def execute_query(self, query: str, params: Tuple = ()) -> List[Dict]:
        """Execute a query and return the results as a list of dictionaries."""
        try:
            # Connect to the database
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Execute the query
            cursor.execute(query, params)
            
            # Check if this is a SELECT query
            if query.strip().upper().startswith("SELECT"):
                # Fetch and convert rows to dictionaries
                rows = cursor.fetchall()
                result = [{key: row[key] for key in row.keys()} for row in rows]
            else:
                # For non-SELECT queries, commit and return affected row count
                conn.commit()
                result = [{"rowcount": cursor.rowcount}]
            
            conn.close()
            return result
            
        except Exception as e:
            logger.error(f"Error executing query: {e}")
            return []