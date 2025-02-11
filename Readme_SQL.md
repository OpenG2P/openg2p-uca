## Files Structure
├── create_embeddings.py   # Creates FAISS embeddings from SQL data
├── program_retriever.py   # Handles retrieval from FAISS and SQL
├── lib_new.py            # Core processing logic and LLM interaction
├── new_agent.py               # Main application interface

## Process Flow

1. **Initial Setup** (`create_embeddings.py`)
- Reads program data from SQLite database
- Creates document embeddings combining program names and descriptions
- Stores embeddings in FAISS with program metadata (pid, mneumonic)

2. **Query Processing** (`program_retriever.py`)
- Performs similarity search in FAISS for relevant programs
- Uses metadata to fetch full program details from SQL
- Returns comprehensive program information

3. **LLM Processing** (`lib_for_sql.py`)
- Takes user query and retrieved program information
- Builds context for LLM incorporating program details
- Processes response through LLM for user-friendly output

4. **User Interface** (`new_agent.py`)
- Handles user input/output
- Manages conversation flow
- Displays formatted responses


## Usage

1. First-time setup:
```bash
python create_embeddings.py

2. Run application:
```bash
python python new_agent.py



