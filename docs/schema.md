# Schema Doc — AI Image Understanding & Content Matching Engine

Document that details design decisions for image metadata and database schemas.

## 1. Image tag schema — the vision model's output contract

This is the schema referenced in §4 and §8 of the brief ("the tag JSON
above"). It is the **validated shape of a single Gemini Flash response** for
one image — not the database table. See §2 below for how it's persisted.

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

- **`category`** — closed vocabulary (Pydantic `Literal` / `Enum`), the
  broad domain an image belongs to — e.g. `animal`, `plant`, `vehicle`,
  `furniture`. Since the corpus can span multiple domains, this is a real
  coarse filter: it catches a wildly wrong candidate (a furniture photo
  surfacing on a plant post) before the guard ever looks at species-level
  detail. Small, fixed list where each image must only be assigned one item from it. List of categories: [animal|plant|vehicle|clothing|furniture|beverage|electronic device].
- **`subject`** — closed vocabulary (Pydantic `Literal` / `Enum`), the
  specific item within that category — e.g. `red fox`, `wolf`, `oak tree`,
  `sedan`. Each `subject` belongs to exactly one `category`. This is the
  fine-grained field the mismatch guard depends on for exact comparison
  ("expected fox, detected wolf") — two candidates can share the same
  `category` (`animal`) and still need to be told apart, which `category`
  alone can't do. Each image must be assigned only one item from the `subject` list which is the following: [bamboo|bed|belt|boat|bookshelf|bus|bush|cabinet|cactus|camera|car|cat|chair|coffee|deer|desk|flower|gaming console|gloves|grass|hat|headphones|horse|jacket|juice|laptop|microphone|milk|motorcycle|owl|pants|phone|plane|printer|red fox|shoes|smoothie|soda|sofa|squirrel|stool|t-shirt|tea|tiger|train|tree|truck|water|wheat|wolf]
- **`attributes`** — free-text, list of strings. This only feeds the
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
| `image_data` | BLOB | raw bytes, in-DB storage per decision in task.md |
| `filename` | text | original filename |
| `author` | text | photographer credit, from Unsplash/Pexels |
| `source_url` | text | Unsplash/Pexels source, for license traceability |
| `license` | text | e.g. "Unsplash License" |
| `created_at` | timestamp | |

### Corpus storage (pre-ingestion)

Before the seed script loads anything into the DB, the raw corpus lives in
the repo as plain files, per §3/§11's reproducibility rules:

- `data/images/` — the actual image files, renamed to stable slugs
  (`fox.jpg`) as they're downloaded. Kept under a few MB total by using
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
| `category` | enum | constrained vocabulary, see §1 — broad domain |
| `subject` | enum | constrained vocabulary, see §1 — specific item within category |
| `attributes` | json | list of free-text strings; SQLite has no native array type |
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
| `embedding` | json | list of floats; embedding of `caption`. Cosine similarity computed in Python — no `pgvector`/vector column needed at ~50 rows |
| `model_name` | text | which embedding model produced it |
| `created_at` | timestamp | |

### `post_vectors`
Mirrors `image_vectors` for blog post content.

| Column | Type | Notes |
|---|---|---|
| `id` | PK | |
| `post_id` | FK → posts | |
| `embedding` | json | list of floats; embedding of post text |
| `model_name` | text | |
| `created_at` | timestamp | |

### `ai_call_log`
Cost tracking lives here, not on `image_metadata` — a single image can
generate multiple vision calls across retries, so cost is a 1-to-many
relationship that doesn't fit as a column on the metadata row. Built in
Phase 2 — this table already exists (`src/db/models.py`, migration `0001`).

| Column | Type | Notes |
|---|---|---|
| `id` | PK | |
| `image_id` | int (nullable) | null for post-embedding calls |
| `call_type` | text | `vision` \| `embedding` |
| `status` | text | `success` \| `retry` \| `failed` |
| `model_name` | text (nullable) | e.g. `gemini-3.7-flash` |
| `model_version` | text (nullable) | |
| `input_tokens` | int | default 0 |
| `output_tokens` | int | default 0 |
| `total_tokens` | int | default 0 |
| `duration_ms` | int | default 0 |
| `retry_count` | int | default 0 |
| `cost_usd` | float | default 0.0 |
| `meta` | json (nullable) | free-form extra context per call |
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
| `image_metadata` | `category` | guard's category gate filters by this |
| `image_metadata` | `subject` | guard's subject gate filters by this |
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

### Migrations

**Documented decision:** SQLAlchemy models + Alembic migrations, regardless
of engine. This is what makes "schema as migrations" (§12 shared
requirement #4) true from day one, and it's also what makes swapping
SQLite → Postgres later a config change rather than a rewrite — directly
serving the Architecture rubric dimension ("swap the DB... without
touching business logic").

 `migrations/env.py` reads
`DATABASE_URL` from `.env` via `python-dotenv` and points
`target_metadata` at `Base.metadata` (`src/db/models.py`), so every
migration is autogenerated from the models instead of hand-written SQL.
The old hand-written SQL and `scripts/init_db.py`/`create_all()` path have
been retired — there is exactly one way to create tables now.

Revision history:
- `a97d1eb44701` — `create ai_call_log`.
- `205804495510` — `images`, `posts`, `image_metadata`, `image_vectors`,
  `post_vectors`, plus the previously-outstanding `ai_call_log` indexes
  (`image_id`, `created_at`). Autogenerate also emitted the indexes from
  the indexes table below for the new tables.

The "one row per image/post" invariants are enforced with unique
constraints (`uq_image_metadata_image_id`, `uq_image_vectors_image_id`,
`uq_post_vectors_post_id`) so re-seeding/re-embedding updates rows instead
of duplicating them.

Outstanding: the `suggestions` table (and its three indexes) will land as
its own revision when the review/guard workflow is implemented.

Workflow: add a model → `alembic revision --autogenerate -m "..."` +
`alembic upgrade head`. Rebuild from nothing:
`rm data/dev.db && alembic upgrade head`.
 