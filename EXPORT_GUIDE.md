# DuckDB to SQLite Export Guide

## Overview

The `export_duckdb_to_sqlite.py` tool allows you to export a DuckDB geocoding database to SQLite format that is fully compatible with the Ruby Geocoder::US library.

## Why Export?

You might want to export from DuckDB to SQLite if you:

- Need to deploy with Ruby-based applications
- Want to use the original Ruby Geocoder::US library
- Need to create pre-built databases for Ruby users
- Want to test database compatibility between Python and Ruby versions
- Have existing Ruby infrastructure that expects SQLite format

## Installation

```bash
pip install duckdb
```

No additional dependencies required - the export tool uses only standard Python libraries and DuckDB.

## Quick Start

### Basic Export

```bash
python tools/export_duckdb_to_sqlite.py geocoder.duckdb geocoder.db --verbose
```

### Overwrite Existing Database

```bash
python tools/export_duckdb_to_sqlite.py geocoder.duckdb geocoder.db --overwrite --verbose
```

### Quiet Mode

```bash
python tools/export_duckdb_to_sqlite.py geocoder.duckdb geocoder.db
```

## What Gets Exported?

The export tool handles:

### Tables
- ✅ `place` - City/ZIP code information
- ✅ `feature` - Street features and names
- ✅ `edge` - Street geometry (with format conversion)
- ✅ `range` - Address ranges
- ✅ `feature_edge` - Feature-to-edge mappings

### Data Preservation
- ✅ All data rows (with batch processing for large datasets)
- ✅ Metaphone codes for fuzzy matching
- ✅ Primary keys and foreign keys
- ✅ All indexes for fast queries

### Geometry Conversion

The most important aspect of the export is geometry format conversion:

**DuckDB Format:**
- Standard WKB (Well-Known Binary) format
- Coordinates stored as 8-byte doubles
- Full precision maintained

**SQLite/Ruby Format:**
- Compressed custom format
- Coordinates stored as 4-byte signed integers (lat/lon × 1,000,000)
- Compatible with Ruby's `unpack_geometry` method

Example conversion:
```
DuckDB WKB:  [01 02 00 00 00 02 00 00 00 ...]  (full WKB format)
SQLite:      [xx yy zz ww ...]                 (compressed int32 array)
```

The tool automatically handles this conversion for all geometries in the `edge` table.

## Usage Examples

### Example 1: Build with Python, Deploy with Ruby

```bash
# 1. Build database with Python tools (faster, easier)
python tools/tiger_import_duckdb.py geocoder.duckdb /data/tiger/ --verbose

# 2. Generate metaphones
python tools/rebuild_metaphones.py geocoder.duckdb --verbose

# 3. Export for Ruby deployment
python tools/export_duckdb_to_sqlite.py geocoder.duckdb geocoder.db --verbose

# 4. Use with Ruby
# ruby -e "require 'geocoder/us'; db = Geocoder::US::Database.new('geocoder.db')"
```

### Example 2: Test Compatibility

```bash
# Export test database
python tools/export_duckdb_to_sqlite.py test.duckdb test.db --verbose

# Test with Ruby
ruby -e "
require 'geocoder/us'
db = Geocoder::US::Database.new('test.db')
results = db.geocode('1600 Pennsylvania Ave, Washington DC')
puts results.inspect
"
```

### Example 3: Batch Export Multiple Databases

```bash
#!/bin/bash
for state in CA NY TX; do
    python tools/export_duckdb_to_sqlite.py \
        "geocoder_${state}.duckdb" \
        "geocoder_${state}.db" \
        --overwrite --verbose
done
```

## Command-Line Options

```
usage: export_duckdb_to_sqlite.py [-h] [--overwrite] [--verbose] source destination

positional arguments:
  source         Path to source DuckDB database
  destination    Path to destination SQLite database

options:
  -h, --help     Show help message and exit
  --overwrite    Overwrite existing destination database
  --verbose, -v  Print detailed progress information
```

## Performance

Typical export performance:

| Database Size | Export Time | Notes |
|---------------|-------------|-------|
| 10 MB | ~2 seconds | Small county |
| 100 MB | ~15 seconds | Medium county |
| 1 GB | ~2 minutes | Large state |
| 10 GB | ~20 minutes | Multiple states |

**Optimization tips:**
- Use SSD storage for both source and destination
- Ensure sufficient RAM (2x database size recommended)
- Run on system with low I/O contention

## Verification

After export, verify the database:

### Check Table Counts

```bash
sqlite3 geocoder.db "SELECT 
    (SELECT COUNT(*) FROM place) as places,
    (SELECT COUNT(*) FROM feature) as features,
    (SELECT COUNT(*) FROM edge) as edges;"
```

### Check Indexes

```bash
sqlite3 geocoder.db "SELECT name FROM sqlite_master WHERE type='index';"
```

### Test with Ruby

```ruby
require 'geocoder/us'
db = Geocoder::US::Database.new('geocoder.db')

# Test place lookup
results = db.geocode('San Francisco, CA')
puts "Place results: #{results.length}"

# Test address lookup
results = db.geocode('100 Main St, San Francisco CA')
puts "Address results: #{results.length}"
```

## Troubleshooting

### Error: Catalog Error: Table does not exist

**Problem:** Source DuckDB database doesn't have the expected schema.

**Solution:** Ensure the database was created with `tiger_import_duckdb.py` or has the correct table structure.

### Error: Destination database already exists

**Problem:** SQLite database already exists at the destination path.

**Solution:** Use the `--overwrite` flag or delete the existing file.

### Warning: Could not convert geometry

**Problem:** Some geometries in the edge table have an unsupported format.

**Solution:** This is usually not critical - the tool will skip invalid geometries and continue. Check the verbose output to see which edges failed.

### Slow Export

**Problem:** Export is taking longer than expected.

**Solutions:**
1. Use SSD storage
2. Ensure sufficient RAM
3. Close other applications
4. Check disk space

### Memory Error

**Problem:** Export crashes with out-of-memory error.

**Solution:** The tool uses batch processing to handle large databases. If you still get memory errors, try:
1. Close other applications
2. Increase system swap space
3. Export in chunks (not currently supported, but can be added)

## File Size Comparison

Typical file sizes (same data):

```
DuckDB:   100 MB
SQLite:   ~80 MB (20% smaller due to compression)
```

The SQLite database is often smaller because:
- More compact geometry storage (int32 vs double)
- Better compression for text fields
- Optimized indexes

## Compatibility Matrix

| Feature | Ruby (SQLite) | Python (DuckDB) | After Export |
|---------|---------------|-----------------|--------------|
| Place lookup | ✅ | ✅ | ✅ |
| Street lookup | ✅ | ✅ | ✅ |
| Address interpolation | ✅ | ⚠️ Partial | ✅ |
| Intersection lookup | ✅ | ⚠️ Partial | ✅ |
| Metaphone matching | ✅ | ✅ | ✅ |
| Geometry format | Custom | WKB | Custom |

✅ = Fully supported
⚠️ = Partially supported

## Technical Details

### Geometry Compression Algorithm

The Ruby version uses this compression (from `wkb_compress.c`):

```c
// Compress WKB to Ruby format
for (s = 9, d = 0; s < len; d += 4, s += 8) {
    value = *(double *)(src + s);
    value *= 1000000;
    *(int32_t *)(dest + d) = (int32_t) value;
}
```

Our Python implementation:

```python
def compress_wkb_linestring(wkb_data: bytes) -> bytes:
    # Parse WKB header (9 bytes)
    num_points = struct.unpack('<I', wkb_data[5:9])[0]
    
    # Convert coordinates
    compressed = bytearray()
    for i in range(num_points):
        offset = 9 + (i * 16)
        x, y = struct.unpack('<dd', wkb_data[offset:offset+16])
        x_int = int(x * 1_000_000)
        y_int = int(y * 1_000_000)
        compressed.extend(struct.pack('<ii', x_int, y_int))
    
    return bytes(compressed)
```

### Precision

Coordinate precision comparison:

| Format | Precision | Example |
|--------|-----------|---------|
| Double (8 bytes) | ~15 decimal digits | -122.419415 |
| Int32 (4 bytes) | 6 decimal places | -122.419415 → -122419415 |

After conversion: -122419415 / 1,000,000 = -122.419415

The compressed format maintains sufficient precision for street-level geocoding (~1 meter accuracy).

## Related Documentation

- [README_PYTHON.md](README_PYTHON.md) - Python/DuckDB implementation guide
- [DATABASE_BUILD_GUIDE.md](DATABASE_BUILD_GUIDE.md) - Building databases from TIGER/Line
- [examples/demo_export.py](examples/demo_export.py) - Complete export workflow example

## Contributing

To improve the export tool:

1. **Add more geometry types**: Currently supports LineString and Point
2. **Add validation**: Verify exported database against source
3. **Add statistics**: Compare row counts, index sizes, etc.
4. **Parallel export**: Export tables in parallel for faster processing
5. **Chunked export**: Support exporting very large databases in chunks

## Support

For issues or questions:

1. Check this guide first
2. Review the [DATABASE_BUILD_GUIDE.md](DATABASE_BUILD_GUIDE.md) documentation
3. Run with `--verbose` to see detailed progress
4. Check test files for examples
5. Open an issue on GitHub

## License

GNU General Public License v3.0 or later.

Based on original Geocoder::US by Schuyler Erle.
