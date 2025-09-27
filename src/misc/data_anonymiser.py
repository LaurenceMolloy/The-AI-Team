"""
===============================================================================
Anonymisation & Trimming Script for Sample Metadata JSON
===============================================================================

Purpose:     Take a real metadata sample as input and create a representative 
             sample JSON file for supplying to a public LLM that doesn't expose
             any commercially sensitive information.
Input:       data_anonymiser.py <input_json_file> <output_folder>   
Output:      A trimmed JSON file with information anonymised.
Authored By: ChatGPT (GPT-5, OpenAI), September 2025
Prompted By: Laurence Molloy
===============================================================================
"""

import json
import re
from pathlib import Path
import argparse

# ----------------- Configuration -----------------
MAX_RECORDS = 5  # Limit output to first N records
# -------------------------------------------------

# Regexes for emails and phone numbers
EMAIL_REGEX = re.compile(r"[^@]+@[^@]+\.[^@]+")
PHONE_REGEX = re.compile(r"\+?\d[\d\s\-()]{6,}\d")

# Dictionaries for consistent anonymisation
url_map, email_map, phone_map, text_map = {}, {}, {}, {}

def anonymise_value(value, mapping, prefix):
    if value not in mapping:
        mapping[value] = f"{prefix}{len(mapping) + 1}"
    return mapping[value]

def anonymise_string(s):
    """Anonymise a string depending on its content."""
    if EMAIL_REGEX.match(s):
        return anonymise_value(s, email_map, "email")
    if PHONE_REGEX.match(s):
        return anonymise_value(s, phone_map, "phone")
    if s.startswith("http"):
        return anonymise_value(s, url_map, "url")
    return anonymise_value(s, text_map, "text")

# Blocks that must be anonymised in full
ANON_BLOCKS = {
    "data_providers",
    "contacts",
    "citations",
    "authors",
    "unique_datasets",
    "dataset_identifiers",
    "datasets",
    "data_files",
    "data_resources",
    "data_collections",
    "data_licences",
    "data_tags",
}

# Fields inside pipeline to anonymise
PIPELINE_FIELDS = {"script", "endpoints"}

# Blocks/keys that should never be anonymised
SKIP_KEYS = {"location", "id", "uuid"}

def anonymise(obj, parent_key=None, force=False):
    """
    Recursively anonymise JSON.
    - force=True means anonymise everything in this subtree.
    """
    if isinstance(obj, dict):
        new_obj = {}
        for k, v in obj.items():
            # Special handling: limit data_files and data_resources
            if k == "data_files" and isinstance(v, list):
                v = v[:1]
            if k == "data_resources" and isinstance(v, list):
                v = v[:1]

            # If we're inside a block to anonymise, or the key is in PIPELINE_FIELDS
            if force or k.lower() in PIPELINE_FIELDS:
                if isinstance(v, str):
                    new_obj[k] = anonymise_string(v)
                else:
                    new_obj[k] = anonymise(v, k, force=True)
            elif k.lower() in ANON_BLOCKS:
                new_obj[k] = anonymise(v, k, force=True)
            elif k.lower() in SKIP_KEYS:
                new_obj[k] = v
            else:
                new_obj[k] = anonymise(v, k, force=False)
        return new_obj
    elif isinstance(obj, list):
        return [anonymise(x, parent_key, force=force) for x in obj]
    elif isinstance(obj, str):
        if force:
            return anonymise_string(obj)
        return obj
    else:
        return obj

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Anonymise a sample metadata JSON file and trim to first N records."
    )
    parser.add_argument("input_file", type=Path, help="Path to the input JSON file")
    parser.add_argument("output_folder", type=Path, help="Folder to write the anonymised JSON file")
    args = parser.parse_args()

    infile = args.input_file
    outfile = args.output_folder / f"{infile.stem}_anonymised.json"

    if not args.output_folder.exists():
        args.output_folder.mkdir(parents=True, exist_ok=True)

    with infile.open("r", encoding="utf-8") as f:
        data = json.load(f)

    # Limit the records section to first N entries, if it exists
    if "records" in data and isinstance(data["records"], list):
        data["records"] = data["records"][:MAX_RECORDS]

    anonymised_data = anonymise(data)

    with outfile.open("w", encoding="utf-8") as f:
        json.dump(anonymised_data, f, indent=2, ensure_ascii=False)

    print(f"Anonymised file written to {outfile}")

