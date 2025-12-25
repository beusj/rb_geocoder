# TIGER/Line Download and Import Consolidation Summary

## Overview

The download and import logic has been consolidated to provide a single, unified entry point with improved defaults for easier use.

## Key Changes

### 1. Default State Tracking: DuckDB

**Before:** State tracking used JSON files by default (with `--use-db` to opt-in to DuckDB)

**After:** State tracking uses DuckDB by default (with `--no-use-db` to opt-out to JSON)

**Benefits:**
- Better scalability for tracking thousands of files
- Concurrent access from multiple processes
- Rich SQL querying capabilities
- Better performance for large downloads

**Usage:**
```bash
# Uses DuckDB by default
python census/zip_dl.py --states 06

# Use JSON if DuckDB is not available or not desired
python census/zip_dl.py --states 06 --no-use-db
```

### 2. Default Output Directory: census/tiger

**Before:** Default output was `./tiger` or required explicit `--output` argument

**After:** Default output is `census/tiger`

**Benefits:**
- Consistent location for TIGER/Line data
- Cleaner project structure
- No need to specify output directory for typical use

**Usage:**
```bash
# Downloads to census/tiger by default
python census/zip_dl.py --states 06

# Can still specify custom location
python census/zip_dl.py --states 06 --output /data/tiger
```

### 3. Unified Entry Point: tiger_download_and_import.py

**Before:** Two separate steps required:
1. Download with `census/zip_dl.py`
2. Import with `tools/tiger_import_duckdb.py`

**After:** Single unified tool combines both steps:
- `tools/tiger_download_and_import.py`

**Benefits:**
- Progressive import (import files as they download)
- Single command for complete workflow
- Automatic state tracking across both phases
- Optional cleanup of ZIP files after import

**Usage:**
```bash
# Complete workflow in one command (defaults to census/tiger)
python tools/tiger_download_and_import.py geocoder.duckdb --states 06 --verbose

# Specify custom output directory
python tools/tiger_download_and_import.py geocoder.duckdb /data/tiger --states 06

# Progressive import with cleanup
python tools/tiger_download_and_import.py geocoder.duckdb --states 06 --cleanup
```

## Migration Guide

### If you were using:

**Old way:**
```bash
# Download
python census/zip_dl.py --states 06 --output /data/tiger

# Import
python tools/tiger_import_duckdb.py geocoder.duckdb /data/tiger --verbose
```

**New way (recommended):**
```bash
# Combined workflow (defaults to census/tiger)
python tools/tiger_download_and_import.py geocoder.duckdb --states 06 --verbose

# Or with custom output
python tools/tiger_download_and_import.py geocoder.duckdb /data/tiger --states 06 --verbose
```

### If you prefer the old defaults:

You can still use the old behavior:

```bash
# Use JSON state tracking
python census/zip_dl.py --states 06 --no-use-db

# Use custom output directory
python census/zip_dl.py --states 06 --output ./tiger
```

## Command Reference

### census/zip_dl.py

Download TIGER/Line files with retry logic.

**Key Arguments:**
- `--output DIR` - Output directory (default: `census/tiger`)
- `--states CODES` - State FIPS codes (comma-separated)
- `--use-db` - Use DuckDB state tracking (default: enabled)
- `--no-use-db` - Use JSON state tracking instead
- `--resume` - Resume interrupted downloads
- `--show-status` - Show download progress

**Examples:**
```bash
# Basic usage (defaults: census/tiger, DuckDB)
python census/zip_dl.py --states 06

# Multiple states with resume
python census/zip_dl.py --states 06,36,48 --resume

# Check download status
python census/zip_dl.py --show-status

# Use JSON state tracking
python census/zip_dl.py --states 06 --no-use-db
```

### tools/tiger_download_and_import.py

Unified download and import workflow.

**Key Arguments:**
- `database` - Path to DuckDB database (required)
- `output_dir` - Output directory (optional, default: `census/tiger`)
- `--states CODES` - State FIPS codes (comma-separated)
- `--use-db` - Use DuckDB state tracking (default: enabled)
- `--no-use-db` - Use JSON state tracking instead
- `--cleanup` - Remove ZIP files after import
- `--resume` - Resume interrupted workflow

**Examples:**
```bash
# Basic usage (defaults: census/tiger, DuckDB)
python tools/tiger_download_and_import.py geocoder.duckdb --states 06

# With custom output
python tools/tiger_download_and_import.py geocoder.duckdb /data/tiger --states 06

# Progressive with cleanup
python tools/tiger_download_and_import.py geocoder.duckdb --states 06 --cleanup

# Resume interrupted workflow
python tools/tiger_download_and_import.py geocoder.duckdb --resume
```

### tools/tiger_import_duckdb.py

Import TIGER/Line files into DuckDB (can still be used separately).

**Key Arguments:**
- `database` - Path to DuckDB database (required)
- `tiger_dir` - Directory with TIGER/Line files (required)
- `--progressive` - Import files as they appear
- `--cleanup` - Remove ZIP files after import
- `--state-file FILE` - Track import state

**Examples:**
```bash
# Import from default location
python tools/tiger_import_duckdb.py geocoder.duckdb census/tiger --verbose

# Progressive import with cleanup
python tools/tiger_import_duckdb.py geocoder.duckdb /data/tiger \
    --progressive --cleanup --verbose
```

## Testing

All changes have been tested and verified:

1. **Unit Tests:** `test_consolidation.py` - Tests DuckDB/JSON backend selection
2. **Integration Tests:** `test_download_enhancements.py` - Tests download state tracking
3. **Manual Verification:** Argument parsing and default values confirmed

Run tests:
```bash
pytest test_consolidation.py -v
pytest test_download_enhancements.py -v
```

## Backward Compatibility

All changes are backward compatible:
- Old command-line arguments still work
- JSON state tracking available with `--no-use-db`
- Custom output directories supported with `--output`
- Separate download and import scripts still functional

## Documentation Updates

Updated files:
- `census/README.md` - New default examples
- `tools/README.md` - Consolidated workflow documentation
- `DATABASE_BUILD_GUIDE.md` - Updated throughout with new defaults

## Benefits Summary

1. **Simpler Commands:** Fewer arguments needed for typical use
2. **Better Performance:** DuckDB state tracking scales better
3. **Single Entry Point:** `tiger_download_and_import.py` combines download and import
4. **Progressive Import:** Files imported as they download (no waiting)
5. **Consistent Defaults:** `census/tiger` output, DuckDB state tracking
6. **Backward Compatible:** All old usage patterns still work

## Questions?

See the updated documentation:
- [Tools README](tools/README.md) - Detailed tool documentation
- [Database Build Guide](DATABASE_BUILD_GUIDE.md) - Complete workflow guide
- [Census README](census/README.md) - Download script examples
