# Task Doc — AI Image Understanding & Content Matching Engine

Document that details the problem of the task and stack decisions.

## 1. Problem
 
Given a library of images and a set of blog posts, understand what each image
actually depicts, and match each post to the image that best represents its
content — based on meaning, not filenames or keywords. When no image is a
confident enough match, say so explicitly instead of guessing. The
production-critical piece is not finding a match, it's refusing a bad one
(the "mismatch guard").
 
## 2. Stack decisions
 
These are locked in to keep third-party overhead minimal:
 
| Concern | Choice | Why |
|---|---|---|
| Language | Python (+ FastAPI) | Chosen lane for this capstone |
| Vision model | Gemini Flash (cloud, free tier) | Avoids local model downloads (Ollama) |
| Embeddings | Gemini embeddings (cloud, free tier) | Same reasoning — one cloud provider, no local model management |
| Database | SQLite, via SQLAlchemy + Alembic | No Docker, ships with Python — matches the "minimal third-party downloads" goal. SQLAlchemy keeps models DB-agnostic (rubric: "swap the DB... without touching business logic"), so swapping to Postgres later is a config change, not a rewrite. Alembic covers the "schema as migrations" shared requirement (§12 #4). |
| Image storage | In-DB `BLOB` column on `images`, not a separate object store | ~50 images is small enough that this stays free and simple; no S3/Docker-based blob storage needed |
| Vectors | JSON-encoded float arrays (SQLite has no native array/vector type) | No `pgvector` needed either — cosine similarity is computed in Python over ~50 rows, which is trivial at this scale |
| Schema validation | Pydantic | `model_validate_json()` rejects malformed vision output before it's trusted |
| Corpus | Unsplash / Pexels licensed-free images | Required by §3 of the brief; committed or fetched via a seed script |
 