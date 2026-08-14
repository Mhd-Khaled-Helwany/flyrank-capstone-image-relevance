# Matching Doc — AI Image Understanding & Content Matching Engine

Document that details design decisions for matching strategy and guard rules.

## 1. Matching strategy
 
Per §4.2 and the glossary, ranking uses **cosine similarity** between
`image_vectors` and a post's `post_vectors` entry — this is fixed by the
brief, not a choice. Both are embedded with the Gemini embeddings API using
the `SEMANTIC_SIMILARITY` task type, so captions and post text land in a
comparable space (the brief's own test: "red fox," "Vulpes vulpes," and
"wild fox species" must rank close despite sharing no words).
 
Flow for `GET /posts/:id/images`:
 
1. Embed the post text (or reuse the stored `post_vectors` row).
2. Rank all images by cosine similarity against that vector — highest first.
3. Walk down the ranked list, evaluating each candidate against the guard
    in order, until one **passes** or the top 5 candidates have all been
   rejected.
4. First passing candidate → suggested image, with its similarity score and
   the guard's reasoning attached.
5. If nothing in the top 5 passes → post-level answer is `no_confident_match`
   , never a forced weak top-1.
Capping the walk at the top 5 keeps this cheap at ~50 images while still
giving the guard a real chance to skip past a wrongly-ranked outlier (the
Probe 3 scenario), rather than only ever judging the single top-ranked
candidate.
 
## 2. Mismatch guard rules
 
Per §4.3, the guard combines tag validation, similarity threshold, and
confidence into a single per-candidate check. It's a pure function —
`evaluate_candidate(post, image) → {result, reason}` — reused both during
the ranking walk and by the review API's "inspect why an image was
selected or refused" endpoint (§4.5), so the explanation logic only lives
in one place.
 
Three gates, checked in order, first failure wins:
 
1. **Category match.** Extract the set of categories mentioned in the post
   text via a keyword scan against the known category enum (case-insensitive
   substring match, e.g. does "fox" appear in the post?). If the candidate's
   `category` is not in that set → `REJECTED`, reason:
   `"Category mismatch: expected {post categories}, detected {candidate
   category}"`. This is the exact fox/wolf scenario from §4.3 and Probe 3.
   - If the post text contains **no** recognized category keyword at all,
     the expected set is empty and every candidate fails this gate by
     definition — that post can never produce an `accepted` suggestion,
     only `no_confident_match`.
2. **Tag confidence.** If the candidate's `confidence` is below the
   `needs_review` threshold (§7, TBD from eval data), it's untrusted data
   and shouldn't be surfaced regardless of category match → `REJECTED`,
   reason: `"Tag confidence too low to trust"`.
3. **Similarity threshold.** If cosine similarity is below the tuned
   threshold (§7, TBD from eval data) → `REJECTED`, reason:
   `"Similarity below threshold"`.
4. All three gates pass → `ACCEPTED`.
**Post-level aggregation** (what the API actually returns for
`GET /posts/:id/images`):
 
- First candidate in the ranked walk that gets `ACCEPTED` → returned as the
  suggestion.
- If every candidate in the top 5 is `REJECTED` → the post-level result is
  `no_confident_match`, per §4.3 and Probe 4 — this covers both failure
  modes the brief names explicitly: **"subjects don't match"** (all
  candidates failed gate 1) and **"similarity below threshold"** (best
  candidate passed gates 1–2 but failed gate 3). The reason surfaced to the
  post is drawn from the top-ranked candidate's specific rejection reason,
  since that candidate is the closest the system got.
- A single forced candidate (Probe 3's scenario) still returns its own
  `REJECTED` result directly from `evaluate_candidate` — the review API can
  call this on any specific (post, image) pair without going through the
  full ranking walk.