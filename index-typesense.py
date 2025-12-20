#!/usr/bin/env python3
"""
Index documents to Typesense Cloud.

Usage:
    uv run index-typesense.py /path/to/typesense-documents.jsonl

Environment variables:
    TYPESENSE_HOST - Typesense Cloud host (e.g., xxx.a1.typesense.net)
    TYPESENSE_API_KEY - Admin API key
"""

import argparse
import gc
import json
import os
import sys
from pathlib import Path

import typesense
from tqdm import tqdm


def get_client():
    host = os.environ.get("TYPESENSE_HOST")
    api_key = os.environ.get("TYPESENSE_API_KEY")

    if not host or not api_key:
        print("Error: TYPESENSE_HOST and TYPESENSE_API_KEY must be set", file=sys.stderr)
        sys.exit(1)

    return typesense.Client({
        "nodes": [{
            "host": host,
            "port": "443",
            "protocol": "https"
        }],
        "api_key": api_key,
        "connection_timeout_seconds": 60
    })


WORKS_SCHEMA = {
    "name": "works",
    "fields": [
        {"name": "id", "type": "string"},
        {"name": "doi", "type": "string"},
        {"name": "arxiv_id", "type": "string"},
        {"name": "arxiv_id_link", "type": "string"},
        {"name": "title", "type": "string"},
        {"name": "year", "type": "int32", "facet": True},
        {"name": "authors", "type": "string[]"},
        {"name": "affiliations", "type": "string[]"},
        {"name": "ror_ids", "type": "string[]", "facet": True},
        {"name": "institution_names", "type": "string[]"},
        {"name": "searchable_names", "type": "string[]"},
        {"name": "countries", "type": "string[]", "facet": True},
        {"name": "subjects", "type": "string[]"},
        {"name": "subject_codes", "type": "string[]", "facet": True},
        {"name": "publication_link", "type": "string", "optional": True},
        {"name": "has_publication", "type": "bool", "facet": True},
        {"name": "author_affiliations", "type": "string", "index": False},
        {"name": "software_repository", "type": "string", "optional": True},
        {"name": "software_references", "type": "string[]", "optional": True},
        {"name": "has_software", "type": "bool", "facet": True},
    ],
    "default_sorting_field": "year",
}

INSTITUTIONS_SCHEMA = {
    "name": "institutions",
    "fields": [
        {"name": "id", "type": "string"},
        {"name": "ror_id", "type": "string"},
        {"name": "name", "type": "string"},
        {"name": "acronyms", "type": "string[]"},
        {"name": "aliases", "type": "string[]"},
        {"name": "labels", "type": "string[]"},
        {"name": "country", "type": "string", "facet": True},
        {"name": "country_code", "type": "string"},
        {"name": "city", "type": "string"},
        {"name": "types", "type": "string[]", "facet": True},
        {"name": "subject_codes", "type": "string[]", "facet": True},
        {"name": "work_count", "type": "int32"},
        {"name": "time_series", "type": "string", "index": False},
        {"name": "top_collaborators", "type": "string", "index": False},
        {"name": "top_subjects", "type": "string", "index": False},
        {"name": "links", "type": "string", "index": False},
        {"name": "locations", "type": "string", "index": False},
    ],
    "default_sorting_field": "work_count",
}

SCHEMAS = {
    "works": WORKS_SCHEMA,
    "institutions": INSTITUTIONS_SCHEMA,
}


def count_lines(filepath: Path) -> int:
    count = 0
    with open(filepath, "rb") as f:
        buf_size = 1024 * 1024
        buf = f.raw.read(buf_size)
        while buf:
            count += buf.count(b'\n')
            buf = f.raw.read(buf_size)
    return count


def import_batch(client, collection_name: str, docs: list[str]) -> tuple[int, int, list[str]]:
    imported = 0
    errors = 0
    error_msgs = []

    try:
        jsonl_str = "\n".join(docs)
        result = client.collections[collection_name].documents.import_(
            jsonl_str,
            {"action": "upsert"}
        )

        docs.clear()
        del jsonl_str

        if isinstance(result, str):
            start = 0
            while True:
                end = result.find('\n', start)
                if end == -1:
                    line = result[start:].strip()
                    if line:
                        r = json.loads(line)
                        if r.get("success"):
                            imported += 1
                        else:
                            errors += 1
                            if len(error_msgs) < 5:
                                error_msgs.append(r.get('error', 'unknown'))
                    break
                else:
                    line = result[start:end].strip()
                    if line:
                        r = json.loads(line)
                        if r.get("success"):
                            imported += 1
                        else:
                            errors += 1
                            if len(error_msgs) < 5:
                                error_msgs.append(r.get('error', 'unknown'))
                    start = end + 1
            del result
        else:
            for r in result:
                if r.get("success"):
                    imported += 1
                else:
                    errors += 1
            del result

    except Exception as e:
        error_msgs.append(str(e))
        errors = len(docs)
        docs.clear()

    return imported, errors, error_msgs


def main():
    parser = argparse.ArgumentParser(description="Index documents to Typesense")
    parser.add_argument("jsonl_file", type=Path, help="Path to JSONL file")
    parser.add_argument("--collection", choices=["works", "institutions"], default="works",
                        help="Collection to index (default: works)")
    parser.add_argument("--recreate", action="store_true", help="Drop and recreate collection")
    parser.add_argument("--batch-size", type=int, default=50, help="Batch size for imports (default: 50)")
    parser.add_argument("--skip", type=int, default=0, help="Skip first N documents (for resuming)")
    parser.add_argument("--limit", type=int, default=0, help="Only import N documents (0 = all)")
    args = parser.parse_args()

    collection_name = args.collection
    schema = SCHEMAS[collection_name]

    if not args.jsonl_file.exists():
        print(f"Error: File not found: {args.jsonl_file}", file=sys.stderr)
        sys.exit(1)

    client = get_client()

    print(f"Collection: {collection_name}")

    try:
        existing = client.collections[collection_name].retrieve()
        if args.recreate:
            print("Dropping existing collection...")
            client.collections[collection_name].delete()
            print("Creating new collection...")
            client.collections.create(schema)
        else:
            print(f"Using existing collection with {existing['num_documents']} documents")
    except typesense.exceptions.ObjectNotFound:
        print("Creating new collection...")
        client.collections.create(schema)

    print(f"Counting documents in {args.jsonl_file.name}...")
    total = count_lines(args.jsonl_file)
    print(f"Found {total:,} documents")

    if args.skip:
        print(f"Skipping first {args.skip:,} documents")
        total = total - args.skip
    if args.limit:
        total = min(total, args.limit)
        print(f"Limiting to {args.limit:,} documents")

    print(f"Importing documents (batch size: {args.batch_size})...")
    batch = []
    total_imported = 0
    total_errors = 0
    line_num = 0
    gc_counter = 0

    with open(args.jsonl_file, "r") as f:
        pbar = tqdm(total=total, desc="Importing")

        for line in f:
            line_num += 1

            if line_num <= args.skip:
                continue

            if args.limit and (line_num - args.skip) > args.limit:
                break

            stripped = line.strip()
            if stripped:
                batch.append(stripped)

            if len(batch) >= args.batch_size:
                imported, errors, error_msgs = import_batch(client, collection_name, batch)
                total_imported += imported
                total_errors += errors

                for msg in error_msgs:
                    print(f"\nError: {msg}", file=sys.stderr)

                pbar.update(imported + errors)
                batch = []

                gc_counter += 1
                if gc_counter % 20 == 0:
                    gc.collect()

        if batch:
            imported, errors, error_msgs = import_batch(client, collection_name, batch)
            total_imported += imported
            total_errors += errors
            for msg in error_msgs:
                print(f"\nError: {msg}", file=sys.stderr)
            pbar.update(imported + errors)

        pbar.close()

    print(f"\nDone!")
    print(f"  Imported: {total_imported:,}")
    print(f"  Errors: {total_errors:,}")

    gc.collect()
    collection = client.collections[collection_name].retrieve()
    print(f"  Total in collection: {collection['num_documents']:,}")


if __name__ == "__main__":
    main()
