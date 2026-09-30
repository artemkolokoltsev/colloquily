from __future__ import annotations

import argparse
import json
import os
import sys


ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from services.index_builder import build_profile_index
from services.index_profiles import load_index_profiles
from services.preprocessing_cache import load_or_extract_pages


def main() -> None:
    parser = argparse.ArgumentParser(description="Build prepared FAISS indexes for configured retrieval profiles.")
    parser.add_argument("--profile", help="Only build one profile by name.")
    parser.add_argument("--force", action="store_true", help="Rebuild existing indexes.")
    parser.add_argument("--force-extract", action="store_true", help="Re-extract PDF text cache before building.")
    args = parser.parse_args()

    load_or_extract_pages(force=args.force_extract)
    profiles = load_index_profiles()
    if args.profile:
        profiles = [profile for profile in profiles if profile.get("name") == args.profile]
        if not profiles:
            raise SystemExit(f"Unknown index profile: {args.profile}")

    results = []
    for profile in profiles:
        results.append(build_profile_index(profile, force=args.force))
        print(json.dumps(results[-1], ensure_ascii=False))
    print(json.dumps({"profiles": len(results), "results": results}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
