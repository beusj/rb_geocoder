# TIGER/Line Download and Import Quick Reference

## Problem: Census Bureau Server Errors

When downloading TIGER/Line files, you may encounter:
- **520 errors** - Server returning unknown errors
- **523 errors** - Origin server unreachable  
- **524 errors** - Timeout occurred
- **Connection timeouts** - Slow or interrupted downloads

## Solution: Enhanced Download and Progressive Loading

### Quick Start: Download and Import in One Command

```bash
# Download and import California
python tools/tiger_download_and_import.py geocoder.db ./tiger \
    --states 06 --cleanup --verbose

# Resume interrupted workflow
python tools/tiger_download_and_import.py geocoder.db ./tiger \
    --states 06 --resume --verbose
```

**Benefits:**
- Downloads and imports progressively (no waiting!)
- Automatically retries 520/523/524 errors (8 attempts with backoff)
- Resumes from interruption at any stage
- Tracks all state: download → extract → load
- Optionally cleans up ZIP files after import

### Alternative: Separate Download and Import

#### Step 1: Download with Enhanced Retry

```bash
# Download with automatic retry for 520/523 errors
python census/zip_dl.py --states 06 --output ./tiger --verbose

# Resume failed downloads
python census/zip_dl.py --states 06 --output ./tiger --resume --verbose

# Adjust for unreliable connections
python census/zip_dl.py --states 06 --output ./tiger \
    --timeout 90 --parallel 2 --resume --verbose
```

**Download Features:**
- 8 retry attempts with exponential backoff (2s → 60s max)
- Skip already downloaded files with `--resume`
- **Resume partial downloads** using HTTP Range headers
- Validates file sizes (retries zero-byte files)
- **Track states/territories requested** with detailed statistics
- State saved to `.tiger_download_state.json`

#### Step 2: Import with Progressive Loading

```bash
# Import as files become available
python tools/tiger_import_duckdb.py geocoder.db ./tiger \
    --progressive --state-file .import_state.json --verbose

# Import with automatic ZIP cleanup
python tools/tiger_import_duckdb.py geocoder.db ./tiger \
    --progressive --cleanup --verbose
```

**Import Features:**
- Import files as they are downloaded (progressive mode)
- Skip already imported files automatically
- Remove ZIPs after successful import (saves space)
- State saved to `.tiger_import_state.json`

## Handling Errors

### Frequent 520/523 Errors

**Reduce load on Census Bureau server:**
```bash
python census/zip_dl.py --states 06 --output ./tiger \
    --parallel 2 --timeout 90 --verbose
```

The script will automatically:
- Retry up to 8 times per file
- Wait with exponential backoff: 2s, 4s, 8s, 16s, 32s, 60s
- Add random jitter to avoid thundering herd
- Show progress: "HTTP 523 error, retrying in 8.3s (attempt 3/8)"

### Interrupted Downloads

**Just resume - it's that simple:**
```bash
python census/zip_dl.py --states 06 --output ./tiger --resume
```

The script will:
- Read `.tiger_download_state.json` to see what's completed
- Skip all successfully downloaded files
- **Resume partial downloads** from where they left off using HTTP Range headers
- Retry only failed files

### Check Download Status

**NEW: View detailed status summary:**
```bash
# Show comprehensive status for all states/territories
python census/zip_dl.py --show-status --output ./tiger

# This displays:
# - States/territories that have been requested
# - Completed vs failed downloads per state
# - Sample URLs for each state
# - Overall statistics
```

**View raw state file:**
```bash
# See completed downloads
cat ./tiger/.tiger_download_state.json | jq '.completed | length'

# See failed downloads
cat ./tiger/.tiger_download_state.json | jq '.failed'

# See all states requested
cat ./tiger/.tiger_download_state.json | jq '.states | keys'

# See details for specific state (e.g., California - 06)
cat ./tiger/.tiger_download_state.json | jq '.states["06"]'
```

### Check Import Status

```bash
# See imported files
cat .tiger_import_state.json | jq '.completed | length'

# See failed imports
cat .tiger_import_state.json | jq '.failed'
```

## State Files Reference

### Download State (`.tiger_download_state.json`)

**Enhanced structure with state/territory tracking:**
```json
{
  "files": {
    "/path/to/file.zip": {
      "status": "completed",
      "timestamp": 1703456789.123,
      "url": "https://www2.census.gov/...",
      "path": "/path/to/file.zip",
      "size": 1024000,
      "state": "06"
    },
    "/path/to/partial.zip": {
      "status": "partial",
      "timestamp": 1703456789.123,
      "url": "https://www2.census.gov/...",
      "path": "/path/to/partial.zip",
      "bytes_downloaded": 524288,
      "state": "06"
    }
  },
  "completed": ["url1", "url2", ...],
  "failed": ["url3", ...],
  "states": {
    "06": {
      "name": "California",
      "completed": 123,
      "failed": 2,
      "urls": []
    }
  }
}
```

**File status values:**
- `completed` - File successfully downloaded
- `failed` - Download failed after all retries
- `partial` - Download interrupted, can be resumed

### Import State (`.tiger_import_state.json`)
```json
{
  "files": {
    "/path/to/file.zip": {
      "status": "loaded",
      "timestamp": 1703456789.123,
      "county": "06075"
    }
  },
  "completed": ["file1", "file2", ...],
  "failed": []
}
```

### Workflow State (`.tiger_workflow_state.json`)
```json
{
  "workflow": "tiger_download_and_import",
  "states": {
    "06": {
      "status": "completed",
      "downloaded": 123,
      "imported": 123
    }
  },
  "statistics": {
    "downloaded": 123,
    "imported": 123,
    "failed_download": 0,
    "failed_import": 0
  }
}
```

## Best Practices

### For Reliable Downloads
1. **Use --resume** - Always use resume to skip completed files and resume partial downloads
2. **Check status** - Use `--show-status` to see progress for all states/territories
3. **Reduce parallelism** - Use `--parallel 2` or `3` for unreliable connections
4. **Increase timeout** - Use `--timeout 90` or `120` for slow connections
5. **Monitor progress** - Use `--verbose` to see retry attempts
6. **Don't delete temp files** - `.tmp` files are used to resume partial downloads

### For Efficient Import
1. **Use progressive mode** - Import files as they arrive with `--progressive`
2. **Clean up ZIPs** - Use `--cleanup` to save disk space after import
3. **Use state files** - Track progress with `--state-file`
4. **Run in parallel** - Start import while download is still running

### For Production Use
1. **Use unified workflow** - `tiger_download_and_import.py` handles everything
2. **Enable cleanup** - Save disk space with `--cleanup`
3. **Set reasonable parallelism** - Use `--parallel 3` for balance
4. **Keep state files** - Don't delete `.json` files until complete

## Command Reference

### Download Script (`census/zip_dl.py`)
```
--states CODES      Comma-separated state FIPS codes (e.g., "06,36,48")
--output DIR        Output directory (default: ./tiger)
--parallel N        Number of parallel downloads (default: 4)
--timeout N         Download timeout in seconds (default: 60)
--resume            Resume from previous session (includes partial downloads)
--state-file FILE   State file path (default: .tiger_download_state.json)
--verbose           Show detailed progress
--list-states       List all state FIPS codes
--list-types        List all dataset types
--show-status       Show download status for all states/territories
```

### Import Script (`tools/tiger_import_duckdb.py`)
```
--progressive       Enable progressive loading mode
--cleanup           Remove ZIP files after successful import
--state-file FILE   State file for tracking progress
--counties CODES    Import specific counties only
--verbose           Show detailed progress
```

### Unified Workflow (`tools/tiger_download_and_import.py`)
```
--states CODES      Comma-separated state FIPS codes
--parallel N        Number of parallel downloads (default: 3)
--timeout N         Download timeout in seconds (default: 60)
--cleanup           Remove ZIPs after import
--resume            Resume from previous workflow
--verbose           Show detailed progress
```

## Troubleshooting

### Downloads keep failing with 520/523 errors
- Reduce `--parallel` to 2
- Increase `--timeout` to 90 or 120
- Use `--resume` to retry only failed files and resume partial downloads
- Try downloading during off-peak hours

### Partial downloads are not resuming
- Make sure you're using `--resume` flag
- Don't delete `.tmp` files - they contain partial downloads
- Check that the state file exists and is valid JSON
- The script will automatically resume from the byte offset where it stopped

### Want to see what's been downloaded?
- Use `--show-status` to see a summary of all states/territories
- Shows completed, failed, and partial downloads per state
- Lists sample URLs for verification

### Import is too slow
- Use `--progressive` to start importing while downloading
- Make sure you have enough RAM (512MB-2GB recommended)
- Import fewer counties at a time

### Running out of disk space
- Use `--cleanup` to remove ZIPs after import
- Import one state at a time
- Download only the types you need with `--types EDGES,ADDR,FEATNAMES`

### How to start over
```bash
# Delete state files to start fresh
rm ./tiger/.tiger_download_state.json
rm .tiger_import_state.json
rm .tiger_workflow_state.json

# Or keep them for resume capability
```

## Examples

### Example 1: California Only
```bash
python tools/tiger_download_and_import.py geocoder.db ./tiger \
    --states 06 --cleanup --verbose
```

### Example 2: Multiple States with Resume
```bash
# Start download and import
python tools/tiger_download_and_import.py geocoder.db ./tiger \
    --states 06,36,48 --cleanup --verbose

# If interrupted, resume
python tools/tiger_download_and_import.py geocoder.db ./tiger \
    --states 06,36,48 --resume --cleanup --verbose
```

### Example 3: Unreliable Connection
```bash
python tools/tiger_download_and_import.py geocoder.db ./tiger \
    --states 06 --parallel 2 --timeout 120 --verbose
```

### Example 4: Progressive Loading (Advanced)
```bash
# Terminal 1: Download
python census/zip_dl.py --states 06,36,48 --output ./tiger --verbose

# Terminal 2: Import as files arrive
python tools/tiger_import_duckdb.py geocoder.db ./tiger \
    --progressive --cleanup --state-file .import_state.json --verbose
```

## Getting Help

```bash
# See all options
python census/zip_dl.py --help
python tools/tiger_import_duckdb.py --help
python tools/tiger_download_and_import.py --help

# List available states
python census/zip_dl.py --list-states

# List available dataset types
python census/zip_dl.py --list-types
```

## More Information

- Full documentation: `DATABASE_BUILD_GUIDE.md`
- Tool details: `tools/README.md`
- Python API: `README_PYTHON.md`
