# Full end2end question/answer app
# Experimenation 

from lib import *
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver

def main():
    
    tool = create_faiss_retriever_tool('all-MiniLM-L6-v2',
                                'faiss/programs_index', 
                                'programs_info')
    
    
    tools = [tool]
    llm = load_llama('llama3.2', nthreads=4)
    memory = MemorySaver()
    
    system_prompt = '''You are an advisor...'''
    agent_executor = create_react_agent(llm, tools, checkpointer=memory, state_modifier=system_prompt)
    
    config = {"configurable": {"thread_id": "thread-1"}}
    
    while 1:
        print('\n==== Say something')
        query = input()
        print("\nProcessing query:", query)
        
        vector_store = FAISS.load_local("faiss/programs_index", 
                                      HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2"), 
                                      allow_dangerous_deserialization=True)
        docs = vector_store.similarity_search(query)
        
        r = get_ai_response(agent_executor, query, config)

        print(r.pretty_repr())

if __name__ == "__main__":
    main()

