# lib_alter.py
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage
from program_retriever import ProgramRetriever

def process_query(query):
    print("\n=== Processing New Query ===")
    print(f"Query: {query}")
    
    try:
        retriever = ProgramRetriever(
            faiss_index_path="new_faiss/programs_index",
            db_path="pdb"
        )
        
        print("\n=== Getting Similar Programs ===")
        relevant_programs = retriever.get_similar_programs(query)
        print(f"\nRelevant Programs Found: {len(relevant_programs)}")
        
        print("\n=== Building Context ===")
        context = build_context(relevant_programs)
        print(f"Context Built: {context[:200]}...")
        
        llm = ChatOllama(model="llama3.2", temperature=0)
        response = llm.invoke([
            SystemMessage(content="You are a helpful government schemes advisor."),
            HumanMessage(content=f"""Based on this information:\n{context}\n\nQuery: {query}""")
        ])
        
        return response
        
    except Exception as e:
        print(f"Error occurred: {e}")
        return None

def build_context(programs):
    context_parts = []
    for program in programs:
        context_parts.append(f"""
Program: {program['mneumonic']}
Description: {program['description']}
Eligibility Criteria: {program['eligibility']}
        """.strip())
    
    return "\n\n".join(context_parts)
