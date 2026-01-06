"""
RAG Tool for communicating with vector database to search for fixes based on error logs.
Uses CAMEL-AI's retriever functionality for vector database integration.

Uses OpenAI's text-embedding-3-small model (1536 dimensions) for generating embeddings.
"""
from typing import List, Dict, Any, Optional, Tuple
import os
from camel.retrievers import VectorRetriever
from camel.embeddings import OpenAIEmbedding
from camel.storages import QdrantStorage
from camel.types import EmbeddingModelType, VectorDistance
from camel.storages.vectordb_storages.base import VectorRecord
import uuid


# Initialize vector storage and retriever
# Using Qdrant as the vector database (can be configured via env vars)
def _get_vector_retriever() -> Optional[Any]:
    """
    Initialize and return a vector retriever for RAG operations.
    Returns None if vector DB is not configured or CAMEL-AI RAG components are not available.
    """
    try:
        qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
        qdrant_api_key = os.getenv("QDRANT_API_KEY")
        collection_name = os.getenv("QDRANT_COLLECTION", "log_fixes")
        qdrant_timeout = float(os.getenv("QDRANT_TIMEOUT", "30.0"))
        
        openai_base_url = os.getenv("OPENAI_EMBEDDING_BASE_URL", os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"))
        openai_api_key = os.getenv("OPENAI_EMBEDDING_API_KEY", os.getenv("OPENAI_API_KEY"))
        
        if not openai_api_key:
            raise ValueError(
                "OPENAI_API_KEY or OPENAI_EMBEDDING_API_KEY environment variable must be set "
                "to use OpenAI embeddings"
            )
        
        # Initialize OpenAI embedding model: text-embedding-3-small
        # This model produces 1536-dimensional vectors optimized for semantic search
        embedding = OpenAIEmbedding(
            model_type=EmbeddingModelType.TEXT_EMBEDDING_3_SMALL,
            url=openai_base_url,
            api_key=openai_api_key
        )
        
        vector_dim = int(os.getenv("EMBEDDING_DIM", "1536"))
        
        url_and_api_key = (qdrant_url, qdrant_api_key)
        
        qdrant_kwargs = {
            "distance": VectorDistance.COSINE
        }
        
        # Add timeout if specified (helps prevent hanging connections)
        if qdrant_timeout:
            qdrant_kwargs["timeout"] = qdrant_timeout
        
        # Enable cloud_inference for Qdrant Cloud instances
        if qdrant_url and "cloud.qdrant.io" in qdrant_url:
            qdrant_kwargs["cloud_inference"] = True
        
        storage = QdrantStorage(
            vector_dim=vector_dim,
            collection_name=collection_name,
            url_and_api_key=url_and_api_key,
            **qdrant_kwargs
        )
        
        retriever = VectorRetriever(
            embedding_model=embedding,
            storage=storage
        )
        
        return retriever
    except Exception as e:
        error_msg = str(e)
        # Provide more helpful error messages for timeout issues
        if "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
            print(f"Warning: Vector DB connection timed out: {error_msg}")
            print("Hint: Check QDRANT_URL and network connectivity. You can increase timeout with QDRANT_TIMEOUT env var.")
        else:
            print(f"Warning: Vector DB not available: {error_msg}")
        return None


_retriever_cache: Optional[Any] = None


def _format_rag_results(results: List[Any]) -> List[Dict[str, Any]]:
    formatted_results = []
    for result in results:
        # Extract content - prefer 'fix' field from payload, fallback to content/text
        content = None
        metadata = {}

        # Try to get payload/metadata from result
        if hasattr(result, 'payload'):
            payload = result.payload
            # Prefer the 'fix' field if available (most relevant for error fixes)
            content = payload.get('fix') or payload.get('text') or payload.get('content')
            # Extract metadata (all payload fields except text/error/fix)
            metadata = {k: v for k, v in payload.items()
                       if k not in ['text', 'error', 'fix', 'content']}
        elif hasattr(result, 'content'):
            content = result.content
        elif hasattr(result, 'text'):
            content = result.text
        else:
            content = str(result)

        # Get metadata from result.metadata if available
        if hasattr(result, 'metadata') and result.metadata:
            metadata.update(result.metadata)

        # Get score
        score = result.score if hasattr(result, 'score') else 0.0

        formatted_results.append({
            "content": content or "No content available",
            "score": score,
            "metadata": metadata
        })

    return formatted_results


def _is_no_results(formatted: List[Dict[str, Any]]) -> bool:
    if not formatted:
        return True
    if len(formatted) != 1:
        return False
    entry = formatted[0]
    if "error" in entry:
        return False
    text = " ".join(
        str(entry.get(key, "")) for key in ("message", "content", "suggestion", "warning")
    ).lower()
    return (
        "no similar fixes found" in text
        or "no suitable information retrieved" in text
    )


def _query_with_threshold(retriever: Any, query: str, top_k: int, threshold: float) -> Tuple[List[Any], bool]:
    try:
        return retriever.query(query=query, top_k=top_k, similarity_threshold=threshold), True
    except TypeError:
        try:
            return retriever.query(query=query, top_k=top_k, score_threshold=threshold), True
        except TypeError:
            return retriever.query(query=query, top_k=top_k), False


def search_fixes_for_error(error_log: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """
    Search the vector database for fixes and solutions related to an error log.
    
    This tool uses RAG (Retrieval-Augmented Generation) to find similar past errors
    and their associated fixes from the knowledge base. The vector database contains
    embeddings of error logs and their corresponding solutions.
    
    Args:
        error_log: The error log message or description to search for
        top_k: Number of most relevant results to return (default: 5, max: 20)
    
    Returns:
        A list of dictionaries containing:
        - content: The fix or solution text
        - score: Relevance score (higher is better)
        - metadata: Additional metadata about the fix (if available)
    """
    global _retriever_cache
    
    if _retriever_cache is None:
        _retriever_cache = _get_vector_retriever()

    if _retriever_cache is None:
        return [{
            "error": "Vector database not configured or unavailable",
            "suggestion": "Please configure QDRANT_URL and related environment variables"
        }]
    
    try:
        top_k = min(max(1, top_k), 20)
        

        start_threshold = float(os.getenv("RAG_SIMILARITY_START", "0.7"))
        step = float(os.getenv("RAG_SIMILARITY_STEP", "0.1"))
        if step <= 0:
            step = 0.1
        start_threshold = max(0.0, min(1.0, start_threshold))

        thresholds = []
        current = start_threshold
        while current > 0:
            thresholds.append(round(current, 2))
            current -= step
        if not thresholds or thresholds[-1] != 0.0:
            thresholds.append(0.0)

        threshold_supported = True
        for idx, threshold in enumerate(thresholds):
            results, threshold_supported = _query_with_threshold(
                _retriever_cache,
                query=str(error_log),
                top_k=top_k,
                threshold=threshold,
            )
            formatted_results = _format_rag_results(results)
            if not _is_no_results(formatted_results):
                if threshold_supported and idx > 0:
                    formatted_results.insert(0, {
                        "message": (
                            "No suitable results at higher similarity. "
                            f"Lowered similarity threshold to {threshold:.2f}."
                        ),
                        "warning": "Results may be less precise; verify relevance.",
                        "similarity_threshold": threshold,
                    })
                return formatted_results
            if not threshold_supported:
                break

        return [{
            "message": "No similar fixes found in the knowledge base",
            "suggestion": "This may be a new error that hasn't been seen before",
            "note": "Similarity threshold was lowered down to 0.0 with no results."
        }]
    except Exception as e:
        return [{
            "error": f"RAG search failed: {str(e)}",
            "suggestion": "Check vector database connection and configuration"
        }]


def add_fix_to_knowledge_base(error_log: str, fix_description: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Add a new error-fix pair to the vector database knowledge base.
    
    This tool allows the system to learn from resolved issues by storing
    error logs and their corresponding fixes in the vector database.
    
    Args:
        error_log: The error log message
        fix_description: Description of the fix or solution
        metadata: Optional metadata (e.g., service name, severity, date)
    
    Returns:
        A dictionary indicating success or failure
    """
    global _retriever_cache
    
    if _retriever_cache is None:
        _retriever_cache = _get_vector_retriever()
    
    if _retriever_cache is None:
        return {
            "error": "Vector database not configured",
            "success": False
        }
    
    try:
        # Combine error and fix for embedding
        combined_text = f"Error: {error_log}\n\nFix: {fix_description}"
        
        # Get embedding for the combined text
        embedding_model = _retriever_cache.embedding_model
        if embedding_model is None:
            return {
                "error": "Embedding model not available",
                "success": False
            }
        
        embedding_vector = embedding_model.embed(combined_text)
        
        # Create payload with structured fields
        # 'text' is used by CAMEL-AI for content extraction
        # 'fix' is the primary field we want to retrieve
        # 'error' is stored for reference
        payload = {
            "text": combined_text,  # Full combined text for embedding context
            "content": combined_text,  # Alternative field name some retrievers use
            "error": error_log,  # Original error message
            "fix": fix_description,  # The fix/solution (primary content to retrieve)
            **(metadata or {})  # Additional metadata fields
        }
        
        record = VectorRecord(
            vector=embedding_vector,
            id=str(uuid.uuid4()),
            payload=payload
        )
        
        if hasattr(_retriever_cache.storage, 'add'):
            _retriever_cache.storage.add([record])
            return {
                "success": True,
                "message": "Fix added to knowledge base"
            }
        else:
            return {
                "error": "Storage backend does not support adding new entries",
                "success": False
            }
    except Exception as e:
        return {
            "error": f"Failed to add fix to knowledge base: {str(e)}",
            "success": False
        }
