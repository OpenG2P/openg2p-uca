# Full end2end question/answer app
# Experimenation 

import time
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_ollama import ChatOllama
from langchain.tools.retriever import create_retriever_tool
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent

def create_faiss_retriever_tool(model, docs_path, tool_name):
    embeddings = HuggingFaceEmbeddings(model_name=model)
    vector_store = FAISS.load_local(docs_path, embeddings, allow_dangerous_deserialization=True)
    retriever = vector_store.as_retriever(search_type="similarity", search_kwargs={"k": 6})
    tool = create_retriever_tool(retriever, tool_name, '') 
    return tool


def format_docs(docs):
    return "\n\n".join(doc.page_content for doc in docs)

'''
Print final response from AI 
'''
def get_ai_response(agent_executor, query, config):
    for event in agent_executor.stream({"messages": [HumanMessage(content=query)]}, config, stream_mode='values'):
        pass
    return event['messages'][-1]


def load_llama(model, nthreads=4):
    llm = ChatOllama(
        model=model,
        temperature=0,
        num_thread=nthreads,  # Change as per your CPU configuration
    )
    return llm

def init_agent(embeddings_model, llm_model, faiss_index_path, tool_name, nthreads=4):
    tool = create_faiss_retriever_tool(embeddings_model, faiss_index_path, tool_name)
    tools = [tool]
    llm =  load_llama(llm_model, nthreads=nthreads)
    memory = MemorySaver()
    system_prompt = '''You are an advisor. Have a conversation with the user. If the user has questions on eligility for programs, or availability of certain programs, answer those from the context. If you don't know the answer, just say that you don't know, don't try to make up an answer. Keep the answer as concise as possible. You can end the conversation once the user does not have any more enquiry. Make sure you remember the name of the user across queries'''
    agent_executor = create_react_agent(llm, tools, checkpointer=memory, state_modifier=system_prompt)

    return agent_executor
