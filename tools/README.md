# TIGER/Line Import Tools for Python/DuckDB

This directory contains Python tools for building geocoding databases from TIGER/Line data, equivalent to the Ruby/bash scripts in the original implementation.

## Directory Structure

The Python implementation is organized as follows:

```
rb_geocoder/
├── geocoder_us/          # Core Python library (main geocoding package)
│   ├── __init__.py
│   ├── address.py        # Address parsing
│   ├── database.py       # DuckDB database interface
│   └── constants.py      # State codes, abbreviations
├── tools/                # Build and maintenance scripts
│   ├── tiger_import_duckdb.py
│   ├── tiger_download_and_import.py
│   └── rebuild_metaphones.py
├── census/               # Census data download utilities
│   └── zip_dl.py
├── examples/             # Example usage scripts
│   └── demo_python.py
└── test_geocoder_us.py  # Unit tests
```

**Note:** This organization is intentional and mirrors best practices:
- `geocoder_us/` - Installable Python package
- `tools/` - Build/maintenance utilities (not part of runtime package)
- `census/` - Data acquisition scripts
- `examples/` - Usage demonstrations

The scripts are already well-organized by purpose, so refactoring them into a single directory would reduce clarity.

## Tools Overview

### 1. `tiger_download_and_import.py` ⭐ NEW
**Unified workflow for downloading and importing TIGER/Line data.**

**Features:**
- Downloads TIGER/Line files with robust retry logic for 520/523 errors
- Progressively imports files into database as they are downloaded
- Tracks complete workflow state (download → extract → load)
- Resume capability for interrupted workflows
- Optional cleanup of ZIP files after import
- Single command for entire workflow

**Usage:**
```bash
# Download and import California
python tiger_download_and_import.py geocoder.duckdb /data/tiger2024/ \
    --states 06 --verbose

# Download and import multiple states with cleanup
python tiger_download_and_import.py geocoder.duckdb /data/tiger2024/ \
    --states 06,36,48 --cleanup --verbose

# Resume interrupted workflow
python tiger_download_and_import.py geocoder.duckdb /data/tiger2024/ \
    --states 06 --resume --verbose

# Custom parallelism and timeout
python tiger_download_and_import.py geocoder.duckdb /data/tiger2024/ \
    --states 06 --parallel 2 --timeout 90 --verbose
```

**Benefits:**
- No need to wait for all downloads before importing
- Saves time by processing files as they arrive
- Automatic retry and resume for reliability
- Tracks progress with JSON state files

### 2. `tiger_import_duckdb.py`
Imports TIGER/Line shapefiles into DuckDB database for geocoding.

**Enhanced Features:**
- Pure Python implementation (no bash/C dependencies)
- Uses DuckDB spatial extension to read shapefiles directly
- Automatic metaphone generation
- **Progressive loading**: Import files as they are downloaded
- **State tracking**: Resume interrupted imports
- **Cleanup option**: Remove ZIP files after successful import
- Parallel processing support
- Progress tracking

**Usage:**
```bash
# Import all counties from TIGER directory
python tiger_import_duckdb.py geocoder.duckdb /data/tiger2024/ --verbose

# Progressive loading with state tracking
python tiger_import_duckdb.py geocoder.duckdb /data/tiger2024/ \
    --progressive --state-file .import_state.json --verbose

# Import with automatic cleanup
python tiger_import_duckdb.py geocoder.duckdb /data/tiger2024/ \
    --progressive --cleanup --verbose

# Import specific counties (e.g., San Francisco, Santa Clara)
python tiger_import_duckdb.py geocoder.duckdb /data/tiger2024/ --counties 06075 06085 --verbose

# Resume interrupted import
python tiger_import_duckdb.py geocoder.duckdb /data/tiger2024/ \
    --state-file .import_state.json --verbose
```

**New Features:**
- `--progressive`: Enable progressive loading mode
- `--cleanup`: Remove ZIP files after successful import
- `--state-file`: Track import progress for resume capability

**Replaces:**
- `build/tiger_import` (bash script)
- `build/shp2sqlite` (C binary)
- `build/sql/create.sql`, `setup.sql`, `convert.sql`

### 3. `rebuild_metaphones.py`
Regenerates metaphone phonetic codes for all street and city names.

**Features:**
- Fast bulk updates using SQL
- Progress reporting
- Dry-run mode for testing
- Example output

**Usage:**
```bash
# Rebuild all metaphones with progress
python rebuild_metaphones.py geocoder.duckdb --verbose

# Preview without making changes
python rebuild_metaphones.py geocoder.duckdb --dry-run --verbose

# Quiet mode
python rebuild_metaphones.py geocoder.duckdb
```

**Replaces:**
- `bin/rebuild_metaphones` (Ruby script)

### 4. `export_duckdb_to_sqlite.py` ⭐ NEW
Exports DuckDB database to SQLite format compatible with the Ruby version.

**Features:**
- Converts all tables from DuckDB to SQLite
- Handles geometry format conversion (WKB → compressed format)
- Preserves metaphone codes and indexes
- Creates database compatible with Ruby `Geocoder::US::Database`
- Validates data integrity during export
- Progress reporting

**Usage:**
```bash
# Basic export
python export_duckdb_to_sqlite.py geocoder.duckdb geocoder.db --verbose

# Overwrite existing database
python export_duckdb_to_sqlite.py geocoder.duckdb geocoder.db --overwrite --verbose

# Quiet mode
python export_duckdb_to_sqlite.py geocoder.duckdb geocoder.db
```

**Geometry Conversion:**
The tool automatically converts geometry formats:
- **DuckDB**: WKB (Well-Known Binary) standard format
- **SQLite/Ruby**: Compressed format with coordinates as 4-byte signed integers (multiplied by 1,000,000)

This ensures full compatibility with the Ruby version's `unpack_geometry` method.

**Use Cases:**
- Migrating from Python/DuckDB back to Ruby/SQLite
- Creating SQLite databases for deployment where Ruby is required
- Testing database compatibility between Python and Ruby versions
- Distributing pre-built databases for Ruby users

## Prerequisites

```bash
pip install duckdb jellyfish
```

## Comparison with Ruby Version

### Advantages of Python/DuckDB Tools

1. **No Compilation Required**
   - Ruby: Requires compiling `shp2sqlite` C binary
   - Python: Pure Python, uses DuckDB spatial extension

2. **Simpler Dependencies**
   - Ruby: Requires sqlite3-ruby with custom patches, Text gem, bash utilities
   - Python: Just `duckdb` and `jellyfish` packages

3. **Native Shapefile Support**
   - Ruby: Needs `shp2sqlite` to convert to SQL statements
   - Python: DuckDB reads shapefiles directly with `ST_Read()`

4. **Better Performance**
   - DuckDB uses columnar storage and SIMD
   - Parallel import processing
   - Faster bulk updates

5. **Cross-Platform**
   - Ruby: bash scripts need Unix-like environment
   - Python: Works on Windows, Mac, Linux

### Feature Parity

| Feature | Ruby | Python/DuckDB | Status |
|---------|------|---------------|--------|
| Import TIGER/Line shapefiles | ✅ | ✅ | Complete |
| Generate metaphones | ✅ | ✅ | Complete |
| Build indexes | ✅ | ✅ | Complete |
| Export to SQLite | ❌ | ✅ | New |
| Progress reporting | ⚠️ | ✅ | Improved |
| Parallel processing | ❌ | ✅ | New |
| Dry-run mode | ❌ | ✅ | New |
| Progressive loading | ❌ | ✅ | New |
| Resume capability | ❌ | ✅ | New |
| State tracking | ❌ | ✅ | New |
| Auto cleanup | ❌ | ✅ | New |

## Detailed Usage

### Downloading TIGER/Line Data

Download TIGER/Line data using the enhanced downloader with retry logic:

```bash
# Download for specific state (e.g., California)
python ../census/zip_dl.py --states 06 --output /data/tiger2024/

# Download with resume capability (handles 520/523 errors)
python ../census/zip_dl.py --states 06 --output /data/tiger2024/ --resume --verbose

# Download with custom timeout and parallelism
python ../census/zip_dl.py --states 06 --output /data/tiger2024/ \
    --timeout 90 --parallel 2 --verbose

# Download for multiple states
python ../census/zip_dl.py --states 06,36,48 --output /data/tiger2024/

# Download all states (large!)
python ../census/zip_dl.py --output /data/tiger2024/
```

**Enhanced Download Features:**
- **Automatic Retry**: 8 retry attempts with exponential backoff for 520/523/524 errors
- **Resume Support**: Skip already downloaded files with `--resume`
- **State Tracking**: Progress saved to `.tiger_download_state.json`
- **Timeout Control**: Configure timeout with `--timeout` (default: 60s)
- **Reliability**: Validates file sizes and retries corrupted downloads

### Building a Complete Database

```bash
# Step 1: Import TIGER/Line data
python tiger_import_duckdb.py geocoder.duckdb /data/tiger2024/ --verbose

# Step 2: (Optional) Rebuild metaphones if data changes
python rebuild_metaphones.py geocoder.duckdb --verbose

# Step 3: Test the database
python ../examples/demo_python.py geocoder.duckdb
```

### Incremental Updates

To add more counties to an existing database:

```bash
# Import additional counties
python tiger_import_duckdb.py geocoder.duckdb /data/tiger2024/ \
    --counties 12086 12095 --verbose

# Rebuild metaphones for new data
python rebuild_metaphones.py geocoder.duckdb --verbose
```

### Memory and Performance Tuning

For large imports, you may want to adjust DuckDB settings:

```python
# Edit tiger_import_duckdb.py, in create_database_schema():
conn.execute("SET memory_limit='4GB';")  # Increase for large imports
conn.execute("SET threads TO 8;")        # Use more CPU cores
```

## Database Schema

The tools create the following tables:

### `place` Table
Stores city/place information with ZIP codes.

| Column | Type | Description |
|--------|------|-------------|
| zip | VARCHAR | ZIP code (primary key) |
| city | VARCHAR | City name |
| state | VARCHAR(2) | State abbreviation |
| city_phone | VARCHAR | Metaphone of city name |
| fips_county | VARCHAR | County FIPS code |
| priority | INTEGER | Priority for disambiguation |

### `feature` Table
Stores street feature information.

| Column | Type | Description |
|--------|------|-------------|
| fid | INTEGER | Feature ID (primary key) |
| street | VARCHAR | Street name |
| street_phone | VARCHAR | Metaphone of street name |
| suftyp | VARCHAR | Suffix type (St, Ave, etc.) |
| sufdir | VARCHAR | Suffix direction (N, S, etc.) |
| predir | VARCHAR | Prefix direction |
| zip | VARCHAR | ZIP code |
| paflag | VARCHAR(1) | Primary address flag |

### `edge` Table
Stores street geometry (line segments).

| Column | Type | Description |
|--------|------|-------------|
| tlid | BIGINT | TIGER/Line ID (primary key) |
| geometry | BLOB | Line geometry (WKB format) |

### `range` Table
Stores address ranges for street segments.

| Column | Type | Description |
|--------|------|-------------|
| tlid | BIGINT | TIGER/Line ID |
| side | VARCHAR(1) | Side of street (L/R) |
| fromhn | INTEGER | From house number |
| tohn | INTEGER | To house number |
| prenum | VARCHAR | Number prefix |

### `feature_edge` Table
Links features to edges (many-to-many).

| Column | Type | Description |
|--------|------|-------------|
| fid | INTEGER | Feature ID |
| tlid | BIGINT | TIGER/Line ID |

## Troubleshooting

### DuckDB Spatial Extension Not Found

```
Error: Extension "spatial" is not loaded
```

**Solution:**
```bash
# Install spatial extension manually
python -c "import duckdb; conn = duckdb.connect(':memory:'); conn.execute('INSTALL spatial;')"
```

### Out of Memory

If you get out of memory errors during import:

1. **Reduce memory usage:**
   ```python
   conn.execute("SET memory_limit='2GB';")
   ```

2. **Import fewer counties at a time:**
   ```bash
   python tiger_import_duckdb.py geocoder.duckdb /data/tiger/ --counties 06001
   python tiger_import_duckdb.py geocoder.duckdb /data/tiger/ --counties 06075
   ```

3. **Use swap space** on Linux

### Shapefile Read Errors

If shapefiles can't be read:

1. **Verify TIGER data:** Check that ZIP files contain `.shp`, `.shx`, `.dbf` files
2. **Check DuckDB spatial:** Ensure spatial extension is loaded
3. **Try manual extraction:** Unzip files and point to directory

### Slow Import

For faster imports:

1. **Disable fsync during import:**
   ```python
   conn.execute("SET force_checkpoint TO true;")
   ```

2. **Use SSD storage** for database

3. **Increase memory limit:**
   ```python
   conn.execute("SET memory_limit='8GB';")
   ```

## Contributing

To improve these tools:

1. **Add support for more TIGER/Line files** (FACES, etc.)
2. **Implement full ETL pipeline** from convert.sql
3. **Add validation checks** for imported data
4. **Parallelize county processing**
5. **Add resume capability** for interrupted imports

## License

GNU General Public License v3.0 or later.

Based on original Geocoder::US by Schuyler Erle.
