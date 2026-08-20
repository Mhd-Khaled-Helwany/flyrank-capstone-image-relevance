from __future__ import annotations
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from db.session import make_session_factory
from matching.guard import suggest_for_post
from matching.ranking import rank_images_for_post
from matching.repository import list_posts

LABELS_PATH = ROOT / "data" / "posts.csv"

def load_labels() -> dict[str, dict]:
    """title -> {expected_subject, expected_result} from data/posts.csv.
    """
    with open(LABELS_PATH, newline="", encoding="utf-8") as f:
        return {row["title"]: row for row in csv.DictReader(f)}

def evaluate(session) -> dict:
    """Measure retrieval precision and guard accuracy against the labels."""
    labels = load_labels()
    details = []
    top1_total = 0
    top1_hits = 0
    guard_total = 0
    guard_hits = 0

    for post in list_posts(session):
        label = labels.get(post.title)
        if label is None:
            continue
        expected_subject = label["expected_subject"] or None
        expected_result = label["expected_result"]

        top1 = rank_images_for_post(session, post.id, limit=1)
        top1_subject = top1[0]["subject"] if top1 else None

        if expected_subject:
            top1_total += 1
            if top1_subject == expected_subject:
                top1_hits += 1

        suggestion = suggest_for_post(session, post)
        if expected_result == "accepted":
            guard_ok = (
                suggestion["result"] == "accepted"
                and suggestion["image"] is not None
                and suggestion["image"]["subject"] == expected_subject
            )
            suggestion_subject = (
                suggestion["image"]["subject"] if suggestion["image"] else None
            )
        else:
            guard_ok = suggestion["result"] == "no_confident_match"
            suggestion_subject = None

        guard_total += 1
        if guard_ok:
            guard_hits += 1

        details.append(
            {
                "post_id": post.id,
                "title": post.title,
                "expected_subject": expected_subject,
                "expected_result": expected_result,
                "top1_subject": top1_subject,
                "suggestion_subject": suggestion_subject,
                "guard": "ok" if guard_ok else "MISS",
            }
        )

    return {
        "details": details,
        "top1_precision": top1_hits / top1_total if top1_total else 0.0,
        "top1_hits": top1_hits,
        "top1_total": top1_total,
        "guard_precision": guard_hits / guard_total if guard_total else 0.0,
        "guard_hits": guard_hits,
        "guard_total": guard_total,
    }

def main() -> int:
    with make_session_factory()() as session:
        result = evaluate(session)

    print(f"{'post':<5} {'title':<40} {'top-1 subject':<16} {'expected':<12} {'suggestion':<12} guard")
    for row in result["details"]:
        print(
            f"{row['post_id']:<5} {row['title'][:38]:<40} "
            f"{str(row['top1_subject'] or '-'):<16} "
            f"{str(row['expected_subject'] or 'n/a'):<12} "
            f"{str(row['suggestion_subject'] or '-'):<12} {row['guard']}"
        )

    print()
    print(
        f"Top-1 precision: {result['top1_hits']}/{result['top1_total']} "
        f"= {result['top1_precision']:.1%}"
    )
    print(
        f"Guard suggestion precision: {result['guard_hits']}/{result['guard_total']} "
        f"= {result['guard_precision']:.1%}"
    )
    return 0

if __name__ == "__main__":
    sys.exit(main())