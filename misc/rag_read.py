from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.docstore.in_memory import InMemoryDocstore
from langchain_community.vectorstores import FAISS

embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

query = "As a student do I get any benefit?"
vector_store = FAISS.load_local(
    "../faiss/programs_index", embeddings, allow_dangerous_deserialization=True
)

query="Are there any schemes related to student?"
docs = vector_store.similarity_search(query)
print(docs[0])

