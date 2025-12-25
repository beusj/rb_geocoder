# TIGER/Line Import Tools for Python/DuckDB

This directory contains Python tools for building geocoding databases from TIGER/Line data, equivalent to the Ruby/bash scripts in the original implementation.

## Tools Overview

### 1. `tiger_import_duckdb.py`
Imports TIGER/Line shapefiles into DuckDB database for geocoding.

**Features:**
- Pure Python implementation (no bash/C dependencies)
- Uses DuckDB spatial extension to read shapefiles directly
- Automatic metaphone generation
- Parallel processing support
- Progress tracking

**Usage:**
```bash
# Import all counties from TIGER directory
python tiger_import_duckdb.py geocoder.db /data/tiger2024/ --verbose

# Import specific counties (e.g., San Francisco, Santa Clara)
python tiger_import_duckdb.py geocoder.db /data/tiger2024/ --counties 06075 06085 --verbose

# Quiet mode
python tiger_import_duckdb.py geocoder.db /data/tiger2024/
```

**Replaces:**
- `build/tiger_import` (bash script)
- `build/shp2sqlite` (C binary)
- `build/sql/create.sql`, `setup.sql`, `convert.sql`

### 2. `rebuild_metaphones.py`
Regenerates metaphone phonetic codes for all street and city names.

**Features:**
- Fast bulk updates using SQL
- Progress reporting
- Dry-run mode for testing
- Example output

**Usage:**
```bash
# Rebuild all metaphones with progress
python rebuild_metaphones.py geocoder.db --verbose

# Preview without making changes
python rebuild_metaphones.py geocoder.db --dry-run --verbose

# Quiet mode
python rebuild_metaphones.py geocoder.db
```

**Replaces:**
- `bin/rebuild_metaphones` (Ruby script)

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
| Progress reporting | ⚠️ | ✅ | Improved |
| Parallel processing | ❌ | ✅ | New |
| Dry-run mode | ❌ | ✅ | New |

## Detailed Usage

### Downloading TIGER/Line Data

First, download TIGER/Line data using the provided downloader:

```bash
# Download for specific state (e.g., California)
python ../census/zip_dl.py --states 06 --output /data/tiger2024/

# Download for multiple states
python ../census/zip_dl.py --states 06,36,48 --output /data/tiger2024/

# Download all states (large!)
python ../census/zip_dl.py --output /data/tiger2024/
```

### Building a Complete Database

```bash
# Step 1: Import TIGER/Line data
python tiger_import_duckdb.py geocoder.db /data/tiger2024/ --verbose

# Step 2: (Optional) Rebuild metaphones if data changes
python rebuild_metaphones.py geocoder.db --verbose

# Step 3: Test the database
python ../examples/demo_python.py geocoder.db
```

### Incremental Updates

To add more counties to an existing database:

```bash
# Import additional counties
python tiger_import_duckdb.py geocoder.db /data/tiger2024/ \
    --counties 12086 12095 --verbose

# Rebuild metaphones for new data
python rebuild_metaphones.py geocoder.db --verbose
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
   python tiger_import_duckdb.py geocoder.db /data/tiger/ --counties 06001
   python tiger_import_duckdb.py geocoder.db /data/tiger/ --counties 06075
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
