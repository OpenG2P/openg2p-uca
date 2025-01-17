# Full end2end question/answer app

import time
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_ollama import ChatOllama
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

def format_docs(docs):
    return "\n\n".join(doc.page_content for doc in docs)

embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

llm = ChatOllama(
    model="llama3.2",
    temperature=0,
    num_thread=4,  # Change as per your CPU configuration
)

vector_store = FAISS.load_local(
    "../faiss/programs_index", embeddings, allow_dangerous_deserialization=True
)
retriever = vector_store.as_retriever(search_type="similarity", search_kwargs={"k": 6})

template = """Use the following pieces of context to answer the question at the end. If you don't know the answer, just say that you don't know, don't try to make up an answer. Use three sentences maximum and keep the answer as concise as possible. Answer as best as possible on eligibility of programs, and how to apply.  

{context}

Question: {question}

Helpful Answer:"""
custom_rag_prompt = PromptTemplate.from_template(template)

rag_chain = (
    {"context": retriever | format_docs, "question": RunnablePassthrough()}
    | custom_rag_prompt
    | llm
    | StrOutputParser()
)

start = time.time()
a = rag_chain.invoke("As a mother am I eligible for some progams?")
end = time.time()
print(a)
print('time taken = %d secs' % (end - start))
