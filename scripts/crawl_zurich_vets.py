"""Collect a bounded Zurich clinic snapshot; no keys, AI calls or website crawling."""
import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pawse.crawling import CrawlError, collect  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--radius-km", type=int, default=10)
    parser.add_argument("--output", type=Path, default=ROOT / "tmp/crawling/zurich-vets.json")
    parser.add_argument("--refresh", action="store_true", help="explicitly replace an existing snapshot")
    args = parser.parse_args()
    if args.output.exists() and not args.refresh:
        parser.error("Snapshot exists; reuse it, or pass --refresh for an intentional network refresh.")
    try:
        result = asyncio.run(collect(args.radius_km))
    except CrawlError as exc:
        parser.exit(1, f"{exc}\n")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(args.output)
    print(f"Saved {len(result['clinics'])} community clinic listings to {args.output}")
    print("Hours, contacts and appointments require verification. Attribution: © OpenStreetMap contributors (ODbL).")


if __name__ == "__main__":
    main()
