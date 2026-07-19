"""
Retrieval-augmented generation: retrieve context from the shared ChromaDB /
LlamaIndex vector store, then generate an answer with Groq.

This module replaces three files from the original project:
  - chatbot/utils/chatgpt_response.py (raw `requests` call to OpenAI)
  - chatbot/utils/engine.py (a second, independent retrieval helper)
  - chatbot/background_task.py::generate_answer_sync

Consolidating them fixes two defects documented in ISSUES.md:
  #1 generate_answer_sync()/background_rag() called the old
     get_chatgpt_response() with 2 positional arguments while it only
     accepted 1 -- a crash in the background answer path.
  #2 a query used to run retrieval twice (once to check "is there any
     context", once again inside the generation step). retrieve_context()
     is now called exactly once per query and its result is reused for both
     the existence check and the prompt.

This module only replaces the generation step: retrieval still comes from
the same ChromaDB/LlamaIndex index as before (now backed by free local
HuggingFace embeddings, see embedding_setup.py); the final "context +
question -> answer" call goes to Groq via LlamaIndex's Groq integration
instead of a raw request to OpenAI's Chat Completions API.
"""

import logging

from django.conf import settings
from llama_index.core.base.llms.types import ChatMessage, MessageRole
from llama_index.llms.groq import Groq

from .embedding_setup import shared_index

logger = logging.getLogger(__name__)

NO_CONTEXT_RESPONSE = (
    "Information related to this question is currently unavailable from the "
    "University of Jhang's official sources. You may try rephrasing your query."
)
MISSING_CREDENTIALS_RESPONSE = "AI service is unavailable due to missing API credentials."
GENERATION_ERROR_RESPONSE = "Our AI system is currently experiencing issues. Please try again later."

SYSTEM_PROMPT = (
    "You are a strict university assistant for the University of Jhang (https://www.uoj.edu.pk/).\n"
    "You must ONLY use the provided context below to answer user questions.\n"
    "Do NOT use your own knowledge. If the context does not contain the answer, respond exactly:\n"
    "Information not found exactly. You may try rephrasing your query.\n"
    "\n"
    "Guidelines:\n"
    "- Do NOT guess or make up information.\n"
    "- Do NOT use external knowledge.\n"
    "- Do NOT answer if the context does not clearly support it.\n"
    "- If the question is unrelated, respond:\n"
    "  This question is outside my scope for the University of Jhang. Please refer to other sources for more information."
)

_groq_llm = None


def _get_llm():
    global _groq_llm
    if _groq_llm is None:
        if not settings.GROQ_API_KEY:
            return None
        _groq_llm = Groq(model=settings.GROQ_MODEL, api_key=settings.GROQ_API_KEY)
    return _groq_llm


def retrieve_context(query: str, top_k: int = 5):
    """Runs retrieval exactly once and returns (context_text, source_nodes)."""
    retriever = shared_index.as_retriever(similarity_top_k=top_k)
    nodes = retriever.retrieve(query)
    if not nodes:
        return '', []
    context_text = '\n\n'.join(node.node.get_content() for node in nodes)
    return context_text, nodes


def generate_rag_response(query: str) -> str:
    """Single entry point used by all call sites (sync or background) that
    need a RAG answer: retrieve once, then generate with Groq.
    """
    try:
        context, nodes = retrieve_context(query)
    except Exception:
        logger.exception('Failed to retrieve vector context for query: %s', query)
        return 'Unable to find relevant information from UOJ records.'

    if not nodes:
        return NO_CONTEXT_RESPONSE

    llm = _get_llm()
    if llm is None:
        logger.error('Missing GROQ_API_KEY - cannot generate a response.')
        return MISSING_CREDENTIALS_RESPONSE

    messages = [
        ChatMessage(role=MessageRole.SYSTEM, content=SYSTEM_PROMPT),
        ChatMessage(
            role=MessageRole.USER,
            content=f'Context:\n{context}\n\nQuestion:\n{query}',
        ),
    ]

    try:
        response = llm.chat(messages, temperature=0, max_tokens=300)
        answer = response.message.content.strip()
        logger.info('Groq response generated for query: %s', query)
        return answer
    except Exception:
        logger.exception('Groq generation failed for query: %s', query)
        return GENERATION_ERROR_RESPONSE
