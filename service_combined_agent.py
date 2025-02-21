
from fastapi import FastAPI
from pydantic import BaseModel
from combined_agent import CombinedProgramAgent


agent = CombinedProgramAgent(
    db_path='program_db',
    faiss_index_path='/home/veerendra/openg2p-uca/program_db_faiss/programs_index',  
    llm_model='llama3.2',
    embeddings_model='all-MiniLM-L6-v2' 
)

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
    
    
    response = agent.get_response(query, thread_id)
    
    return {'ai_message': response}


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(app, host="0.0.0.0", port=8000)
