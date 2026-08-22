"""DoD §6 Matching system #1b: posts return ranked suggestions over HTTP.

Run: py evidence/http_ranked_suggestions.py   (server must be up:
     fastapi dev src/api/main.py)

Hits GET /posts/1/images exactly like a client would and prints the ranked
candidates with their guard verdicts.
"""
import json
import sys
import urllib.error
import urllib.request

URL = "http://127.0.0.1:8000/posts/1/images"


def main() -> None:
    try:
        with urllib.request.urlopen(URL, timeout=5) as resp:
            body = json.load(resp)
    except urllib.error.URLError as exc:
        print(f"Cannot reach {URL} - is the server running? ({exc.reason})")
        sys.exit(1)

    print(f'{body["post_id"]} "{body["title"]}" -> result={body["result"]}')
    for i, row in enumerate(body["ranked"], 1):
        print(f"  {i}. {row['filename']:<14} subject={row['subject']:<10} "
              f"similarity={row['similarity']:.4f} guard={row['guard']}")
    suggestion = body["suggestion"]
    if suggestion:
        print(f'suggestion: {suggestion["filename"]} ({suggestion["subject"]})')


if __name__ == "__main__":
    main()