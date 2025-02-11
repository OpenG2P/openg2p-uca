# create_embeddings.py
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
import sqlite3
import json

def fetch_programs_from_db():
    conn = sqlite3.connect('pdb')
    cursor = conn.cursor()
    cursor.execute('SELECT pid, mneumonic, description FROM pinfo')
    programs = cursor.fetchall()
    conn.close()
    return programs

def create_program_documents(programs):
    # Convert to langchain Document objects
    documents = []
    for pid, mneumonic, description in programs:
        # Combine mneumonic and description for meaningful embedding
        content = f"{mneumonic}: {description}" if description else mneumonic
        
        # Create langchain Document with metadata
        doc = Document(
            page_content=content,  # This is the text to be embedded
            metadata={
                "pid": pid,
                "mneumonic": mneumonic
            }
        )
        documents.append(doc)
    return documents

def create_and_save_embeddings():
    # Initialize embeddings model
    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    
    # Get programs and create documents
    programs = fetch_programs_from_db()
    documents = create_program_documents(programs)
    
    # Create and save FAISS index
    vector_store = FAISS.from_documents(documents, embeddings)
    vector_store.save_local("new_faiss/programs_index")

if __name__ == "__main__":
    create_and_save_embeddings()
