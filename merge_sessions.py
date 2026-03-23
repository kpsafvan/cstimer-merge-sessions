import argparse
import copy
import json
import os
import sys


def read_file(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        print(f"Error: file not found: {path}", file=sys.stderr)
        sys.exit(1)
    except IOError as e:
        print(f"Error reading file {path}: {e}", file=sys.stderr)
        sys.exit(1)


def parse_json(raw: str, source: str):
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end != -1 and end > start:
            fragment = raw[start:end + 1]
            try:
                return json.loads(fragment)
            except json.JSONDecodeError as e2:
                print(f"Error: unable to parse JSON from {source} after trimming wrapper text: {e2}", file=sys.stderr)
                sys.exit(1)
        print(f"Error: unable to parse JSON from {source}", file=sys.stderr)
        sys.exit(1)


def find_nested_session_data(obj):
    if isinstance(obj, dict):
        if "sessionData" in obj and isinstance(obj["sessionData"], dict):
            return obj["sessionData"]
        for value in obj.values():
            nested = find_nested_session_data(value)
            if nested is not None:
                return nested
    elif isinstance(obj, list):
        for item in obj:
            nested = find_nested_session_data(item)
            if nested is not None:
                return nested
    return None


def parse_session_data_value(value):
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            # try unescaped form
            try:
                parsed = json.loads(value.encode("utf-8").decode("unicode_escape"))
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                pass
    return None


def get_session_data(obj):
    if not isinstance(obj, dict):
        return None

    props = obj.get("properties")
    if isinstance(props, dict):
        session_data = parse_session_data_value(props.get("sessionData"))
        if session_data is not None:
            return session_data

    session_data = parse_session_data_value(obj.get("sessionData"))
    if session_data is not None:
        return session_data

    return find_nested_session_data(obj)


def extract_root_session_arrays(obj):
    if not isinstance(obj, dict):
        return {}
    return {k: v for k, v in obj.items() if isinstance(k, str) and k.startswith("session") and isinstance(v, list)}


def get_solve_timestamp_from_item(solve):
    if isinstance(solve, dict):
        return get_solve_timestamp(solve)
    if isinstance(solve, list) and solve:
        for item in reversed(solve):
            if isinstance(item, (int, float)):
                return float(item)
            if isinstance(item, str):
                try:
                    return float(item)
                except ValueError:
                    continue
    return None


def merge_session_arrays(arr1, arr2):
    list1 = arr1 or []
    list2 = arr2 or []
    combined = list1 + list2
    indexed = []
    for i, item in enumerate(combined):
        ts = get_solve_timestamp_from_item(item)
        indexed.append((float('inf') if ts is None else ts, i, item))
    if all(x[0] == float('inf') for x in indexed):
        return combined
    sorted_items = [x[2] for x in sorted(indexed, key=lambda x: (x[0], x[1]))]
    return sorted_items


def find_solve_list_key(event_obj):
    if not isinstance(event_obj, dict):
        return None
    for key in ["solves", "solveData", "solveList", "session", "sessions", "data"]:
        if key in event_obj and isinstance(event_obj[key], list):
            return key
    return None


def get_solve_timestamp(solve):
    if not isinstance(solve, dict):
        return None
    candidates = ["datetime", "date", "timestamp", "time", "ts", "t"]
    for key in candidates:
        value = solve.get(key)
        if value is None:
            continue
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                continue
    return None


def normalize_solves(solves):
    if not isinstance(solves, list):
        return []
    enumerated = []
    for idx, solve in enumerate(solves):
        ts = get_solve_timestamp(solve)
        enumerated.append((ts, idx, solve))
    # if no timestamps at all, keep original order
    if all(item[0] is None for item in enumerated):
        return solves
    # sort by timestamp, then original index to preserve stable ordering
    sorted_data = sorted(enumerated, key=lambda x: (float('inf') if x[0] is None else x[0], x[1]))
    return [item[2] for item in sorted_data]


def merge_event_data(dest_event, src_event):
    dest_event = copy.deepcopy(dest_event) if dest_event is not None else {}
    src_event = src_event or {}

    key = find_solve_list_key(dest_event) or find_solve_list_key(src_event)
    if key is None:
        return dest_event if dest_event else copy.deepcopy(src_event)

    dest_solves = dest_event.get(key, []) if isinstance(dest_event.get(key), list) else []
    src_solves = src_event.get(key, []) if isinstance(src_event.get(key), list) else []

    merged = dest_solves + src_solves
    merged = normalize_solves(merged)
    dest_event[key] = merged

    # update count fields if they are present or can be inferred
    count_key = None
    for candidate in ["count", "length", "total"]:
        if candidate in dest_event or candidate in src_event:
            count_key = candidate
            break
    if count_key:
        dest_event[count_key] = len(merged)

    return dest_event


def merge_session_data(data1, data2):
    merged = copy.deepcopy(data1 or {})
    data2 = data2 or {}

    for key, src_entry in data2.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(src_entry, dict):
            dest_entry = merged[key]
            # merge stat count
            stat1 = dest_entry.get("stat")
            stat2 = src_entry.get("stat")
            if isinstance(stat1, list) and stat1 and isinstance(stat2, list) and stat2:
                try:
                    c1 = float(stat1[0])
                    c2 = float(stat2[0])
                    sumc = c1 + c2
                    dest_entry["stat"][0] = int(sumc) if sumc.is_integer() else sumc
                except (ValueError, TypeError):
                    pass
            # merge range dates
            d1 = dest_entry.get("date")
            d2 = src_entry.get("date")
            if isinstance(d1, list) and len(d1) >= 2 and isinstance(d2, list) and len(d2) >= 2:
                dates = [x for x in [d1[0], d2[0]] if isinstance(x, (int, float))]
                dates2 = [x for x in [d1[1], d2[1]] if isinstance(x, (int, float))]
                if dates and dates2:
                    dest_entry["date"] = [min(dates), max(dates2)]
            # fill missing fields with src values
            for sub_key, sub_val in src_entry.items():
                if sub_key not in dest_entry:
                    dest_entry[sub_key] = copy.deepcopy(sub_val)
            merged[key] = dest_entry
        else:
            merged[key] = copy.deepcopy(src_entry)

    return merged


def merge_root_sessions(root1, root2):
    root1 = root1 or {}
    root2 = root2 or {}
    merged = copy.deepcopy(root1)

    all_session_keys = set(extract_root_session_arrays(root1).keys()) | set(extract_root_session_arrays(root2).keys())
    for key in all_session_keys:
        arr1 = root1.get(key, []) if isinstance(root1.get(key), list) else []
        arr2 = root2.get(key, []) if isinstance(root2.get(key), list) else []
        merged[key] = merge_session_arrays(arr1, arr2)

    # keep any extra non-session keys from root2 (preserve properties handled elsewhere)
    for key, val in root2.items():
        if key not in merged and key != "properties":
            merged[key] = copy.deepcopy(val)

    return merged


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge two csTimer JSON session files by event sessionData.")
    parser.add_argument("file1", help="First input file")
    parser.add_argument("file2", help="Second input file")
    parser.add_argument("-o", "--output", default=None, help="Output file path (default: merged_[file1]_[file2].json)")
    args = parser.parse_args()

    raw1 = read_file(args.file1)
    raw2 = read_file(args.file2)

    obj1 = parse_json(raw1, args.file1)
    obj2 = parse_json(raw2, args.file2)

    session1 = get_session_data(obj1)
    session2 = get_session_data(obj2)

    if session1 is None and session2 is None:
        print("Error: neither input JSON contains properties.sessionData", file=sys.stderr)
        sys.exit(1)

    merged_root = merge_root_sessions(obj1, obj2)

    merged_session_data = merge_session_data(session1 or {}, session2 or {})

    merged_root.setdefault("properties", {})
    # keep same type as input (string if originally string)
    original_session_data = None
    if isinstance(obj1, dict) and isinstance(obj1.get("properties"), dict):
        original_session_data = obj1["properties"].get("sessionData")
    if original_session_data is None and isinstance(obj2, dict) and isinstance(obj2.get("properties"), dict):
        original_session_data = obj2["properties"].get("sessionData")

    if isinstance(original_session_data, str):
        merged_root["properties"]["sessionData"] = json.dumps(merged_session_data, ensure_ascii=False)
    else:
        merged_root["properties"]["sessionData"] = merged_session_data

    out_path = args.output
    if not out_path:
        base1 = os.path.splitext(os.path.basename(args.file1))[0]
        base2 = os.path.splitext(os.path.basename(args.file2))[0]
        out_path = f"merged_{base1}_{base2}.json"

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(merged_root, f, ensure_ascii=False, indent=2)

    print(f"Merged session output written to: {out_path}")

    merged_sessions = merged_session_data
    if not merged_sessions:
        print("Warning: merged sessionData is empty")
    else:
        print("Combined events and solve counts:")
        for event, event_obj in sorted(merged_sessions.items()):
            count = "?"
            if isinstance(event_obj, dict):
                stat = event_obj.get("stat")
                if isinstance(stat, list) and stat:
                    count = int(stat[0]) if isinstance(stat[0], (int, float)) else stat[0]
            print(f" - {event}: {count} solves")


if __name__ == "__main__":
    main()
