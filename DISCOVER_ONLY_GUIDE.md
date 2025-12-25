# Discover-Only Feature Guide

## Overview

The `--discover-only` flag allows you to populate the tracking/state database with URLs for TIGER/Line files without actually downloading them. This is useful for:

- **Planning downloads**: See what files are available before downloading
- **Bandwidth management**: Separate discovery from download phases
- **Resource allocation**: Know the total size before starting downloads
- **Selective downloading**: Discover all files, then selectively download

## Quick Start

### 1. Discover Available Files

Discover files for one or more states:

```bash
# Single state (California)
python census/zip_dl.py --discover-only --states 06 --types EDGES,ADDR

# Multiple states (California, Texas, New York)
python census/zip_dl.py --discover-only --states 06,48,36 --types EDGES,ADDR,FEATNAMES
```

### 2. Check Status

View what was discovered:

```bash
python census/zip_dl.py --show-status
```

This shows:
- Number of URLs discovered per state
- Completed downloads
- Failed downloads
- Pending downloads

### 3. Download Discovered Files

Download the files that were discovered:

```bash
# Download with discovery (uses already discovered URLs)
python census/zip_dl.py --states 06 --discover --resume

# Or just download without re-discovering (if URLs already in database)
python census/zip_dl.py --states 06 --resume
```

## Command Reference

### Required Arguments for `--discover-only`

- `--states`: One or more state FIPS codes (comma-separated)
- `--types`: One or more dataset types (comma-separated)

### Optional Arguments

- `--year`: Year to discover (default: 2024)
- `--output`: Output directory (default: census/tiger)
- `--state-file`: State database file (default: .tiger_download_state)
- `--use-db` / `--no-use-db`: Use DuckDB (default) or JSON for state tracking
- `--timeout`: Request timeout in seconds (default: 60)

## Examples

### Example 1: Basic Discovery

```bash
# Discover EDGES and ADDR files for Delaware
python census/zip_dl.py --discover-only --states 10 --types EDGES,ADDR
```

Output:
```
MODE: Discover-only (populating state database without downloading)

======================================================================
Discovering files for Delaware (FIPS: 10)
======================================================================

Total files discovered: 150
URLs populated in state database

======================================================================
DISCOVERY SUMMARY
======================================================================
Total URLs Discovered: 150
States Processed:      1
Elapsed Time:          5.2 seconds
```

### Example 2: Multiple States and Types

```bash
# Discover multiple types for multiple states
python census/zip_dl.py --discover-only \
  --states 06,36,48 \
  --types EDGES,ADDR,FACES,FEATNAMES
```

### Example 3: Using Custom Output Directory

```bash
# Discover and specify custom state file location
python census/zip_dl.py --discover-only \
  --states 13 \
  --types EDGES,ADDR \
  --output /data/tiger \
  --state-file /data/tiger/.download_state
```

### Example 4: Complete Workflow

```bash
# Step 1: Discover files
python census/zip_dl.py --discover-only --states 06 --types EDGES,ADDR

# Step 2: Check what was discovered
python census/zip_dl.py --show-status

# Step 3: Download discovered files
python census/zip_dl.py --states 06 --discover --resume

# Step 4: Check progress during download
python census/zip_dl.py --show-status
```

## State Database Structure

The discover-only feature populates the state database with:

### JSON Format (`.json` file)
```json
{
  "files": {},
  "completed": [],
  "failed": [],
  "states": {
    "06": {
      "name": "California",
      "completed": 0,
      "failed": 0,
      "urls": []
    }
  },
  "discovered_urls": {
    "06": [
      "https://www2.census.gov/geo/tiger/TIGER2024/EDGES/tl_2024_06001_edges.zip",
      "https://www2.census.gov/geo/tiger/TIGER2024/EDGES/tl_2024_06003_edges.zip",
      ...
    ]
  }
}
```

### DuckDB Format (`.duckdb` file)

Tables:
- `files`: Individual file tracking
- `states`: State-level statistics
- `discovered_urls`: All discovered URLs per state
- `url_lists`: Completed/failed URL tracking

## Status Output

The `--show-status` command shows detailed information:

```
Download Status Summary
======================================================================
State: California (FIPS: 06)
  Discovered: 3000
  Completed:  1500
  Failed:     50
  Pending:    1450
  Progress:   50.0%
  
  Sample Completed URLs (3):
    ✓ https://www2.census.gov/geo/tiger/TIGER2024/EDGES/tl_2024_06001_edges.zip
    ✓ https://www2.census.gov/geo/tiger/TIGER2024/EDGES/tl_2024_06003_edges.zip
    ✓ https://www2.census.gov/geo/tiger/TIGER2024/EDGES/tl_2024_06005_edges.zip
  
  Sample Pending URLs (3):
    ⊙ https://www2.census.gov/geo/tiger/TIGER2024/EDGES/tl_2024_06007_edges.zip
    ⊙ https://www2.census.gov/geo/tiger/TIGER2024/EDGES/tl_2024_06009_edges.zip
    ⊙ https://www2.census.gov/geo/tiger/TIGER2024/EDGES/tl_2024_06011_edges.zip
```

## Available Dataset Types

Use `--list-types` to see all available types:

```bash
python census/zip_dl.py --list-types
```

Common types for geocoding:
- `EDGES`: All Lines (roads, railroads, etc.)
- `ADDR`: Address Ranges
- `FACES`: Topological Faces (polygons)
- `FEATNAMES`: Feature Names

## Available States

Use `--list-states` to see all state FIPS codes:

```bash
python census/zip_dl.py --list-states
```

## Tips

1. **Start small**: Test with a small state (like Delaware - 10) first
2. **Use DuckDB**: Better performance for large states (enabled by default)
3. **Check status frequently**: Monitor progress with `--show-status`
4. **Resume capability**: Can pause and resume at any time
5. **Parallel downloads**: Adjust `--parallel` for faster downloads (default: 4)

## Troubleshooting

### "Error: --discover-only requires --states to be specified"
**Solution**: Always specify `--states` and `--types` with `--discover-only`

### "Warning: Could not scrape directory"
**Possible causes**:
- Network connectivity issues
- Census Bureau website temporarily unavailable
- Invalid dataset type or year

**Solution**: Check network connection and retry

### No URLs discovered
**Possible causes**:
- Invalid state FIPS code
- Dataset type not available for that year
- Network issues

**Solution**: Verify state code with `--list-states` and type with `--list-types`

## Performance

Discovery is relatively fast:
- Small state (e.g., Delaware): ~5-10 seconds
- Large state (e.g., California): ~30-60 seconds
- Multiple states: Processed sequentially

## See Also

- Main README: `/census/README.md`
- Example script: `/examples/demo_discover_only.py`
- Test suite: `/test_discover_only.py`
