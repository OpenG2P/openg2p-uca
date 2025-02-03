from lib import *
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
from langchain_community.utilities import SQLDatabase
from langchain_core.messages import SystemMessage
import sqlite3

def get_program_info(query):
    """Search for program information in the database"""
    conn = sqlite3.connect('programs.db')
    cursor = conn.cursor()
    
    # Create a search query that looks through all text fields
    search_query = '''
    SELECT 
        program_name,
        description,
        eligibility_criteria,
        exclusions,
        application_procedure
    FROM program_info
    WHERE 
        program_name LIKE ? OR
        description LIKE ? OR
        eligibility_criteria LIKE ? OR
        exclusions LIKE ? OR
        application_procedure LIKE ?
    '''
    
    # Use wildcards for flexible matching
    search_term = f"%{query}%"
    cursor.execute(search_query, (search_term,) * 5)
    
    results = cursor.fetchall()
    conn.close()
    
    if not results:
        return "No matching programs found."
    
    # Format the results in a readable way
    formatted_results = []
    for result in results:
        program_info = f"""
Program: {result[0]}

Description:
{result[1]}

Eligibility:
{result[2]}

Exclusions:
{result[3]}

How to Apply:
{result[4]}
        """
        formatted_results.append(program_info)
    
    return "\n\n".join(formatted_results)

def init_db_agent(llm_model="llama3.2", nthreads=4):
    llm = load_llama(llm_model, nthreads=nthreads)
    memory = MemorySaver()
    
    system_prompt = '''You are a helpful government schemes advisor. Your role is to:
    1. Understand user queries about government programs
    2. Search the database for relevant program information
    3. Explain eligibility criteria and benefits clearly
    4. Guide users through application procedures
    5. Maintain conversation context and remember user details
    
    Always provide clear, natural language responses focusing on:
    - Program eligibility
    - Benefits offered
    - Application process
    - Any relevant exclusions
    
    If you're not sure about something, say so rather than making assumptions.'''
    
    agent_executor = create_react_agent(llm, [], checkpointer=memory, state_modifier=system_prompt)
    return agent_executor

def get_ai_response(agent_executor, query, config):
    # First, search the database for relevant information
    program_info = get_program_info(query)
    
    # Create an enhanced prompt combining the query and program information
    enhanced_prompt = f"""Based on this information about government schemes:

{program_info}

Please provide a helpful response to the user's query: {query}
Focus on explaining eligibility, benefits, and how to apply in a clear, natural way."""
    
    # Get response from LLM
    llm = ChatOllama(model="llama3.2", temperature=0)
    response = llm.invoke([HumanMessage(content=enhanced_prompt)])
    
    return response

def main():
    print("\n=== Government Programs Advisor ===")
    agent_executor = init_db_agent(llm_model='llama3.2', nthreads=4)
    config = {"configurable": {"thread_id": "thread-1"}}
    
    while True:
        print('\n==== Ask about government programs (or type "exit" to quit) ====')
        query = input("Your query: ")
        
        if query.lower() == 'exit':
            break
        
        try:
            response = get_ai_response(agent_executor, query, config)
            print("\nAdvisor:", response.content)
        except Exception as e:
            print(f"Error: {str(e)}")

if __name__ == "__main__":
    main()
