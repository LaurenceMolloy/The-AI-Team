#!/usr/bin/env python3
import os
import sys
import json
import datetime
import argparse
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap

PLACEHOLDERS = {"-", "n/a", "na", "unknown"}

def clean_location_name(name):
    if not isinstance(name, str):
        return None
    name = name.strip()
    if name.lower() in PLACEHOLDERS or not name:
        return None
    return name

def is_scotland(name):
    if not isinstance(name, str):
        return False
    name = name.strip().strip('.,;:!?\'"()[]{}').lower()
    return name == "scotland"

def file_identity(path):
    base = os.path.basename(path)
    if '.' in base:
        parts = base.split('.')
        if len(parts) > 1:
            return '.'.join(parts[:-1])
        else:
            return base
    return base

def process_file(filepath):
    try:
        with open(filepath, encoding='utf-8') as f:
            data = json.load(f)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None, True

    records = data.get("records")
    if not isinstance(records, list):
        records = []

    file_info = {
        "has_location": False,
        "has_scotland": False,
        "total_records": len(records),
        "records_with_location": 0,
        "records_with_scotland": 0
    }

    for rec in records:
        locs = rec.get("locations")
        if not isinstance(locs, list):
            locs = []
        populated = [clean_location_name(l.get("name")) for l in locs if isinstance(l, dict)]
        populated = [p for p in populated if p]
        if populated:
            file_info["has_location"] = True
            file_info["records_with_location"] += 1
        if any(is_scotland(l.get("name")) for l in locs if isinstance(l, dict)):
            file_info["has_scotland"] = True
            file_info["records_with_scotland"] += 1

    return file_info, False

def population_level(pct):
    if pct == 0:
        return "empty"
    elif pct <= 0.05:
        return "trace"
    elif pct <= 0.25:
        return "low"
    elif pct <= 0.50:
        return "medium"
    elif pct < 1.0:
        return "high"
    else:
        return "full"

def write_txt_lists(filename, error_files, scottish_files, populated_files,
                    pop_bin_files, scot_bin_files):
    def write_section(f, header, items):
        f.write(f"[{header}]\n")
        for item in sorted(items, key=str.lower):
            f.write(f"{item}\n")
        f.write("\n")

    with open(filename, "w", encoding="utf-8") as f:
        write_section(f, "error", error_files)
        write_section(f, "contains scottish", scottish_files)
        write_section(f, "populated", populated_files)

        # Per-bin lists for location population
        for bin_name in ["empty", "trace", "low", "medium", "high", "full"]:
            write_section(f, f"population_{bin_name}", pop_bin_files[bin_name])

        # Per-bin lists for Scottish distribution
        for bin_name in ["empty", "trace", "low", "medium", "high", "full"]:
            write_section(f, f"scotland_{bin_name}", scot_bin_files[bin_name])

def main():
    parser = argparse.ArgumentParser(description="Analyse JSON location fields.")
    parser.add_argument("--input", required=True, help="Folder containing JSON files to analyse")
    parser.add_argument("--output", required=True, help="Folder to write analysis outputs (YAML and TXT)")
    args = parser.parse_args()

    folder = args.input
    out_folder = args.output

    if not os.path.isdir(folder):
        print(f"Input folder does not exist: {folder}", file=sys.stderr)
        sys.exit(1)
    os.makedirs(out_folder, exist_ok=True)

    json_files = [f for f in os.listdir(folder)
                  if os.path.isfile(os.path.join(folder, f)) and f.lower().endswith(".json")]

    total_records = 0
    records_with_any_location_name = 0
    records_with_scotland = 0
    files_with_any_location_name = []
    files_with_scotland = []
    files_failed = []

    population_buckets = CommentedMap({"empty":0, "trace":0, "low":0, "medium":0, "high":0, "full":0})
    scotland_buckets = CommentedMap({"empty":0, "trace":0, "low":0, "medium":0, "high":0, "full":0})
    pop_bin_files = {k: [] for k in population_buckets.keys()}
    scot_bin_files = {k: [] for k in scotland_buckets.keys()}

    for f in json_files:
        path = os.path.join(folder, f)
        identity = file_identity(path)
        info, failed = process_file(path)
        if failed:
            files_failed.append(identity)
            continue

        total_records += info["total_records"]
        records_with_any_location_name += info["records_with_location"]
        records_with_scotland += info["records_with_scotland"]

        if info["has_location"]:
            files_with_any_location_name.append(identity)
        if info["has_scotland"]:
            files_with_scotland.append(identity)

        total = info["total_records"]
        pct_loc = (info["records_with_location"] / total) if total > 0 else 0.0
        pop_bin = population_level(pct_loc)
        population_buckets[pop_bin] += 1
        pop_bin_files[pop_bin].append(identity)

        pct_scot = (info["records_with_scotland"] / total) if total > 0 else 0.0
        scot_bin = population_level(pct_scot)
        scotland_buckets[scot_bin] += 1
        scot_bin_files[scot_bin].append(identity)

    files_parsed = len(json_files) - len(files_failed)

    # Build clean YAML
    summary = CommentedMap()
    metadata = CommentedMap({
        "analyzed_at": datetime.datetime.now(datetime.UTC).isoformat(),
        "input_path": folder,
        "files_scanned": len(json_files),
        "files_parsed": files_parsed
    })

    summary_map = CommentedMap({
        "total_files": files_parsed,
        "files_with_any_location_name": len(files_with_any_location_name),
        "files_with_scotland": len(files_with_scotland),
        "total_records": total_records,
        "records_with_any_location_name": records_with_any_location_name,
        "records_with_scotland": records_with_scotland
    })

    summary["metadata"] = metadata
    summary["summary"] = summary_map
    summary["location_population_level_distribution"] = population_buckets
    summary["scottish_location_distribution"] = scotland_buckets

    # Write YAML
    yaml_obj = YAML()
    yaml_obj.default_flow_style = False
    yaml_obj.indent(mapping=2, sequence=2, offset=2)
    yaml_path = os.path.join(out_folder, "location_analysis.yaml")
    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml_obj.dump(summary, f)

    # Write TXT lists including per-bin file lists
    txt_path = os.path.join(out_folder, "location_analysis_lists.txt")
    write_txt_lists(txt_path,
                    files_failed,
                    files_with_scotland,
                    files_with_any_location_name,
                    pop_bin_files,
                    scot_bin_files)

if __name__ == "__main__":
    main()