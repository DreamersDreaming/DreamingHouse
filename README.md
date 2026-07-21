# Doream Recall — Agentic Dream Memory

A new, isolated project for the **CockroachDB × AWS Hackathon: Build with Agentic Memory**. It is not the pre-existing Doream production repository.

Doream Recall accepts one remembered dream scene, retrieves only the user's own semantically related dream memories from CockroachDB, asks Amazon Bedrock for a bounded non-diagnostic reflection, and writes the result and an auditable action record back to CockroachDB. Memory is the product behavior: the agent can notice recurring user-supplied themes across private sessions without inventing facts.

## Core loop

1. `remember` — persist the explicit scene, emotion, and optional real-life context.
2. `retrieve` — query CockroachDB Distributed Vector Indexing for related memories owned by the same user.
3. `reflect` — call Amazon Bedrock with a strict contract: mirror only supplied/retrieved details; never diagnose or predict.
4. `act` — write the grounded Dream Card reflection and audit record transactionally.

## Required hackathon technologies

- **CockroachDB Distributed Vector Indexing** — per-user semantic retrieval with operational records and embeddings in one consistent database.
- **CockroachDB Cloud Managed MCP Server** — read-only inspection of schema, safe queries, and audit-visible agent/developer operations during build and judging.
- **Amazon Bedrock** — foundation-model inference for the grounded reflection.
- **AWS Lambda** — serverless execution of the agent loop.

The final submission must show both CockroachDB tools and the AWS deployment working. Merely listing them is not enough.

## Privacy and safety

- raw dream entries are private by default;
- every query is scoped by `user_id`;
- the model prompt forbids diagnosis, prediction, supernatural claims, and details absent from the user's records;
- the agent stores a compact audit trail with the retrieved memory IDs;
- production Doream data and secrets are never copied into this repository.

## Local tests

```bash
python -m unittest discover -s tests -v
```

Tests exercise the prompt contract, request validation, and ownership-scoped SQL without connecting to CockroachDB or AWS.

## Configure CockroachDB Cloud

1. Create a CockroachDB Cloud cluster and a dedicated database/user for this demo.
2. Enable vector indexes when required by the selected cluster version:

   ```sql
   SET CLUSTER SETTING feature.vector_index.enabled = true;
   ```

3. Export the least-privilege connection string, then apply the idempotent schema:

   ```bash
   export DATABASE_URL='postgresql://...'
   python scripts/apply_schema.py
   ```

The vector index uses `user_id` as a prefix column. Every retrieval query constrains that prefix before ordering by cosine distance.

## Deploy to AWS

The included AWS SAM template creates an HTTP API and Python 3.12 Lambda with least-privilege permission to invoke Amazon Nova Lite and Amazon Titan Text Embeddings V2.

The same Lambda serves a small judge-facing browser demo at `GET /`; `POST /reflect` runs the agent. The page asks for a private demo key and generates a random session UUID locally.

```bash
sam build
sam deploy --guided \
  --parameter-overrides \
  DatabaseUrl="$DATABASE_URL" \
  DemoApiKey="$DEMO_API_KEY"
```

Call the deployed endpoint twice with the same randomly generated UUID to demonstrate durable memory retrieval:

```bash
curl -X POST "$REFLECT_ENDPOINT" \
  -H 'content-type: application/json' \
  -H "x-doream-demo-key: $DEMO_API_KEY" \
  -d '{"user_id":"00000000-0000-4000-8000-000000000001","scene":"A blue whale crossed the stars.","emotion":"wonder"}'
```

Never use production Doream user data for the demo. The judge key and database URL must not be committed.

## Deployment evidence gate

Do not claim a working submission until all of these are real:

- CockroachDB Cloud cluster created with vector support;
- schema applied and a least-privilege application user configured;
- Managed MCP endpoint used in read-only mode and its audit evidence preserved;
- AWS Lambda deployed and invokes Amazon Bedrock;
- a public demo URL exercises two sessions and visibly retrieves prior memory;
- public open-source repository includes a license, configuration example, and exact setup steps;
- public video under three minutes shows the CockroachDB memory layer at work.

`Doream` means **Do + Dream**: do the small act of recording a dream now; an optional future impact layer may help children pursue their dreams. Ownership transfer, trading, blockchain settlement, and the Impact Reserve are future/non-live and are not part of this hackathon build.
