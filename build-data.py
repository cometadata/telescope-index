#!/usr/bin/env python3
"""
Build script for the Telescope UI.

Usage:
    uv run build-data.py /path/to/input/dir /path/to/output/dir

Input directory should contain:
    - *.jsonl (works data in DataCite format)
    - *ror-data*.json (ROR data)
"""

import re
import sys
import ijson
import orjson
import argparse
from pathlib import Path
from decimal import Decimal
from collections import defaultdict
from datetime import datetime, timezone

from tqdm import tqdm

from extractors import SoftwareExtractor


def convert_decimals(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    elif isinstance(obj, dict):
        return {k: convert_decimals(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_decimals(item) for item in obj]
    return obj


def find_files(input_dir: Path) -> tuple[Path, Path]:
    works_file = None
    ror_file = None

    for f in input_dir.iterdir():
        # JSONL files = DataCite works data
        if f.suffix == ".jsonl":
            works_file = f
        # JSON files = ROR data
        elif f.suffix == ".json":
            name_lower = f.name.lower()
            if "ror" in name_lower and "data" in name_lower:
                ror_file = f

    if not works_file:
        raise FileNotFoundError("Could not find works JSONL file in input directory")
    if not ror_file:
        raise FileNotFoundError("Could not find ROR data file in input directory")

    return works_file, ror_file


def count_lines(filepath: Path) -> int:
    count = 0
    with open(filepath, "rb") as f:
        for _ in f:
            count += 1
    return count


def extract_arxiv_id(record: dict) -> str:
    attrs = record.get("attributes", {})
    for ident in attrs.get("identifiers", []):
        if ident.get("identifierType") == "arXiv":
            return ident.get("identifier", "")
    for ident in attrs.get("alternateIdentifiers", []):
        if ident.get("alternateIdentifierType") == "arXiv":
            return ident.get("alternateIdentifier", "")
    return ""


def extract_arxiv_id_link(record: dict) -> str:
    return record.get("attributes", {}).get("url", "")


def extract_doi(record: dict) -> str:
    return record.get("attributes", {}).get("doi", "")


def extract_title(record: dict) -> str:
    titles = record.get("attributes", {}).get("titles", [])
    if titles:
        return titles[0].get("title", "")
    return ""


def extract_year_datacite(record: dict) -> int | None:
    dates = record.get("attributes", {}).get("dates", [])
    for d in dates:
        if d.get("dateType") == "Submitted":
            date_str = d.get("date", "")
            match = re.match(r"(\d{4})", date_str)
            if match:
                return int(match.group(1))
    return None


def parse_arxiv_subject(subject_str: str) -> tuple[str, str]:
    match = re.match(r"(.+?)\s*\(([^)]+)\)$", subject_str)
    if match:
        return match.group(1).strip(), match.group(2).strip()
    return subject_str, ""


def extract_subjects_datacite(record: dict) -> tuple[list[str], list[str]]:
    subjects = []
    subject_codes = []
    for subj in record.get("attributes", {}).get("subjects", []):
        if subj.get("subjectScheme") == "arXiv":
            subject_str = subj.get("subject", "")
            name, code = parse_arxiv_subject(subject_str)
            if name:
                subjects.append(name)
            if code:
                subject_codes.append(code)
    return subjects, subject_codes


def extract_publication_link(record: dict) -> str:
    related = record.get("attributes", {}).get("relatedIdentifiers", [])
    for rel in related:
        if rel.get("relationType") == "IsVersionOf" and rel.get("relatedIdentifierType") == "DOI":
            doi = rel.get("relatedIdentifier", "")
            if doi:
                return f"https://doi.org/{doi}"
    return ""


def get_ror_id_hash(ror_id: str) -> str:
    return ror_id.replace("https://ror.org/", "")


def get_display_name(ror_record: dict) -> str:
    for name in ror_record.get("names", []):
        if "ror_display" in name.get("types", []):
            return name.get("value", "")
    names = ror_record.get("names", [])
    return names[0].get("value", "") if names else ""


def get_all_names(ror_record: dict) -> dict:
    result = {
        "aliases": [],
        "acronyms": [],
        "labels": []
    }
    for name in ror_record.get("names", []):
        value = name.get("value", "")
        if not value:
            continue
        types = name.get("types", [])
        if "ror_display" in types:
            continue
        if "acronym" in types:
            result["acronyms"].append(value)
        elif "alias" in types:
            result["aliases"].append(value)
        elif "label" in types:
            result["labels"].append(value)
    return result


def get_country(ror_record: dict) -> str:
    locations = ror_record.get("locations", [])
    if locations:
        return locations[0].get("geonames_details", {}).get("country_name", "Unknown")
    return "Unknown"


def get_country_code(ror_record: dict) -> str:
    locations = ror_record.get("locations", [])
    if locations:
        return locations[0].get("geonames_details", {}).get("country_code", "")
    return ""


def get_city(ror_record: dict) -> str:
    locations = ror_record.get("locations", [])
    if locations:
        return locations[0].get("geonames_details", {}).get("name", "")
    return ""


def load_ror_lookup(ror_file: Path) -> dict:
    print(f"Loading ROR data from {ror_file.name}...")
    lookup = {}
    with open(ror_file, "rb") as f:
        for record in tqdm(ijson.items(f, "item"), desc="Loading ROR"):
            ror_id = record.get("id")
            if ror_id:
                lookup[ror_id] = record
    print(f"Loaded {len(lookup)} ROR records")
    return lookup


def write_json(path: Path, data):
    with open(path, "wb") as f:
        f.write(orjson.dumps(convert_decimals(data), option=orjson.OPT_INDENT_2))


def main():
    parser = argparse.ArgumentParser(description="Build data for arXiv Explorer")
    parser.add_argument("input_dir", type=Path, help="Directory containing source JSON files")
    parser.add_argument("output_dir", type=Path, help="Directory for output files")
    args = parser.parse_args()

    input_dir = args.input_dir.resolve()
    output_dir = args.output_dir.resolve()

    if not input_dir.is_dir():
        print(f"Error: {input_dir} is not a directory", file=sys.stderr)
        sys.exit(1)

    works_file, ror_file = find_files(input_dir)
    print(f"Works file: {works_file.name}")
    print(f"ROR file: {ror_file.name}")

    stats_dir = output_dir / "stats"
    institutions_dir = output_dir / "institutions"
    stats_dir.mkdir(parents=True, exist_ok=True)
    institutions_dir.mkdir(parents=True, exist_ok=True)

    typesense_output = output_dir / "typesense-documents.jsonl"
    typesense_institutions_output = output_dir / "typesense-institutions.jsonl"

    ror_lookup = load_ror_lookup(ror_file)

    # Initialize extractors for relatedIdentifiers
    extractors = [SoftwareExtractor()]

    print("Counting works...")
    total_works = count_lines(works_file)
    print(f"Found {total_works} works")

    institution_work_counts = defaultdict(int)
    institution_years = defaultdict(lambda: defaultdict(int))
    institution_subjects = defaultdict(lambda: defaultdict(int))
    collaboration_pairs = defaultdict(int)
    global_years = defaultdict(int)
    subject_years = defaultdict(lambda: defaultdict(int))
    country_counts = defaultdict(int)
    all_ror_ids = set()

    print("Processing works...")
    with open(typesense_output, "wb") as ts_out:
        with open(works_file, "rb") as f:
            for line in tqdm(f, total=total_works, desc="Processing"):
                work = orjson.loads(line)

                year = extract_year_datacite(work)
                if year:
                    global_years[year] += 1

                arxiv_subjects, arxiv_subject_codes = extract_subjects_datacite(work)

                creators = work.get("attributes", {}).get("creators", [])
                work_ror_ids = set()
                work_authors = []
                work_affiliations = []
                work_institution_names = {}
                work_searchable_names = []
                work_countries = set()
                author_affiliations_list = []

                for creator in creators:
                    author_name = creator.get("name", "")
                    if author_name:
                        work_authors.append(author_name)

                    author_affs = []

                    for aff in creator.get("affiliation", []):
                        aff_text = aff.get("name", "")
                        if aff_text:
                            work_affiliations.append(aff_text)

                        ror_id = aff.get("affiliationIdentifier", "")
                        if ror_id and aff.get("affiliationIdentifierScheme") != "ROR":
                            ror_id = ""

                        aff_entry = {"text": aff_text} if aff_text else {}

                        if ror_id:
                            work_ror_ids.add(ror_id)
                            all_ror_ids.add(ror_id)
                            aff_entry["ror_id"] = ror_id

                            if ror_id in ror_lookup:
                                ror_record = ror_lookup[ror_id]
                                inst_name = get_display_name(ror_record)
                                if inst_name:
                                    work_institution_names[ror_id] = inst_name
                                    aff_entry["institution_name"] = inst_name
                                    work_searchable_names.append(inst_name)
                                name_variants = get_all_names(ror_record)
                                work_searchable_names.extend(name_variants["aliases"])
                                work_searchable_names.extend(name_variants["acronyms"])
                                work_searchable_names.extend(name_variants["labels"])
                                country = get_country(ror_record)
                                if country:
                                    work_countries.add(country)

                        if aff_entry:
                            author_affs.append(aff_entry)

                    if author_name:
                        author_affiliations_list.append({
                            "name": author_name,
                            "affiliations": author_affs
                        })

                for ror_id in work_ror_ids:
                    institution_work_counts[ror_id] += 1
                    if year:
                        institution_years[ror_id][year] += 1
                    for subj in arxiv_subject_codes:
                        institution_subjects[ror_id][subj] += 1

                    if ror_id in ror_lookup:
                        country = get_country(ror_lookup[ror_id])
                        country_counts[country] += 1

                ror_list = sorted(work_ror_ids)
                for i, ror1 in enumerate(ror_list):
                    for ror2 in ror_list[i+1:]:
                        collaboration_pairs[(ror1, ror2)] += 1

                for subj in arxiv_subject_codes:
                    if year:
                        subject_years[subj][year] += 1

                ror_ids_list = sorted(work_ror_ids)
                institution_names_list = [work_institution_names.get(rid, "") for rid in ror_ids_list]

                arxiv_id = extract_arxiv_id(work)

                ts_doc = {
                    "id": arxiv_id,
                    "doi": extract_doi(work),
                    "arxiv_id": arxiv_id,
                    "arxiv_id_link": extract_arxiv_id_link(work),
                    "title": extract_title(work),
                    "year": year or 0,
                    "authors": work_authors,
                    "affiliations": work_affiliations,
                    "ror_ids": ror_ids_list,
                    "institution_names": institution_names_list,
                    "searchable_names": list(set(work_searchable_names)),
                    "countries": list(work_countries),
                    "subjects": arxiv_subjects,
                    "subject_codes": arxiv_subject_codes,
                    "publication_link": extract_publication_link(work),
                    "has_publication": bool(extract_publication_link(work)),
                    "author_affiliations": orjson.dumps(author_affiliations_list).decode("utf-8")
                }

                # Run extractors on the record
                for extractor in extractors:
                    extracted_fields = extractor.extract(work)
                    ts_doc.update(extracted_fields)

                ts_out.write(orjson.dumps(ts_doc) + b"\n")

    print(f"Found {len(all_ror_ids)} unique institutions")
    print(f"Wrote Typesense documents to {typesense_output}")

    print("Writing stats...")
    years_list = sorted(global_years.keys())
    global_stats = {
        "total_works": total_works,
        "total_institutions": len(all_ror_ids),
        "total_countries": len(country_counts),
        "year_range": {
            "min": min(years_list) if years_list else None,
            "max": max(years_list) if years_list else None
        },
        "generated_at": datetime.now(timezone.utc).isoformat()
    }
    write_json(stats_dir / "global-stats.json", global_stats)

    institution_counts = sorted(institution_work_counts.items(), key=lambda x: -x[1])
    top_100 = []
    for ror_id, count in institution_counts[:100]:
        if ror_id in ror_lookup:
            ror_record = ror_lookup[ror_id]
            name_variants = get_all_names(ror_record)
            top_100.append({
                "ror_id": ror_id,
                "name": get_display_name(ror_record),
                "aliases": name_variants["aliases"],
                "acronyms": name_variants["acronyms"],
                "labels": name_variants["labels"],
                "city": get_city(ror_record),
                "country": get_country(ror_record),
                "work_count": count
            })
    write_json(stats_dir / "top-institutions.json", top_100)

    country_list = sorted(
        [{"country": c, "work_count": cnt} for c, cnt in country_counts.items()],
        key=lambda x: -x["work_count"]
    )
    write_json(stats_dir / "by-country.json", country_list)

    year_series = [{"year": y, "count": global_years[y]} for y in sorted(global_years.keys())]
    write_json(stats_dir / "by-year.json", year_series)

    subject_trend_data = {
        subj: [{"year": y, "count": c} for y, c in sorted(year_counts.items())]
        for subj, year_counts in subject_years.items()
    }
    write_json(stats_dir / "subject-trends.json", subject_trend_data)

    print("Writing institutions JSONL for Typesense...")
    with open(typesense_institutions_output, "wb") as inst_out:
        for ror_id in tqdm(all_ror_ids, desc="Institutions"):
            ror_record = ror_lookup.get(ror_id, {})

            collaborators = defaultdict(int)
            for pair, count in collaboration_pairs.items():
                if pair[0] == ror_id:
                    collaborators[pair[1]] += count
                elif pair[1] == ror_id:
                    collaborators[pair[0]] += count

            top_collab = sorted(collaborators.items(), key=lambda x: -x[1])[:20]
            collab_list = []
            for collab_ror, collab_count in top_collab:
                if collab_ror in ror_lookup:
                    collab_record = ror_lookup[collab_ror]
                    collab_list.append({
                        "ror_id": collab_ror,
                        "name": get_display_name(collab_record),
                        "country": get_country(collab_record),
                        "collaboration_count": collab_count
                    })

            subj_counts = institution_subjects[ror_id]
            top_subjects = sorted(subj_counts.items(), key=lambda x: -x[1])[:10]

            year_data = institution_years[ror_id]
            time_series = [{"year": y, "count": c} for y, c in sorted(year_data.items())]

            name_variants = get_all_names(ror_record)
            ror_hash = get_ror_id_hash(ror_id)

            inst_doc = {
                "id": ror_hash,
                "ror_id": ror_id,
                "name": get_display_name(ror_record),
                "acronyms": name_variants["acronyms"],
                "aliases": name_variants["aliases"],
                "labels": name_variants["labels"],
                "country": get_country(ror_record),
                "country_code": get_country_code(ror_record),
                "city": get_city(ror_record),
                "types": ror_record.get("types", []),
                "subject_codes": [s for s, _ in top_subjects],
                "work_count": institution_work_counts[ror_id],
                "time_series": orjson.dumps(time_series).decode("utf-8"),
                "top_collaborators": orjson.dumps(collab_list).decode("utf-8"),
                "top_subjects": orjson.dumps([{"code": s, "count": c} for s, c in top_subjects]).decode("utf-8"),
                "links": orjson.dumps(convert_decimals(ror_record.get("links", []))).decode("utf-8"),
                "locations": orjson.dumps(convert_decimals(ror_record.get("locations", []))).decode("utf-8"),
            }
            inst_out.write(orjson.dumps(inst_doc) + b"\n")

    print(f"Wrote institutions JSONL to {typesense_institutions_output}")

    print("\nDone!")
    print(f"Output written to {output_dir}")


if __name__ == "__main__":
    main()
