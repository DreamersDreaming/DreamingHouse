"""Ownership-scoped memory retrieval and bounded Bedrock reflection."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Iterable
from uuid import UUID


BOUNDARY = (
    "You are a private dream-memory reflection assistant. Mirror only details explicitly "
    "present in the current entry or the user's retrieved memories. Do not diagnose, "
    "predict the future, claim supernatural meaning, or add facts. Use tentative language."
)


@dataclass(frozen=True)
class DreamInput:
    user_id: str
    scene: str
    emotion: str = ""
    real_life_context: str = ""

    @classmethod
    def from_payload(cls, payload: dict) -> "DreamInput":
        user_id = str(payload.get("user_id", "")).strip()
        scene = " ".join(str(payload.get("scene", "")).split())
        if not user_id:
            raise ValueError("user_id is required")
        try:
            UUID(user_id)
        except ValueError as exc:
            raise ValueError("user_id must be a valid UUID") from exc
        if not scene:
            raise ValueError("scene is required")
        if len(scene) > 1_200:
            raise ValueError("scene must be 1,200 characters or fewer")
        return cls(
            user_id=user_id,
            scene=scene,
            emotion=" ".join(str(payload.get("emotion", "")).split()),
            real_life_context=" ".join(str(payload.get("real_life_context", "")).split()),
        )


def similar_memory_query() -> str:
    return """
        SELECT id, scene, emotion, real_life_context,
               embedding <=> %(embedding)s::VECTOR AS distance
        FROM dream_memories
        WHERE user_id = %(user_id)s::UUID
          AND id <> %(current_memory_id)s::UUID
        ORDER BY embedding <=> %(embedding)s::VECTOR
        LIMIT 5
    """.strip()


def build_reflection_prompt(current: DreamInput, memories: Iterable[dict]) -> str:
    prior = list(memories)
    memory_json = json.dumps(prior, ensure_ascii=False)
    return (
        f"{BOUNDARY}\n\n"
        "Current user-supplied entry:\n"
        f"scene: {current.scene}\n"
        f"emotion: {current.emotion or '(not supplied)'}\n"
        f"real-life context: {current.real_life_context or '(not supplied)'}\n\n"
        "Related memories owned by the same user (may be empty):\n"
        f"{memory_json}\n\n"
        "Return JSON with keys summary, recurring_patterns, and one_gentle_question. "
        "If no pattern is supported, recurring_patterns must be an empty array."
    )


def memory_text(dream: DreamInput) -> str:
    """Return only user-supplied fields for embedding."""
    fields = [f"scene: {dream.scene}"]
    if dream.emotion:
        fields.append(f"emotion: {dream.emotion}")
    if dream.real_life_context:
        fields.append(f"real-life context: {dream.real_life_context}")
    return "\n".join(fields)


def invoke_embedding(text: str) -> list[float]:
    """Create a 1,024-dimension Bedrock Titan embedding."""
    import boto3

    region = os.environ.get("AWS_REGION", "us-east-1")
    model_id = os.environ.get(
        "BEDROCK_EMBEDDING_MODEL_ID", "amazon.titan-embed-text-v2:0"
    )
    client = boto3.client("bedrock-runtime", region_name=region)
    response = client.invoke_model(
        modelId=model_id,
        contentType="application/json",
        accept="application/json",
        body=json.dumps(
            {"inputText": text, "dimensions": 1024, "normalize": True}
        ),
    )
    payload = json.loads(response["body"].read())
    embedding = payload.get("embedding")
    if not isinstance(embedding, list) or len(embedding) != 1024:
        raise RuntimeError("Bedrock did not return a 1,024-dimension embedding")
    return [float(value) for value in embedding]


def vector_literal(embedding: Iterable[float]) -> str:
    values = [float(value) for value in embedding]
    if len(values) != 1024:
        raise ValueError("embedding must contain exactly 1,024 values")
    return "[" + ",".join(f"{value:.9g}" for value in values) + "]"


def invoke_bedrock(prompt: str) -> str:
    import boto3

    region = os.environ.get("AWS_REGION", "us-east-1")
    model_id = os.environ.get("BEDROCK_MODEL_ID", "amazon.nova-lite-v1:0")
    client = boto3.client("bedrock-runtime", region_name=region)
    response = client.converse(
        modelId=model_id,
        system=[{"text": BOUNDARY}],
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        inferenceConfig={"temperature": 0.2, "maxTokens": 700},
    )
    return response["output"]["message"]["content"][0]["text"]


def process_dream(dream: DreamInput, database_url: str) -> dict:
    """Run remember → retrieve → reflect → audit in one DB transaction."""
    import psycopg

    embedding = invoke_embedding(memory_text(dream))
    vector = vector_literal(embedding)
    model_id = os.environ.get("BEDROCK_MODEL_ID", "amazon.nova-lite-v1:0")

    with psycopg.connect(database_url) as connection:
        with connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO dream_memories
                        (user_id, scene, emotion, real_life_context, embedding)
                    VALUES (%(user_id)s::UUID, %(scene)s, %(emotion)s,
                            %(real_life_context)s, %(embedding)s::VECTOR)
                    RETURNING id
                    """,
                    {
                        "user_id": dream.user_id,
                        "scene": dream.scene,
                        "emotion": dream.emotion or None,
                        "real_life_context": dream.real_life_context or None,
                        "embedding": vector,
                    },
                )
                current_memory_id = cursor.fetchone()[0]

                cursor.execute(
                    similar_memory_query(),
                    {
                        "embedding": vector,
                        "user_id": dream.user_id,
                        "current_memory_id": str(current_memory_id),
                    },
                )
                memories = [
                    {
                        "id": str(row[0]),
                        "scene": row[1],
                        "emotion": row[2] or "",
                        "real_life_context": row[3] or "",
                        "distance": float(row[4]),
                    }
                    for row in cursor.fetchall()
                ]

                reflection = invoke_bedrock(build_reflection_prompt(dream, memories))
                retrieved_ids = [memory["id"] for memory in memories]
                cursor.execute(
                    """
                    INSERT INTO reflection_runs
                        (user_id, current_memory_id, retrieved_memory_ids,
                         reflection, model_id)
                    VALUES (%(user_id)s::UUID, %(current_memory_id)s::UUID,
                            %(retrieved_memory_ids)s::UUID[], %(reflection)s,
                            %(model_id)s)
                    RETURNING id
                    """,
                    {
                        "user_id": dream.user_id,
                        "current_memory_id": str(current_memory_id),
                        "retrieved_memory_ids": retrieved_ids,
                        "reflection": reflection,
                        "model_id": model_id,
                    },
                )
                run_id = cursor.fetchone()[0]

    return {
        "status": "ok",
        "memory_id": str(current_memory_id),
        "reflection_run_id": str(run_id),
        "retrieved_memory_ids": retrieved_ids,
        "reflection": reflection,
        "model_id": model_id,
    }
