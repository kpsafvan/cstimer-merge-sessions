# cstimer-merge-sessions

A Python script to merge two csTimer session export JSON files into a single combined file.

## Overview

This tool combines solving data from two separate csTimer session exports. It intelligently merges events by their scramble type (`scrType`) and consolidates all solves into chronologically ordered lists.

## Features

- **Event matching by `scrType`**: Events with the same scramble type are automatically merged
- **Default event handling**: Events without a scramble type are treated as the same default event
- **Chronological sorting**: All solves are sorted by timestamp within each event
- **Stats consolidation**: Solve counts and date ranges are properly combined
- **Non-destructive**: Original input files remain untouched
- **Flexible output**: Define custom output filename or use default naming

## Requirements

- Python 3.7+
- Standard library only (no external dependencies)

## Installation

Clone the repository:
```bash
git clone https://github.com/kpsafvan/cstimer-merge-sessions.git
cd cstimer-merge-sessions
```

## Usage

### Basic usage
```bash
python merge_sessions.py file1.json file2.json
```

This creates a merged output file with default naming: `merged_<file1>_<file2>.json`

### Custom output filename
```bash
python merge_sessions.py file1.json file2.json -o merged_result.json
```

### Example with files folder
```bash
python merge_sessions.py files/session_a.json files/session_b.json
```

## Input Format

Both input files should be csTimer session exports containing:
- `properties.sessionData`: JSON object or stringified JSON with event metadata
- `sessionX`: Arrays of solve records for each event (e.g., `session1`, `session2`, etc.)

Example structure:
```json
{
  "session1": [[0, 45000], [0, 52000], ...],
  "session2": [[0, 28000], ...],
  "properties": {
    "sessionData": "{\"1\": {\"opt\": {\"scrType\": \"666wca\"}, ...}, ...}"
  }
}
```

## Output Format

The merged file contains:
- Combined `sessionX` arrays with solves sorted chronologically
- Merged `properties.sessionData` with updated solve counts and date ranges
- All other metadata preserved from inputs

Example merged event:
```json
{
  "1": {
    "name": 1,
    "opt": {"scrType": "666wca"},
    "stat": [256, 0, 165000.5],
    "date": [1650188199, 1774260017],
    "rank": 1
  }
}
```

Where `stat[0]` is the total combined solve count.

## How Merging Works

1. **Event grouping**: Events are grouped by `opt.scrType`
   - If `scrType` is missing, the event is grouped as "default"
2. **Stat merging**: Solve counts are summed, statistics are recalculated
3. **Date merging**: The earliest and latest timestamps across both events are used
4. **Solve merging**: All solves from matching events are combined and sorted by timestamp
5. **Renumbering**: Events are renumbered sequentially (1, 2, 3, ...) with corresponding session arrays

## Files

- `merge_sessions.py` - Main script
- `files/` - Folder for input/output files
- `.gitignore` - Excludes the `files/` folder from version control

## Example

```bash
# Merge two session exports
python merge_sessions.py files/session_2024.json files/session_backup.json -o files/combined.json

# Output shows merged events:
# Merged session output written to: files/combined.json
# Combined events and solve counts:
#  - 1: 512 solves
#  - 2: 4262 solves (default event)
#  - 3: 32 solves
```

## Notes

- Original input files are never modified
- Solves are automatically sorted by timestamp if available
- The script handles both JSON objects and stringified JSON in `sessionData`
- Empty session arrays are preserved in the output

## License

MIT
