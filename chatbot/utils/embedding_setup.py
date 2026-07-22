"""
Vector store / embedding pipeline.

Embeddings run entirely locally via a free, open-source HuggingFace model
(no OpenAI dependency, no per-call embedding cost) -- ChromaDB remains the
vector store, LlamaIndex remains the indexing/retrieval layer. Only answer
generation (chatbot/utils/rag.py) uses an external API, and that's Groq.

The embedding model name is read from Django settings (EMBEDDING_MODEL) in a
single place so the raw Chroma embedding function and the LlamaIndex
embed_model can never drift out of sync with each other (see ISSUES.md #9).

Only ONE SentenceTransformer is ever constructed (the LlamaIndex
HuggingFaceEmbedding below). chromadb's own SentenceTransformerEmbeddingFunction
would otherwise load a second, independent copy of the same model -- that's
why `embedding_function` wraps embed_model instead of instantiating chromadb's
helper. This module runs once per process (Python caches imports), so as long
as nothing constructs its own model, "Loading SentenceTransformer model" logs
exactly once per process.
"""

import os

from chromadb import PersistentClient
from chromadb.config import Settings as ChromaSettings
from django.conf import settings
from llama_index.core import StorageContext, VectorStoreIndex
from llama_index.core.settings import Settings as LlamaSettings
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.vector_stores.chroma import ChromaVectorStore

CHROMA_PATH = str(settings.BASE_DIR / 'chroma_db')
os.makedirs(CHROMA_PATH, exist_ok=True)

EMBEDDING_MODEL = settings.EMBEDDING_MODEL


class _SharedModelEmbeddingFunction:
    """Adapts `embed_model` to chromadb's EmbeddingFunction protocol
    (a callable taking a list of strings, returning a list of vectors) so
    Chroma reuses the single loaded model instead of loading its own.
    """

    def __init__(self, embed_model):
        self._embed_model = embed_model

    def __call__(self, input):
        return self._embed_model.get_text_embedding_batch(list(input))


# Runs locally on CPU the first time it downloads the model weights from the
# HuggingFace hub (a few hundred MB, one-time, then cached under
# ~/.cache/huggingface); no API key and no per-call cost either way.
embed_model = HuggingFaceEmbedding(
    model_name=EMBEDDING_MODEL,
    embed_batch_size=100,
)
LlamaSettings.embed_model = embed_model

embedding_function = _SharedModelEmbeddingFunction(embed_model)

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
