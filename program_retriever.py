# program_retriever.py
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
import sqlite3

class ProgramRetriever:
    def __init__(self, faiss_index_path, db_path):
        self.embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        self.vector_store = FAISS.load_local(
            faiss_index_path, 
            self.embeddings, 
            allow_dangerous_deserialization=True
        )
        self.db_path = db_path

    
    def get_similar_programs(self, query, k=3):
        # Perform similarity search
        docs = self.vector_store.similarity_search(query, k=k)
        print("\n=== Similar Documents from FAISS ===")
        for doc in docs:
            print(f"Content: {doc.page_content}")
            print(f"Metadata: {doc.metadata}\n")
        
        # Extract program IDs from metadata
        program_ids = [doc.metadata['pid'] for doc in docs]
        print(f"Program IDs to fetch: {program_ids}")
        
        # Fetch complete program details from SQL
        programs = self.fetch_program_details(program_ids)
        print("\n=== Programs from SQL Database ===")
        for prog in programs:
            print(f"Program: {prog}")
        
        return programs


    def fetch_program_details(self, program_ids):
        # Connect to SQLite and fetch full program details
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create placeholders for SQL IN clause
        placeholders = ','.join('?' * len(program_ids))
        
        # Fetch all relevant columns
        cursor.execute(f'''
            SELECT pid, mneumonic, description, domain, eligibility 
            FROM pinfo 
            WHERE pid IN ({placeholders})
        ''', program_ids)
        
        programs = cursor.fetchall()
        conn.close()
        
        # Convert to list of dictionaries for easier handling
        program_details = []
        for prog in programs:
            program_details.append({
                'pid': prog[0],
                'mneumonic': prog[1],
                'description': prog[2],
                'domain': prog[3],
                'eligibility': prog[4]
            })
        
        return program_details
