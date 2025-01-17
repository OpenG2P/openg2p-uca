# Full end2end question/answer app
# Experimenation 

from lib import *
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_core.messages import SystemMessage

def init_db_agent(db_path, llm_model, nthreads=4):
    db = SQLDatabase.from_uri(f'sqlite:///{db_path}')
    llm =  load_llama(llm_model, nthreads=nthreads)
    toolkit = SQLDatabaseToolkit(db=db, llm=llm)
    tools = toolkit.get_tools()
    memory = MemorySaver()
    system_prompt = '''You are an agent designed to interact with a SQL database and verify identity of users. After the first message from user, ask the user for his/her user ID. The user ID is a 4 digit integer. After receiving user ID from user create a syntactically correct SQLite query for this ID in the 'user' table of database. The ID column in the database is called user_id. The user_id column from database must match exactly the ID provided by user. If the ID is found, ask the user his/her name and date of birth. After the user has given these, close the conversation with a happy message. If the user does not provide name and date of birth properly, just close the conversation saying you can't help much. If the ID is not found tell the user politely that the user ID was not found and close the converstation politely.  You have access to tools for interacting with the database. Only use the below tools. Only use the information returned by the below tools to construct your final answer. You MUST double check your query before executing it. Show the SQL query you executed . If you get an error while executing a query, rewrite the query and try again. DO NOT make any DML statements (INSERT, UPDATE, DELETE, DROP etc.) to the database. To start you should ALWAYS look at the tables in the database to see what you can query. Do NOT skip this step.  Then you should query the schema of the most relevant tables. ALWAYS show the SQL query you have executed.''' 

    system_message = SystemMessage(content=system_prompt)
    agent_executor = create_react_agent(llm, tools, checkpointer=memory, state_modifier=system_message)

    return agent_executor
def main():

    agent_executor = init_db_agent('db/users.db','llama3.2', nthreads=4) 
    config = {"configurable": {"thread_id": "thread-1"}}
    while 1:
        print('==== Say something')
        query = input()
        r = get_ai_response(agent_executor, query, config)
        print(r.pretty_repr())

if __name__ == "__main__":
    main()

