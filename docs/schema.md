# Schema Doc — AI Image Understanding & Content Matching Engine

## 1. Image tag schema — the vision model's output contract
 
This is the schema referenced in §4 and §8 of the brief ("the tag JSON
above"). It is the **validated shape of a single Gemini Flash response** for
one image — not the database table. See §4 below for how it's persisted.
 
```json
{
  "subject": "red fox",
  "category": "animal",
  "attributes": ["orange fur", "wild", "forest"],
  "caption": "A red fox standing in a forest",
  "confidence": 0.94
}
```
 
### Field decisions
 
- **`category`** — closed vocabulary (Pydantic `Literal` / `Enum`), not free
  text. Specifics of which items to include in the list  will be decided later.
- **`subject`** — closed vocabulary (Pydantic `Literal` / `Enum`), not free
  text. Each `subject` belongs to a certain `category` that the model predicts. Specifics of which items to include in the list  will be decided later.
- **`attributes`** — stays free-text, list of strings. This only feeds the
  caption/embedding space, never exact-match guard logic, so it doesn't need
  a controlled vocabulary.
- **`caption`** — free text, one sentence. Feeds the embedding.
- **`confidence`** — float, `0.0–1.0`. Matches the brief's definition
  exactly ("the model's own 0–1 estimate"). Kept as a single scalar — no
  per-field confidence, unnecessary at this scale.
### What's explicitly *not* in this schema
 
- No `needs_review` flag — that's derived downstream (`confidence` below
  threshold), not something the model should emit itself.
- No image identifier — the vision model doesn't know its own filename/DB
  id; that gets attached when the response is persisted.
- No model/version metadata — tracked at the call-log level, not per-tag.
## 2. Database schema
 
The architecture diagram in §5 of the brief separates image metadata, image
vectors, and post vectors into distinct stores. The DB design follows that
split rather than collapsing everything into one table.
 
### `images`
One row per image, independent of any AI processing.
 
| Column | Type | Notes |
|---|---|---|
| `id` | PK | |
| `image_data` | bytea / array | in-DB storage per decision in task.md |
| `filename` | text | original filename |
| `source_url` | text | Unsplash/Pexels source, for license traceability |
| `license` | text | e.g. "Unsplash License" |
| `created_at` | timestamp | |
 
### `image_metadata`
The validated vision output, one row per successfully tagged image.
 
| Column | Type | Notes |
|---|---|---|
| `id` | PK | |
| `image_id` | FK → images | |
| `category` | enum | constrained vocabulary, see section 1 in this file |
| `subject` | enum | constrained vocabulary, see section 1 in this file |
| `attributes` | text[] | free text |
| `caption` | text | free text |
| `confidence` | float | 0.0–1.0 |
| `needs_review` | bool | derived: `confidence < threshold`, not model output |
| `model_name` | text | e.g. `gemini-flash` |
| `model_version` | text | for reproducibility if re-tagging later |
| `raw_response` | jsonb (nullable) | untouched model response, kept for debugging failed validations |
| `created_at` | timestamp | |
 
### `image_vectors`
Separate from `image_metadata` per the architecture diagram — matching logic
only needs this table, not the full tag row.
 
| Column | Type | Notes |
|---|---|---|
| `id` | PK | |
| `image_id` | FK → images | |
| `embedding` | float[] / vector | embedding of `caption` |
| `model_name` | text | which embedding model produced it |
| `created_at` | timestamp | |
 
### `post_vectors`
Mirrors `image_vectors` for blog post content.
 
| Column | Type | Notes |
|---|---|---|
| `id` | PK | |
| `post_id` | FK → posts | |
| `embedding` | float[] / vector | embedding of post text |
| `model_name` | text | |
| `created_at` | timestamp | |
 
### `ai_call_log`
Cost tracking lives here, not on `image_metadata` — a single image can
generate multiple vision calls across retries, so cost is a 1-to-many
relationship that doesn't fit as a column on the metadata row.
 
| Column | Type | Notes |
|---|---|---|
| `id` | PK | |
| `image_id` | FK → images (nullable) | null for post-embedding calls |
| `call_type` | enum | `vision` \| `embedding` |
| `status` | enum | `success` \| `retry` \| `failed` |
| `cost_usd` | float | |
| `tokens` | int (nullable) | |
| `created_at` | timestamp | |
 
### `suggestions` (review workflow, per §4.5)
 
| Column | Type | Notes |
|---|---|---|
| `id` | PK | |
| `post_id` | FK → posts | |
| `image_id` | FK → images | |
| `similarity_score` | float | |
| `guard_result` | enum | `accepted` \| `rejected` \| `no_confident_match` |
| `guard_reason` | text | human-readable explanation |
| `review_status` | enum | `pending` \| `approved` \| `rejected` |
| `created_at` | timestamp | |