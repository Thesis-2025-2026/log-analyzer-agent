"""
Report RAG Tool for searching previous reports that were helpful to users.

Reports are synthesized outputs and may contain inaccuracies.
Always validate against logs or primary sources.
"""
from typing import List, Dict, Any, Optional, Tuple
import ast
import json
import os
import re
import uuid

from camel.retrievers import VectorRetriever
from camel.embeddings import OpenAIEmbedding
from camel.storages import QdrantStorage
from camel.types import EmbeddingModelType, VectorDistance
from camel.storages.vectordb_storages.base import VectorRecord


REPORT_WARNING = (
    "Report content is synthesized and may be inaccurate. "
    "Validate with logs or primary sources."
)


def _get_report_retriever() -> Optional[Any]:
    """
    Initialize and return a vector retriever for report RAG operations.
    Returns None if vector DB is not configured or unavailable.
    """
    try:
        qdrant_url = os.getenv("QDRANT_REPORT_URL", os.getenv("QDRANT_URL", "http://localhost:6333"))
        qdrant_api_key = os.getenv("QDRANT_REPORT_API_KEY", os.getenv("QDRANT_API_KEY"))
        collection_name = os.getenv("QDRANT_REPORT_COLLECTION", "report_knowledge")
        qdrant_timeout = float(os.getenv("QDRANT_TIMEOUT", "30.0"))

        openai_base_url = os.getenv(
            "OPENAI_EMBEDDING_BASE_URL",
            os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        )
        openai_api_key = os.getenv("OPENAI_EMBEDDING_API_KEY", os.getenv("OPENAI_API_KEY"))

        if not openai_api_key:
            raise ValueError(
                "OPENAI_API_KEY or OPENAI_EMBEDDING_API_KEY environment variable must be set "
                "to use OpenAI embeddings"
            )

        embedding = OpenAIEmbedding(
            model_type=EmbeddingModelType.TEXT_EMBEDDING_3_SMALL,
            url=openai_base_url,
            api_key=openai_api_key,
        )

        vector_dim = int(os.getenv("EMBEDDING_DIM", "1536"))
        url_and_api_key = (qdrant_url, qdrant_api_key)

        qdrant_kwargs = {"distance": VectorDistance.COSINE}
        if qdrant_timeout:
            qdrant_kwargs["timeout"] = qdrant_timeout

        if qdrant_url and "cloud.qdrant.io" in qdrant_url:
            qdrant_kwargs["cloud_inference"] = True

        storage = QdrantStorage(
            vector_dim=vector_dim,
            collection_name=collection_name,
            url_and_api_key=url_and_api_key,
            **qdrant_kwargs,
        )

        return VectorRetriever(embedding_model=embedding, storage=storage)
    except Exception as e:
        error_msg = str(e)
        if "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
            print(f"Warning: Report vector DB connection timed out: {error_msg}")
            print("Hint: Check QDRANT_REPORT_URL/QDRANT_URL and network connectivity.")
        else:
            print(f"Warning: Report vector DB not available: {error_msg}")
        return None


_report_retriever_cache: Optional[Any] = None


_REPORT_TAG_KEYS = (
    "service",
    "service_owner",
    "level",
    "error_code",
    "incident_id",
    "incident_cause",
    "trace_id",
    "order_id",
    "customer_id",
    "method",
    "component",
    "message",
)

_REPORT_ID_PATTERNS = (
    r"\bORD-\d+\b",
    r"\bCUST-\d+\b",
    r"\btr_[A-Za-z0-9]+\b",
    r"\binc_\d+\b",
)


def _safe_parse_raw_log(raw_log: Optional[Any]) -> Optional[Dict[str, Any]]:
    if raw_log is None:
        return None
    if isinstance(raw_log, dict):
        return raw_log
    if isinstance(raw_log, str):
        try:
            return json.loads(raw_log)
        except json.JSONDecodeError:
            return None
    return None


def _collect_report_tags(metadata: Dict[str, Any]) -> List[str]:
    tags = set()

    for key in ("service", "level", "trace_id", "incident_id", "incident_cause", "error_code"):
        value = metadata.get(key)
        if value:
            tags.add(str(value))

    raw_log = metadata.get("raw_log")
    parsed = _safe_parse_raw_log(raw_log)
    if parsed:
        for key in _REPORT_TAG_KEYS:
            value = parsed.get(key)
            if value:
                tags.add(str(value))

    source_text = ""
    if isinstance(raw_log, str):
        source_text = raw_log
    elif parsed:
        source_text = json.dumps(parsed)

    if source_text:
        for pattern in _REPORT_ID_PATTERNS:
            for match in re.findall(pattern, source_text):
                tags.add(match)

    clean = []
    for tag in tags:
        tag = str(tag).strip()
        if tag and len(tag) <= 120:
            clean.append(tag)

    return sorted(clean)


def _build_report_search_text(report_text: str, metadata: Dict[str, Any]) -> Tuple[str, List[str]]:
    tags = _collect_report_tags(metadata)
    parts = []
    report_id = metadata.get("report_id")
    if report_id is not None:
        parts.append(f"Report ID: {report_id}")
        parts.append(f"Report Link: /report/{report_id}")
    service = metadata.get("service")
    if service:
        parts.append(f"Service: {service}")
    title = metadata.get("title")
    if title:
        parts.append(f"Title: {title}")
    level = metadata.get("level")
    if level:
        parts.append(f"Level: {level}")
    trace_id = metadata.get("trace_id")
    if trace_id:
        parts.append(f"Trace: {trace_id}")
    incident_id = metadata.get("incident_id")
    if incident_id:
        parts.append(f"Incident: {incident_id}")
    error_code = metadata.get("error_code")
    if error_code:
        parts.append(f"Error code: {error_code}")
    if tags:
        parts.append("Tags: " + ", ".join(tags))

    if parts:
        return "\n".join(parts), tags

    return report_text, tags


def _query_with_threshold(retriever: Any, query: str, top_k: int, threshold: float) -> Tuple[List[Any], bool]:
    try:
        return retriever.query(query=query, top_k=top_k, similarity_threshold=threshold), True
    except TypeError:
        try:
            return retriever.query(query=query, top_k=top_k, score_threshold=threshold), True
        except TypeError:
            return retriever.query(query=query, top_k=top_k), False


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
        "no similar reports found" in text
        or "no suitable information retrieved" in text
    )

def _format_report_results(results: List[Any]) -> List[Dict[str, Any]]:
    formatted: List[Dict[str, Any]] = []
    for result in results:
        content = None
        metadata = {}

        if hasattr(result, "payload"):
            payload = result.payload
            content = payload.get("report") or payload.get("text") or payload.get("content")
            metadata = {k: v for k, v in payload.items() if k not in ["text", "content", "report"]}
        elif hasattr(result, "content"):
            content = result.content
        elif hasattr(result, "text"):
            content = result.text
        else:
            content = str(result)

        if hasattr(result, "metadata") and result.metadata:
            metadata.update(result.metadata)

        if isinstance(content, str):
            trimmed = content.strip()
            if trimmed.startswith("{") and "'text'" in trimmed:
                try:
                    parsed = ast.literal_eval(trimmed)
                    if isinstance(parsed, dict):
                        content = parsed.get("text") or parsed.get("content") or content
                        meta_candidate = parsed.get("metadata")
                        if isinstance(meta_candidate, dict):
                            metadata.update(meta_candidate)
                except (ValueError, SyntaxError):
                    pass

        score = result.score if hasattr(result, "score") else 0.0
        entry: Dict[str, Any] = {
            "content": content or "No content available",
            "score": score,
            "metadata": metadata,
            "warning": REPORT_WARNING,
        }
        report_id = metadata.get("report_id")
        if report_id is None and isinstance(content, str):
            match = re.search(r"/report/(\\d+)", content)
            if not match:
                match = re.search(r"report id\\s*[:#]?\\s*(\\d+)", content, re.IGNORECASE)
            if match:
                report_id = match.group(1)
        if report_id is not None:
            entry["report_id"] = report_id
            entry["report_link"] = f"/report/{report_id}"
            try:
                from agent_system.core.storage import get_report
                report_row = get_report(int(report_id))
                if report_row:
                    created_at = report_row.get("created_at")
                    if hasattr(created_at, "isoformat"):
                        created_at = created_at.isoformat()
                    entry["report_title"] = report_row.get("title")
                    entry["report_content"] = report_row.get("content")
                    entry["report_raw_log"] = report_row.get("raw_log")
                    entry["report_service"] = report_row.get("service")
                    entry["report_created_at"] = created_at
            except Exception:
                pass
        formatted.append(entry)
    return formatted


def search_reports_for_context(query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """
    Look through previous reports that were helpful to users.

    Reports are synthesized and may be inaccurate; always validate with logs.
    """
    global _report_retriever_cache

    if _report_retriever_cache is None:
        _report_retriever_cache = _get_report_retriever()

    if _report_retriever_cache is None:
        return [{
            "error": "Report vector database not configured or unavailable",
            "warning": REPORT_WARNING,
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
                _report_retriever_cache,
                query=str(query),
                top_k=top_k,
                threshold=threshold,
            )
            formatted = _format_report_results(results)
            if not _is_no_results(formatted):
                if threshold_supported and idx > 0:
                    formatted.insert(0, {
                        "message": (
                            "No suitable results at higher similarity. "
                            f"Lowered similarity threshold to {threshold:.2f}."
                        ),
                        "warning": "Results may be less precise; verify relevance.",
                        "similarity_threshold": threshold,
                    })
                return formatted
            if not threshold_supported:
                break

        return [{
            "message": "No similar reports found in the report knowledge base",
            "warning": REPORT_WARNING,
            "note": "Similarity threshold was lowered down to 0.0 with no results.",
        }]
    except Exception as e:
        return [{
            "error": f"Report RAG search failed: {str(e)}",
            "warning": REPORT_WARNING,
        }]


def add_report_to_knowledge_base(report_text: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Add a report to the report knowledge base.

    Reports are synthesized and should not be treated as ground truth.
    """
    global _report_retriever_cache

    if _report_retriever_cache is None:
        _report_retriever_cache = _get_report_retriever()

    if _report_retriever_cache is None:
        return {
            "error": "Report vector database not configured",
            "success": False,
        }

    if not isinstance(report_text, str) or not report_text.strip():
        return {
            "error": "Report text must be a non-empty string",
            "success": False,
        }

    try:
        embedding_model = _report_retriever_cache.embedding_model
        if embedding_model is None:
            return {
                "error": "Embedding model not available",
                "success": False,
            }

        meta = metadata or {}
        search_text, tags = _build_report_search_text(report_text, meta)

        embedding_vector = embedding_model.embed(search_text)

        payload = {
            "text": search_text,
            "content": report_text,
            "report": report_text,
            "search_text": search_text,
            "tags": tags,
            "source": "generated_report",
            **meta,
        }

        record = VectorRecord(
            vector=embedding_vector,
            id=str(uuid.uuid4()),
            payload=payload,
        )

        if hasattr(_report_retriever_cache.storage, "add"):
            _report_retriever_cache.storage.add([record])
            return {
                "success": True,
                "message": "Report added to report knowledge base",
            }

        return {
            "error": "Storage backend does not support adding new entries",
            "success": False,
        }
    except Exception as e:
        return {
            "error": f"Failed to add report to knowledge base: {str(e)}",
            "success": False,
        }
