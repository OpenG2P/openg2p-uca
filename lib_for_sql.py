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
       
       prompt = f"""You are a government program advisor. I will provide you with program eligibility criteria in SQL query format. 

For each provided program, analyze its SQL query and explain:

Program Details:
{context}

Based on the SQL WHERE conditions:
1. List all eligibility requirements in clear bullet points
2. Group related conditions (connected by AND/OR)
3. Convert database field names to human-readable terms:
  - res_partner.country_id → Country of residence
  - education_level → Education level
  - employment_status → Employment status
  - type_of_disability → Type of disability
  - marital_status → Marital status
  - annual_income → Annual income
  - birthdate → Date of birth
  - occupation → Occupation
  - land_holding → Land ownership
  - pension_amount → Pension amount
  - citizenship → Citizenship

4. Translate SQL operators to plain language:
  - "=" → "must be" or "is"
  - "<" → "less than" or "before"
  - ">" → "more than" or "after"
  - AND → "Additionally," or "Also must"
  - OR → "Either" or "Or"

Present the requirements in clear, simple language without any technical terms or SQL references.

User Query: {query}"""

       llm = ChatOllama(model="llama3.2", temperature=0)
       response = llm.invoke([
           SystemMessage(content="You are a helpful government schemes advisor. Convert SQL eligibility rules into clear, human-friendly explanations."),
           HumanMessage(content=prompt)
       ])
       
       return response
       
   except Exception as e:
       print(f"Error occurred: {e}")
       return None

def build_context(programs):
   context_parts = []
   for program in programs:
       context_parts.append(f"""
Program Name: {program['mneumonic']}
Description: {program['description']}
Eligibility Criteria: {program['eligibility']}
       """.strip())
   
   return "\n\n".join(context_parts)
