from typing import List, Dict
from langchain_core.tools import Tool
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.tools.retriever import create_retriever_tool
from langchain_ollama import ChatOllama
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import SystemMessage, HumanMessage

class CombinedProgramAgent:
    def __init__(
        self,
        db_path: str,
        faiss_index_path: str,
        llm_model: str = "llama3.2",
        embeddings_model: str = "all-MiniLM-L6-v2",
        num_threads: int = 4
    ):
        self.llm = self._init_llm(llm_model, num_threads)
        self.tools = self._init_tools(db_path, faiss_index_path, embeddings_model)
        self.agent_executor = self._init_agent()

    def _init_llm(self, model: str, num_threads: int):
        """Initialize the LLM with specified parameters"""
        return ChatOllama(
            model=model,
            temperature=0,
            num_thread=num_threads
        )

    def _init_tools(self, db_path: str, faiss_index_path: str, embeddings_model: str) -> List[Tool]:
        """Initialize both FAISS and SQL tools"""
        # Initialize SQL Database toolkit
        db = SQLDatabase.from_uri(f'sqlite:///{db_path}')
        sql_toolkit = SQLDatabaseToolkit(db=db, llm=self.llm)
        sql_tools = sql_toolkit.get_tools()

        # Initialize FAISS retriever tool
        embeddings = HuggingFaceEmbeddings(model_name=embeddings_model)
        vector_store = FAISS.load_local(faiss_index_path, embeddings, allow_dangerous_deserialization=True)
        retriever = vector_store.as_retriever(search_type="similarity", search_kwargs={"k": 3})
        faiss_tool = create_retriever_tool(
            retriever,
            "program_info",
            "Search for program information and descriptions"
        )

        return sql_tools + [faiss_tool]

    def _init_agent(self):
        """Initialize the React agent with a comprehensive system prompt"""

        system_prompt = """You are a program eligibility advisor that helps users find suitable social benefit programs. Follow these steps for each query:

1. Identify the intent of the user,if it is greeting then respond naturally to greetings and casual conversation. If its related to Programs/eligibility/schemes then follow the next instructions.
2. First, use the program_info tool to find relevant programs based on the user's situation
3. For each potentially relevant program found, use the SQL tools to check detailed eligibility criteria
4. Combine the information from both sources to provide a complete response that includes:
   - Program name and brief description
   - Key eligibility criteria
   - Whether the user likely qualifies based on their stated situation
   
Keep responses concise but informative. If more information is needed from the user to determine eligibility, ask for specific details.

Remember: 
- Verify eligibility criteria in the database before making definitive statements
- Consider all relevant programs that might apply to the user's situation
- Be clear about what information you're basing your response on"""

        memory = MemorySaver()
        return create_react_agent(
            self.llm,
            self.tools,
            checkpointer=memory,
            state_modifier=SystemMessage(content=system_prompt)
        )

    def get_response(self, query: str, thread_id: str) -> str:
        """Process a user query and return a response"""
        config = {"configurable": {"thread_id": thread_id}}
        response = None
        
        for event in self.agent_executor.stream(
            {"messages": [HumanMessage(content=query)]},
            config,
            stream_mode='values'
        ):
            response = event['messages'][-1]
            
        return response.pretty_repr()

# Example usage
def main():
    agent = CombinedProgramAgent(
        db_path='pdb',
        faiss_index_path='new_faiss/programs_index',
        llm_model='llama3.2',
        num_threads=4
    )
    
    while True:
        print('\nEnter your query (or "quit" to exit):')
        query = input()
        if query.lower() == 'quit':
            break
            
        response = agent.get_response(query, thread_id='test-thread_1')
        print('\nResponse:', response)

if __name__ == "__main__":
    main()
