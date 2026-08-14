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
| Image storage | In-DB array (bytes column), not Docker/blob storage | ~50 images is small enough that this stays free and simple; no object storage service needed |
| Schema validation | Pydantic | `model_validate_json()` rejects malformed vision output before it's trusted |
| Corpus | Unsplash / Pexels licensed-free images | Required by §3 of the brief; committed or fetched via a seed script |
 