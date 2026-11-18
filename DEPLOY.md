# Deploying Ironvale for real users

Everything below except the API host runs on free tiers. Do the steps in order. **Keys go only into `.env` on
your laptop and into each host's secrets page, never into chat or git.**

| Piece | Service | Plan |
|---|---|---|
| Postgres + pgvector | Neon | Free |
| Knowledge graph | Neo4j AuraDB | Free |
| Tracing | Langfuse Cloud | Hobby (free) |
| LLM | Groq | Developer, pay as you go (set a spend limit) |
| API | Hugging Face Space (Docker, CPU Basic 16 GB) | needs HF PRO, $9/month |
| Website | Vercel | Hobby (free) |

## 1. Accounts and keys (about 15 minutes)

1. **Groq:** console.groq.com → API Keys → create a key. In Settings → Billing, add a card and **set a spend limit of $5**. In Settings → Data Controls, switch on **Zero Data Retention**.
2. **Neon:** neon.tech → New project `ironvale` (region: AWS Asia Pacific, Singapore) → copy the connection string (Connection details → "Pooled connection" off). It looks like `postgresql://neondb_owner:...@ep-xxx.ap-southeast-1.aws.neon.tech/neondb?sslmode=require`.
3. **Neo4j AuraDB:** console.neo4j.io → New instance → AuraDB Free → download the credentials file. You need the `NEO4J_URI` (`neo4j+s://xxxx.databases.neo4j.io`), the user `neo4j` and the password.
4. **Langfuse Cloud:** cloud.langfuse.com → New project `ironvale` → Settings → API keys → create. Copy the public key, secret key and host (`https://cloud.langfuse.com`).

## 2. Load the data from your laptop (about 10 minutes)

You need Python **3.11 or newer** (the macOS system Python 3.9 won't work) and Tesseract.
```bash
brew install python@3.12 tesseract
git clone <your repo url> ironvale-assistant && cd ironvale-assistant
/opt/homebrew/bin/python3.12 -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt && python -m spacy download en_core_web_sm
cp .env.example .env
```
Edit `.env`: set `LLM_API_KEY`, `DATABASE_URL` (Neon), `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` (Aura), and the three
`LANGFUSE_*` values (Cloud). Then:
```bash
./setup_data.sh        # seeds Neon (tables, roles, RLS), ingests the 23 documents with OCR + masking, loads Neo4j
cd backend && python -m pytest -q && cd ..                  # 76 passed
cd backend && uvicorn app.main:app --port 8000              # local API check: open http://localhost:8000/health
```
`/health` should show `"status": "ok"`, `"chunks": 110`, `"llm_configured": true`, `"langfuse": true`.

## 3. Put the API online (Hugging Face Space)

1. huggingface.co → subscribe to PRO (Docker Spaces need it) → New Space → name `ironvale-api`, SDK **Docker**, hardware **CPU Basic**, visibility Public.
2. In the Space → Settings → **Variables and secrets**, add secrets: `LLM_API_KEY`, `DATABASE_URL`, `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST`. Add variables: `LLM_BASE_URL=https://api.groq.com/openai/v1`, `LLM_MODEL=openai/gpt-oss-120b`, `LLM_FAST_MODEL=llama-3.1-8b-instant`, `RERANK_THRESHOLD=0.30`, `CORS_ORIGINS=https://<your-vercel-app>.vercel.app` (fill in after step 4, then restart the Space).
3. Push the code:
   ```bash
   ./deploy/make_hf_space.sh ../ironvale-api-space
   cd ../ironvale-api-space
   git init -b main && git remote add origin https://huggingface.co/spaces/<hf-username>/ironvale-api
   git add -A && git commit -m "Ironvale API" && git push -u origin main   # password = an HF access token (write)
   ```
4. The first build takes about 10 minutes (it bakes the bge models into the image). Check `https://<hf-username>-ironvale-api.hf.space/health`.

## 4. Put the website online (Vercel)

1. vercel.com → Add New → Project → import the GitHub repo.
2. **Root Directory: `frontend`.** Framework: Next.js (auto-detected).
3. Environment variable: `NEXT_PUBLIC_API_URL=https://<hf-username>-ironvale-api.hf.space`.
4. Deploy. Then copy the Vercel URL into the Space's `CORS_ORIGINS` and restart the Space.

## 5. Check it like a client would

Open the Vercel URL on your phone and laptop and run the demo script:
1. As **Priya (Line 1)**: "What does alarm E-417 mean on the DMC 850?" → answer cites **MAN-CNC-04 p. 42**. Then "Can I bypass it to finish the batch?" → **"Understood as: … E-417"**, and the answer is No.
2. "Breakdown downtime by machine on Line 1 in October 2026" → bar chart of 6 machines, the table and the SQL.
3. Switch to **Farah**: "Which suppliers are behind deviations on Line 1 this year?" → graph path Arcflow → HX-220-B → QDR-2026-014 → CNC-L1-04.
4. As **Priya**: "What's the unit price of HX-220-B?" → not found. In Langfuse, open that trace: the `retrieve.bm25` and `retrieve.dense` spans list no `PRC-2026-Q3` chunk.
5. Open **Evaluation** in the app after running `python eval/run_eval.py` (from `backend/`, against Neon).

## Running costs and limits

- The Neon free compute sleeps after 5 minutes idle; the first question after that takes a few extra seconds.
- AuraDB Free pauses after 3 days without use: resume it in the Aura console before a demo.
- Groq Developer tier: the whole demo and a full eval run cost well under ₹50. The spend limit stops runaway loops.
