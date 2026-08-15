# Schema Doc — AI Image Understanding & Content Matching Engine

Document that details design decisions for image metadata and database schemas.

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
| `author` | text | photographer credit, from Unsplash/Pexels |
| `source_url` | text | Unsplash/Pexels source, for license traceability |
| `license` | text | e.g. "Unsplash License" |
| `created_at` | timestamp | |
 
### Corpus storage (pre-ingestion)
 
Before the seed script loads anything into the DB, the raw corpus lives in
the repo as plain files, per §3/§11's reproducibility rules:
 
- `data/images/` — the actual image files, renamed to stable slugs
  (`fox_01.jpg`) as they're downloaded. Kept under a few MB total by using
  Unsplash/Pexels' "regular"/"small" download size, not full resolution
  (§11: don't commit datasets over a few MB).
- `data/manifest.csv` — one row per image: `filename, author, source_url,
  license`. This is the reproducibility artifact itself, and the seed
  script's input for populating the `images` table.
### `posts`
One row per blog post — the other half of the matching problem. Not
explicitly listed in §4's five parts, but required by §6's Definition of
Done ("database models for... posts") and by `post_vectors`' FK below.
 
| Column | Type | Notes |
|---|---|---|
| `id` | PK | |
| `title` | text | |
| `body` | text | full post content — this is what gets embedded |
| `created_at` | timestamp | |

### `image_metadata`
The validated vision output, one row per successfully tagged image.
 
| Column | Type | Notes |
|---|---|---|
| `id` | PK | |
| `image_id` | FK → images | |
| `category` | enum | constrained vocabulary, see section 1 in this file |
| `subject` | enum | constrained vocabulary, see section 1 in this file |
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

### Indexes
 
§6's Definition of Done explicitly calls for "the required indexes," so
these are part of the schema, not an afterthought:
 
| Table | Index | Why |
|---|---|---|
| `image_metadata` | `image_id` (FK) | join back to `images` |
| `image_metadata` | `category` | guard's category-match gate filters by this |
| `image_vectors` | `image_id` (FK) | join back to `images` during ranking |
| `post_vectors` | `post_id` (FK) | join back to `posts` |
| `ai_call_log` | `image_id` (FK) | cost lookups per image |
| `ai_call_log` | `created_at` | Probe 6 — cost log needs to be scanned/reported |
| `suggestions` | `post_id` (FK) | `GET /posts/:id/images` looks these up |
| `suggestions` | `image_id` (FK) | review API looks up by image too |
| `suggestions` | `review_status` | review workflow queries pending items |
 
### Constraints
 
- **`suggestions.(post_id, image_id)` is unique.** Re-running the guard on
  the same pair (e.g. re-ranking after new images are tagged) should update
  the existing row, not create a duplicate. This also directly supports
  Probe 3's "force this specific candidate" check being idempotent.
- **`ON DELETE CASCADE`** from `images` → `image_metadata`, `image_vectors`,
  and `suggestions`; from `posts` → `post_vectors` and `suggestions`. Deleting
  an image or post shouldn't leave orphaned rows behind.
