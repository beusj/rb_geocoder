#!/usr/bin/env python3
"""
Export DuckDB TIGER/Line database to SQLite format compatible with Ruby version.

This script exports a DuckDB geocoding database to SQLite format that can be
used with the original Ruby Geocoder::US library. It handles:
- Schema conversion
- Geometry format conversion (WKB → compressed format)
- Index creation
- Metaphone preservation

Usage:
    python export_duckdb_to_sqlite.py <source_duckdb> <dest_sqlite> [options]

Example:
    python export_duckdb_to_sqlite.py geocoder.duckdb geocoder.db --verbose
    python export_duckdb_to_sqlite.py geocoder.duckdb geocoder.db --overwrite
"""

import argparse
import sqlite3
import duckdb
import struct
import sys
from pathlib import Path
from typing import List, Tuple, Optional


def compress_wkb_linestring(wkb_data: bytes) -> bytes:
    """
    Compress WKB LineString to Ruby-compatible format.
    
    The Ruby version stores geometries as little-endian 4-byte signed integers,
    where each coordinate is multiplied by 1,000,000 to preserve precision.
    
    WKB LineString format:
    - Byte 0: Byte order (01 = little-endian)
    - Bytes 1-4: Geometry type (02000000 = LineString)
    - Bytes 5-8: Number of points
    - Bytes 9+: Coordinate pairs (x, y) as doubles
    
    Args:
        wkb_data: WKB-encoded LineString geometry
        
    Returns:
        Compressed geometry as bytes
    """
    if not wkb_data or len(wkb_data) < 9:
        return b''
    
    # Parse WKB header
    byte_order = wkb_data[0]
    if byte_order != 1:  # Only little-endian supported
        raise ValueError("Only little-endian WKB is supported")
    
    geom_type = struct.unpack('<I', wkb_data[1:5])[0]
    if geom_type not in (2, 1002, 3002):  # LineString variants
        # For Point geometries, convert to 2-point line
        if geom_type in (1, 1001, 3001):  # Point variants
            x, y = struct.unpack('<dd', wkb_data[5:21])
            # Create compressed format with single point (repeated)
            x_int = int(x * 1_000_000)
            y_int = int(y * 1_000_000)
            return struct.pack('<ii', x_int, y_int)
        raise ValueError(f"Unsupported geometry type: {geom_type}")
    
    num_points = struct.unpack('<I', wkb_data[5:9])[0]
    
    # Extract and compress coordinates
    compressed = bytearray()
    offset = 9
    
    for _ in range(num_points):
        if offset + 16 > len(wkb_data):
            break
        
        x, y = struct.unpack('<dd', wkb_data[offset:offset+16])
        
        # Convert to int32 (multiply by 1,000,000 for precision)
        x_int = int(x * 1_000_000)
        y_int = int(y * 1_000_000)
        
        # Pack as little-endian 32-bit signed integers
        compressed.extend(struct.pack('<ii', x_int, y_int))
        
        offset += 16
    
    return bytes(compressed)


def create_sqlite_schema(conn: sqlite3.Connection):
    """Create SQLite database schema compatible with Ruby version."""
    
    cursor = conn.cursor()
    
    # Create place table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS place (
            zip TEXT PRIMARY KEY,
            city TEXT,
            state TEXT,
            city_phone TEXT,
            fips_county TEXT,
            fips_class TEXT,
            fips_place TEXT,
            priority INTEGER
        )
    """)
    
    # Create feature table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS feature (
            fid INTEGER PRIMARY KEY,
            street TEXT,
            street_phone TEXT,
            suftyp TEXT,
            sufdir TEXT,
            predir TEXT,
            pretyp TEXT,
            zip TEXT,
            paflag TEXT,
            city TEXT,
            state TEXT
        )
    """)
    
    # Create edge table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS edge (
            tlid INTEGER PRIMARY KEY,
            geometry BLOB
        )
    """)
    
    # Create range table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS "range" (
            tlid INTEGER,
            side TEXT,
            fromhn INTEGER,
            tohn INTEGER,
            prenum TEXT,
            PRIMARY KEY (tlid, side, fromhn, tohn)
        )
    """)
    
    # Create feature_edge table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS feature_edge (
            fid INTEGER,
            tlid INTEGER,
            PRIMARY KEY (fid, tlid)
        )
    """)
    
    conn.commit()


def create_sqlite_indexes(conn: sqlite3.Connection, verbose: bool = False):
    """Create indexes for SQLite database."""
    
    cursor = conn.cursor()
    
    indexes = [
        ("CREATE INDEX IF NOT EXISTS place_city_idx ON place (city)", "place.city"),
        ("CREATE INDEX IF NOT EXISTS place_state_idx ON place (state)", "place.state"),
        ("CREATE INDEX IF NOT EXISTS place_city_phone_idx ON place (city_phone)", "place.city_phone"),
        ("CREATE INDEX IF NOT EXISTS feature_zip_idx ON feature (zip)", "feature.zip"),
        ("CREATE INDEX IF NOT EXISTS feature_street_phone_idx ON feature (street_phone)", "feature.street_phone"),
        ("CREATE INDEX IF NOT EXISTS range_tlid_idx ON \"range\" (tlid)", "range.tlid"),
        ("CREATE INDEX IF NOT EXISTS feature_edge_fid_idx ON feature_edge (fid)", "feature_edge.fid"),
        ("CREATE INDEX IF NOT EXISTS feature_edge_tlid_idx ON feature_edge (tlid)", "feature_edge.tlid"),
    ]
    
    for sql, name in indexes:
        if verbose:
            print(f"  Creating index on {name}...")
        cursor.execute(sql)
    
    conn.commit()
    
    if verbose:
        print("✓ Indexes created")


def export_table_simple(duck_conn: duckdb.DuckDBPyConnection, 
                       sqlite_conn: sqlite3.Connection,
                       table_name: str,
                       verbose: bool = False) -> int:
    """
    Export a simple table (no geometry) from DuckDB to SQLite.
    
    Args:
        duck_conn: DuckDB connection
        sqlite_conn: SQLite connection
        table_name: Name of table to export
        verbose: Print progress
        
    Returns:
        Number of rows exported
    """
    if verbose:
        print(f"\nExporting table '{table_name}'...")
    
    # Get row count
    result = duck_conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()
    if not result:
        if verbose:
            print(f"  Table '{table_name}' is empty or doesn't exist")
        return 0
    
    row_count = result[0]
    
    if row_count == 0:
        if verbose:
            print(f"  Table '{table_name}' is empty")
        return 0
    
    # Get column names
    columns_result = duck_conn.execute(
        f"SELECT column_name FROM information_schema.columns WHERE table_name = '{table_name}'"
    ).fetchall()
    
    if not columns_result:
        if verbose:
            print(f"  Warning: Could not get columns for table '{table_name}'")
        return 0
    
    columns = [col[0] for col in columns_result]
    
    # Use DuckDB to export directly to SQLite
    # This is more efficient than row-by-row insertion
    try:
        # Read all data from DuckDB
        data = duck_conn.execute(f"SELECT * FROM {table_name}").fetchall()
        
        # Insert into SQLite
        sqlite_cursor = sqlite_conn.cursor()
        placeholders = ','.join(['?' for _ in columns])
        
        # Quote table name if it's a reserved word (like "range")
        table_name_quoted = f'"{table_name}"' if table_name == "range" else table_name
        
        sql = f"INSERT INTO {table_name_quoted} ({','.join(columns)}) VALUES ({placeholders})"
        
        # Batch insert
        batch_size = 1000
        for i in range(0, len(data), batch_size):
            batch = data[i:i+batch_size]
            sqlite_cursor.executemany(sql, batch)
            
            if verbose and (i + batch_size) % 10000 == 0:
                print(f"  Inserted {min(i + batch_size, len(data))}/{len(data)} rows...")
        
        sqlite_conn.commit()
        
        if verbose:
            print(f"✓ Exported {len(data)} rows from '{table_name}'")
        
        return len(data)
        
    except Exception as e:
        if verbose:
            print(f"  Error exporting table '{table_name}': {e}")
        return 0


def export_edge_table(duck_conn: duckdb.DuckDBPyConnection,
                     sqlite_conn: sqlite3.Connection,
                     verbose: bool = False) -> int:
    """
    Export edge table with geometry conversion from DuckDB to SQLite.
    
    Args:
        duck_conn: DuckDB connection
        sqlite_conn: SQLite connection
        verbose: Print progress
        
    Returns:
        Number of rows exported
    """
    if verbose:
        print("\nExporting table 'edge' with geometry conversion...")
    
    # Check if table exists and has data
    result = duck_conn.execute("SELECT COUNT(*) FROM edge").fetchone()
    if not result or result[0] == 0:
        if verbose:
            print("  Table 'edge' is empty or doesn't exist")
        return 0
    
    row_count = result[0]
    
    # Export edges with geometry conversion
    sqlite_cursor = sqlite_conn.cursor()
    
    # Process in batches
    batch_size = 1000
    total_exported = 0
    errors = 0
    
    for offset in range(0, row_count, batch_size):
        edges = duck_conn.execute(
            f"SELECT tlid, geometry FROM edge LIMIT {batch_size} OFFSET {offset}"
        ).fetchall()
        
        batch_data = []
        for tlid, geom_wkb in edges:
            if geom_wkb is None:
                # Skip edges without geometry
                continue
            
            try:
                # Convert WKB to compressed format
                compressed_geom = compress_wkb_linestring(geom_wkb)
                batch_data.append((tlid, compressed_geom))
            except Exception as e:
                errors += 1
                if verbose and errors <= 10:
                    print(f"  Warning: Could not convert geometry for TLID {tlid}: {e}")
        
        if batch_data:
            sqlite_cursor.executemany(
                "INSERT INTO edge (tlid, geometry) VALUES (?, ?)",
                batch_data
            )
            total_exported += len(batch_data)
        
        if verbose and (offset + batch_size) % 10000 == 0:
            print(f"  Processed {min(offset + batch_size, row_count)}/{row_count} edges...")
    
    sqlite_conn.commit()
    
    if verbose:
        print(f"✓ Exported {total_exported} edges")
        if errors > 0:
            print(f"  Warning: {errors} edges could not be converted")
    
    return total_exported


def export_duckdb_to_sqlite(source_path: str, dest_path: str, 
                            overwrite: bool = False, verbose: bool = False) -> int:
    """
    Export DuckDB database to SQLite format compatible with Ruby version.
    
    Args:
        source_path: Path to source DuckDB database
        dest_path: Path to destination SQLite database
        overwrite: Overwrite existing SQLite database
        verbose: Print progress information
        
    Returns:
        0 on success, 1 on error
    """
    source = Path(source_path)
    dest = Path(dest_path)
    
    # Validate source
    if not source.exists():
        print(f"Error: Source database not found: {source_path}")
        return 1
    
    # Check destination
    if dest.exists() and not overwrite:
        print(f"Error: Destination database already exists: {dest_path}")
        print("Use --overwrite to replace it")
        return 1
    
    if dest.exists() and overwrite:
        if verbose:
            print(f"Removing existing database: {dest_path}")
        dest.unlink()
    
    try:
        # Connect to databases
        if verbose:
            print(f"Opening source database: {source_path}")
        duck_conn = duckdb.connect(str(source), read_only=True)
        
        if verbose:
            print(f"Creating destination database: {dest_path}")
        sqlite_conn = sqlite3.connect(str(dest))
        
        # Create schema
        if verbose:
            print("\nCreating SQLite schema...")
        create_sqlite_schema(sqlite_conn)
        if verbose:
            print("✓ Schema created")
        
        # Export tables
        tables_exported = {}
        
        # Export simple tables
        for table in ['place', 'feature', 'range', 'feature_edge']:
            count = export_table_simple(duck_conn, sqlite_conn, table, verbose)
            tables_exported[table] = count
        
        # Export edge table with geometry conversion
        count = export_edge_table(duck_conn, sqlite_conn, verbose)
        tables_exported['edge'] = count
        
        # Create indexes
        if verbose:
            print("\nCreating indexes...")
        create_sqlite_indexes(sqlite_conn, verbose)
        
        # Optimize database
        if verbose:
            print("\nOptimizing database...")
        sqlite_conn.execute("VACUUM")
        sqlite_conn.execute("ANALYZE")
        
        # Close connections
        duck_conn.close()
        sqlite_conn.close()
        
        # Print summary
        if verbose:
            print("\n" + "="*70)
            print("Export Summary")
            print("="*70)
            for table, count in tables_exported.items():
                print(f"  {table:15s}: {count:,} rows")
            print("="*70)
            print(f"✓ Export complete: {dest_path}")
            
            # Get file size
            size_mb = dest.stat().st_size / (1024 * 1024)
            print(f"  Database size: {size_mb:.2f} MB")
        
        return 0
        
    except Exception as e:
        print(f"Error during export: {e}")
        import traceback
        traceback.print_exc()
        return 1


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Export DuckDB TIGER/Line database to SQLite format compatible with Ruby version",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic export
  python export_duckdb_to_sqlite.py geocoder.duckdb geocoder.db --verbose
  
  # Overwrite existing database
  python export_duckdb_to_sqlite.py geocoder.duckdb geocoder.db --overwrite --verbose
  
  # Quiet mode
  python export_duckdb_to_sqlite.py geocoder.duckdb geocoder.db
        """
    )
    
    parser.add_argument(
        'source',
        help='Path to source DuckDB database'
    )
    
    parser.add_argument(
        'destination',
        help='Path to destination SQLite database'
    )
    
    parser.add_argument(
        '--overwrite',
        action='store_true',
        help='Overwrite existing destination database'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Print detailed progress information'
    )
    
    args = parser.parse_args()
    
    return export_duckdb_to_sqlite(
        args.source,
        args.destination,
        overwrite=args.overwrite,
        verbose=args.verbose
    )


if __name__ == '__main__':
    sys.exit(main())
