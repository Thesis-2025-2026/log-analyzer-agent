"""
Seed the auth-service Qdrant collection with runbook entries.

Standalone script - uses openai + qdrant-client directly so it can run
in a minimal container without importing the main codebase.
"""

import os
import sys
import time
import uuid

from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
COLLECTION = os.getenv("QDRANT_COLLECTION", "auth_log_fixes")
EMBEDDING_MODEL = "text-embedding-3-small"
VECTOR_DIM = 1536

RUNBOOKS = [
    {
        "error": "authentication rejected - oauth_token_exchange_failed",
        "fix": (
            "When authentication rejected errors spike with error_code "
            "oauth_token_exchange_failed, check recent deployments to the auth "
            "service. A schema change in the OAuth callback payload is a known "
            "cause. Verify deployment status via the deployments-service and "
            "check if a rollback was triggered. Also verify IdP provider health "
            "to rule out external provider issues."
        ),
        "tags": "oauth,deployment,rollback,callback_schema",
    },
    {
        "error": "authentication rejected - idp_unreachable",
        "fix": (
            "When authentication fails with error_code idp_unreachable, check "
            "external identity provider (Okta/Auth0) health status. If the "
            "provider is degraded, escalate to the IdP team. If the provider is "
            "healthy, check internal network and firewall rules between the auth "
            "service and the IdP endpoint."
        ),
        "tags": "oauth,idp,provider,network",
    },
    {
        "error": "token signing key missing",
        "fix": (
            "When token signing fails with error_code signing_key_missing, "
            "verify that the expected key ID exists in the key store. Common "
            "causes: key rotation completed but old key ID still referenced in "
            "config, or secrets vault sync lag after a deployment. Restart the "
            "auth pods after confirming the key is present."
        ),
        "tags": "token,signing,key_rotation",
    },
]


def wait_for_qdrant(client: QdrantClient, retries: int = 30, delay: float = 2.0) -> None:
    for attempt in range(retries):
        try:
            client.get_collections()
            return
        except Exception:
            if attempt < retries - 1:
                print(f"Qdrant not ready, retrying in {delay}s... ({attempt + 1}/{retries})")
                time.sleep(delay)
    print("ERROR: Qdrant did not become ready in time.")
    sys.exit(1)


def main() -> None:
    openai_key = os.getenv("OPENAI_API_KEY")
    if not openai_key:
        print("ERROR: OPENAI_API_KEY is required.")
        sys.exit(1)

    oai = OpenAI(api_key=openai_key)
    qd = QdrantClient(url=QDRANT_URL, timeout=30)

    print(f"Waiting for Qdrant at {QDRANT_URL} ...")
    wait_for_qdrant(qd)

    if not qd.collection_exists(COLLECTION):
        qd.create_collection(
            collection_name=COLLECTION,
            vectors_config=VectorParams(size=VECTOR_DIM, distance=Distance.COSINE),
        )
        print(f"Created collection '{COLLECTION}'.")
    else:
        info = qd.get_collection(COLLECTION)
        if info.points_count and info.points_count >= len(RUNBOOKS):
            print(f"Collection '{COLLECTION}' already has {info.points_count} points - skipping seed.")
            return
        print(f"Collection '{COLLECTION}' exists ({info.points_count} points), adding entries.")

    points = []
    for entry in RUNBOOKS:
        combined = f"Error: {entry['error']}\n\nFix: {entry['fix']}"
        resp = oai.embeddings.create(input=combined, model=EMBEDDING_MODEL)
        vector = resp.data[0].embedding

        points.append(
            PointStruct(
                id=str(uuid.uuid4()),
                vector=vector,
                payload={
                    "text": combined,
                    "content": combined,
                    "error": entry["error"],
                    "fix": entry["fix"],
                    "tags": entry["tags"],
                    "source": "runbook_seed",
                },
            )
        )

    qd.upsert(collection_name=COLLECTION, points=points)
    print(f"Seeded {len(points)} runbook entries into '{COLLECTION}'.")


if __name__ == "__main__":
    main()
