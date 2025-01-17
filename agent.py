# Full end2end question/answer app
# Experimenation 

from lib import *
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver

def main():
    tool = create_faiss_retriever_tool('all-MiniLM-L6-v2',
                                '../faiss/programs_index', 
                                'programs_info',
                                'Searches relevant programs')
    tools = [tool]
    llm =  load_llama('llama3.2', nthreads=4)
    memory = MemorySaver()
    system_prompt = '''You are an advisor. Have a conversation with the user. If the user has questions on eligility for programs, or availability of certain programs, answer those from the context. If you don't know the answer, just say that you don't know, don't try to make up an answer. Keep the answer as concise as possible. You can end the conversation once the user does not have any more enquiry. Make sure you remember the name of the user.'''
    agent_executor = create_react_agent(llm, tools, checkpointer=memory, state_modifier=system_prompt)

    config = {"configurable": {"thread_id": "thread-1"}}
    while 1:
        print('==== Say something')
        query = input()
        r = get_ai_response(agent_executor, query, config)
        print(r.pretty_repr())

if __name__ == "__main__":
    main()

