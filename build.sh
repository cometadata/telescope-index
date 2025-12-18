#!/bin/bash
# Build data files from DataCite JSONL input
#
# Usage:
#   ./build.sh                           # Uses default ./input directory
#   ./build.sh /path/to/input/dir        # Custom input directory
#
# Input directory should contain:
#   - *.jsonl (works data in DataCite format)
#   - *ror-data*.json (ROR data)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

INPUT_DIR="${1:-./input}"
OUTPUT_DIR="./output"

if [ ! -d "$INPUT_DIR" ]; then
    echo "Error: Input directory not found: $INPUT_DIR"
    exit 1
fi

echo "Building data from: $INPUT_DIR"
echo "Output directory: $OUTPUT_DIR"
echo ""

uv run build-data.py "$INPUT_DIR" "$OUTPUT_DIR"

echo ""
echo "Build complete. Output files:"
ls -lh "$OUTPUT_DIR"/*.jsonl 2>/dev/null || true
