from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_ollama import ChatOllama
from langchain.tools.retriever import create_retriever_tool
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.checkpoint.memory import MemorySaver

def create_faiss_retriever_tool(model, docs_path, tool_name):
    embeddings = HuggingFaceEmbeddings(model_name=model)
    vector_store = FAISS.load_local(docs_path, embeddings, allow_dangerous_deserialization=True)
    retriever = vector_store.as_retriever(search_type="similarity", search_kwargs={"k": 6})
    tool = create_retriever_tool(retriever, tool_name, 'Search for information about government schemes') 
    return tool

def get_ai_response(agent_executor, query, config):
    # First get relevant information directly
    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    vector_store = FAISS.load_local("../faiss/programs_index", embeddings, allow_dangerous_deserialization=True)
    docs = vector_store.similarity_search(query)
    context = "\n\n".join(doc.page_content for doc in docs)

    # Prepare enhanced prompt with context
    prompt = f"""Based on the following information about government schemes:

    {context}

    Please provide a helpful response to this query: {query}

    Focus on eligibility, benefits, and how to apply. If you don't find relevant information, 
    just say so politely."""

    # Get direct response from LLM
    llm = ChatOllama(model="llama3.2", temperature=0)
    response = llm.invoke([
        SystemMessage(content="You are a helpful government schemes advisor. Provide clear, direct answers."),
        HumanMessage(content=prompt)
    ])

    return response

def load_llama(model, nthreads=4):
    llm = ChatOllama(
        model=model,
        temperature=0,
        num_thread=nthreads,
    )
    return llm

def init_agent(embeddings_model, llm_model, faiss_index_path, tool_name, nthreads=4):
    llm = load_llama(llm_model, nthreads=nthreads)
    memory = MemorySaver()
    
    system_prompt = '''You are a helpful government schemes advisor. Provide clear information about 
    scheme eligibility, benefits, and application processes. If you don't know something, say so politely.'''
    
    agent_executor = create_react_agent(llm, [], checkpointer=memory, state_modifier=system_prompt)
    return agent_executor
