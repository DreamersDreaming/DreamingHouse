CREATE TABLE IF NOT EXISTS dream_memories (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL,
  scene STRING NOT NULL,
  emotion STRING,
  real_life_context STRING,
  embedding VECTOR(1024) NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- user_id is a prefix column so the ownership filter is applied before ANN
-- search. The query in agent.py constrains this prefix with equality.
CREATE VECTOR INDEX IF NOT EXISTS dream_memories_owner_embedding_idx
ON dream_memories (user_id, embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS dream_memories_owner_time_idx
ON dream_memories (user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS reflection_runs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL,
  current_memory_id UUID NOT NULL REFERENCES dream_memories(id),
  retrieved_memory_ids UUID[] NOT NULL DEFAULT ARRAY[]::UUID[],
  reflection STRING NOT NULL,
  model_id STRING NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
