"""
Vector store / embedding pipeline.

Embeddings run entirely locally via a free, open-source HuggingFace model
(no OpenAI dependency, no per-call embedding cost) -- ChromaDB remains the
vector store, LlamaIndex remains the indexing/retrieval layer. Only answer
generation (chatbot/utils/rag.py) uses an external API, and that's Groq.

The embedding model name is read from Django settings (EMBEDDING_MODEL) in a
single place so the raw Chroma embedding function and the LlamaIndex
embed_model can never drift out of sync with each other (see ISSUES.md #9).
"""

import os

from chromadb import PersistentClient
from chromadb.config import Settings as ChromaSettings
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
from django.conf import settings
from llama_index.core import StorageContext, VectorStoreIndex
from llama_index.core.settings import Settings as LlamaSettings
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.vector_stores.chroma import ChromaVectorStore

CHROMA_PATH = str(settings.BASE_DIR / 'chroma_db')
os.makedirs(CHROMA_PATH, exist_ok=True)

EMBEDDING_MODEL = settings.EMBEDDING_MODEL

# Runs locally on CPU the first time it downloads the model weights from the
# HuggingFace hub (a few hundred MB, one-time, then cached under
# ~/.cache/huggingface); no API key and no per-call cost either way.
embedding_function = SentenceTransformerEmbeddingFunction(model_name=EMBEDDING_MODEL)

LlamaSettings.embed_model = HuggingFaceEmbedding(
    model_name=EMBEDDING_MODEL,
    embed_batch_size=100,
)

chroma_client = PersistentClient(
    path=CHROMA_PATH,
    settings=ChromaSettings(allow_reset=True, anonymized_telemetry=False),
)

chroma_collection = chroma_client.get_or_create_collection(
    name='rag_index',
    embedding_function=embedding_function,
)

vector_store = ChromaVectorStore.from_collection(chroma_collection)
storage_context = StorageContext.from_defaults(vector_store=vector_store)
shared_index = VectorStoreIndex.from_vector_store(vector_store)
