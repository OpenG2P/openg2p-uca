from haystack import Pipeline
from haystack.document_stores import FAISSDocumentStore
from haystack.nodes import PDFToTextConverter, PreProcessor
from haystack.nodes import EmbeddingRetriever

faiss_index_path = "../faiss/test_index"
faiss_config_path = "../faiss/test_config"
faiss_db_path = "../faiss/faiss_document_store.db"

document_store = FAISSDocumentStore.load(
    index_path=faiss_index_path,
    config_path=faiss_config_path)

print(document_store.get_all_documents())
