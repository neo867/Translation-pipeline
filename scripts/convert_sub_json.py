import json
import csv
import os
import re

def json_to_csv(json_path):
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    if not data:
        print(f"Empty data in {json_path}")
        return

    # Infer language from filename
    # Patterns: sub-50-eng-id.json, sub-50-eng-jp.json, etc.
    filename = os.path.basename(json_path)
    lang_match = re.search(r'-eng-([a-z]+)\.json$', filename.lower())
    if lang_match:
        lang_raw = lang_match.group(1)
        # Normalize lang key for CSV column template
        lang_map = {
            'id': 'id',
            'ind': 'id',
            'jp': 'jp',
            'thai': 'th',
            'tw': 'tw',
            'kr': 'kr'
        }
        lang_key = lang_map.get(lang_raw, lang_raw)
    else:
        lang_key = 'tw' # default

    target_col = f"target_{lang_key}"
    
    csv_path = json_path.replace('.json', '.csv')
    
    # Expected keys in JSON: lesson, segment, timestamp, source, original translation
    fieldnames = ["lesson", "segment", "timestamp", "source", target_col]
    
    with open(csv_path, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for item in data:
            row = {
                "lesson": item.get("lesson", ""),
                "segment": item.get("segment", ""),
                "timestamp": item.get("timestamp", ""),
                "source": item.get("source", ""),
                target_col: item.get("original translation", "")
            }
            writer.writerow(row)
    
    print(f"Converted {json_path} -> {csv_path}")

if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    files = [
        os.path.join(base_dir, "Test Case/Course Subtitle/sub-50-eng-id.json"),
        os.path.join(base_dir, "Test Case/Course Subtitle/sub-50-eng-ind.json"),
        os.path.join(base_dir, "Test Case/Course Subtitle/sub-50-eng-jp.json"),
        os.path.join(base_dir, "Test Case/Course Subtitle/sub-50-eng-thai.json"),
        os.path.join(base_dir, "Test Case/Course Subtitle/sub-50-eng-tw.json"),
        os.path.join(base_dir, "Test Case/Course Subtitle/sub-50-eng-kr.json")
    ]
    
    for f in files:
        if os.path.exists(f):
            json_to_csv(f)
        else:
            print(f"File not found: {f}")
