"""Small script to validate the sample vision JSON using the processor module."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vision.processor import validate_from_json_file

def main():
    sample = ROOT / "data" / "sample_tag.json"
    result = validate_from_json_file(str(sample))
    print(result)

if __name__ == "__main__":
    main()
