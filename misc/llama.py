from langchain_ollama.llms import OllamaLLM
from langchain_core.messages import AIMessage
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage

llm = ChatOllama(
    model="llama3.2",
    temperature=0,
)


ai_msg = llm.invoke([HumanMessage(content="Hi! Sally is 10 years of age, Micky is 15 years and Puneet is 55 years. Who is the youngest of all of them?")])
print(ai_msg.content)


