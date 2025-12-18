#!/bin/bash
# Index documents to Typesense Cloud
#
# Usage:
#   ./index.sh                          # Index both works and institutions
#   ./index.sh works                    # Index only works
#   ./index.sh institutions             # Index only institutions
#   ./index.sh --recreate               # Recreate both collections
#   ./index.sh works --recreate         # Recreate works collection
#   ./index.sh institutions --recreate  # Recreate institutions collection
#
# Environment:
#   Reads TYPESENSE_HOST and TYPESENSE_API_KEY from ../.env.local

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Load environment variables from .env.local
ENV_FILE="../.env.local"
if [ -f "$ENV_FILE" ]; then
    set -a
    source "$ENV_FILE"
    set +a
else
    echo "Warning: $ENV_FILE not found"
fi

# Check required environment variables
if [ -z "$TYPESENSE_HOST" ] || [ -z "$TYPESENSE_API_KEY" ]; then
    echo "Error: TYPESENSE_HOST and TYPESENSE_API_KEY must be set"
    echo "Either set them in $ENV_FILE or export them"
    exit 1
fi

OUTPUT_DIR="./output"
EXTRA_ARGS=""

# Parse arguments
COLLECTION="all"
for arg in "$@"; do
    case "$arg" in
        works|institutions|all)
            COLLECTION="$arg"
            ;;
        --recreate)
            EXTRA_ARGS="--recreate"
            ;;
    esac
done

index_works() {
    local works_file="$OUTPUT_DIR/typesense-documents.jsonl"
    if [ ! -f "$works_file" ]; then
        echo "Error: Works file not found: $works_file"
        echo "Run ./build.sh first"
        exit 1
    fi
    echo "Indexing works collection..."
    uv run index-typesense.py --collection works $EXTRA_ARGS "$works_file"
}

index_institutions() {
    local inst_file="$OUTPUT_DIR/typesense-institutions.jsonl"
    if [ ! -f "$inst_file" ]; then
        echo "Error: Institutions file not found: $inst_file"
        echo "Run ./build.sh first"
        exit 1
    fi
    echo "Indexing institutions collection..."
    uv run index-typesense.py --collection institutions $EXTRA_ARGS "$inst_file"
}

case "$COLLECTION" in
    works)
        index_works
        ;;
    institutions)
        index_institutions
        ;;
    all)
        index_works
        echo ""
        index_institutions
        ;;
    *)
        echo "Unknown collection: $COLLECTION"
        echo "Usage: ./index.sh [works|institutions|all] [--recreate]"
        exit 1
        ;;
esac

echo ""
echo "Indexing complete!"
