# FastAPI based service to respond to user queries

from fastapi import Body, FastAPI
from pydantic import BaseModel
from lib import init_agent, get_ai_response
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver

agent_executor = init_agent('all-MiniLM-L6-v2', 
                             'llama3.2', 
                             '/home/puneet/faiss/programs_index', 
                             'programs_info')
app = FastAPI()

class UserInput(BaseModel):
    query: str
    thread_id: str

@app.get("/")
def respond():
    return 'All well'

@app.post("/chat")
def ai_respond(user_input: UserInput):
    query = user_input.query
    thread_id = user_input.thread_id
    config = {"configurable": {"thread_id": thread_id}}
    r = get_ai_response(agent_executor, query, config)
    return {'ai_message': r.pretty_repr() }

if __name__ == "__main__":
    main()

