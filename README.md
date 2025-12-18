# Telescope Index

Python data pipeline for building and indexing arXiv works to Typesense for use in the [Telescope UI](https://github.com/cometadata/telescope-ui).

## Setup

Requires Python 3.11+ and [uv](https://github.com/astral-sh/uv).

```bash
uv sync
```

## Environment Variables

Create `.env.local` with:

```
TYPESENSE_HOST=your-host.a1.typesense.net
TYPESENSE_API_KEY=your-admin-api-key
```

## Usage

### Build Data

Convert DataCite JSONL to Typesense format:

```bash
./build.sh /path/to/input.jsonl
# Or with custom output:
uv run build-data.py /path/to/input.jsonl /path/to/output
```

Outputs:
- `output/typesense-documents.jsonl` - Works collection
- `output/typesense-institutions.jsonl` - Institutions collection
- `output/stats/*.json` - Statistics for UI

### Index to Typesense

Upload JSONL to Typesense Cloud:

```bash
./index.sh                          # Index both collections
./index.sh --recreate               # Recreate collections from scratch
./index.sh works                    # Index only works
./index.sh institutions --recreate  # Recreate institutions only
```

## After Indexing

Copy stats files to telescope-ui:

```bash
cp -r output/stats/* /path/to/telescope-ui/public/data/stats/
```
