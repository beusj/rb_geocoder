#!/usr/bin/env python3
"""
Example: Complete workflow from DuckDB to SQLite export

This example demonstrates:
1. Creating a sample DuckDB geocoding database
2. Adding sample data (places and features)
3. Exporting to SQLite format for Ruby compatibility
4. Verifying the exported database

This workflow is useful when you need to:
- Migrate from Python/DuckDB to Ruby/SQLite deployment
- Create pre-built SQLite databases for Ruby users
- Test database compatibility between Python and Ruby versions
"""

import tempfile
import sqlite3
import duckdb
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.export_duckdb_to_sqlite import export_duckdb_to_sqlite


def create_sample_duckdb_database(db_path: Path):
    """Create a sample DuckDB database with geocoding data."""
    print(f"Creating sample DuckDB database: {db_path}")
    
    conn = duckdb.connect(str(db_path))
    
    # Create schema (same as tiger_import_duckdb.py)
    conn.execute("""
        CREATE TABLE place (
            zip VARCHAR PRIMARY KEY,
            city VARCHAR,
            state VARCHAR(2),
            city_phone VARCHAR,
            fips_county VARCHAR,
            fips_class VARCHAR,
            fips_place VARCHAR,
            priority INTEGER
        )
    """)
    
    conn.execute("""
        CREATE TABLE feature (
            fid INTEGER PRIMARY KEY,
            street VARCHAR,
            street_phone VARCHAR,
            suftyp VARCHAR,
            sufdir VARCHAR,
            predir VARCHAR,
            pretyp VARCHAR,
            zip VARCHAR,
            paflag VARCHAR(1),
            city VARCHAR,
            state VARCHAR(2)
        )
    """)
    
    conn.execute("""
        CREATE TABLE edge (
            tlid BIGINT PRIMARY KEY,
            geometry BLOB
        )
    """)
    
    conn.execute("""
        CREATE TABLE range (
            tlid BIGINT,
            side VARCHAR(1),
            fromhn INTEGER,
            tohn INTEGER,
            prenum VARCHAR,
            PRIMARY KEY (tlid, side, fromhn, tohn)
        )
    """)
    
    conn.execute("""
        CREATE TABLE feature_edge (
            fid INTEGER,
            tlid BIGINT,
            PRIMARY KEY (fid, tlid)
        )
    """)
    
    # Insert sample places
    conn.execute("""
        INSERT INTO place VALUES 
        ('94102', 'San Francisco', 'CA', 'SNFRNSK', '075', 'C1', '67000', 1),
        ('94103', 'San Francisco', 'CA', 'SNFRNSK', '075', 'C1', '67000', 2),
        ('10001', 'New York', 'NY', 'NYRK', '061', 'C1', '51000', 1),
        ('10002', 'New York', 'NY', 'NYRK', '061', 'C1', '51000', 2),
        ('60601', 'Chicago', 'IL', 'CKCK', '031', 'C1', '14000', 1)
    """)
    
    # Insert sample features
    conn.execute("""
        INSERT INTO feature VALUES 
        (1, 'Main St', 'MN', 'St', NULL, NULL, NULL, '94102', 'P', 'San Francisco', 'CA'),
        (2, 'Market St', 'MRKT', 'St', NULL, NULL, NULL, '94102', 'P', 'San Francisco', 'CA'),
        (3, 'Broadway', 'BRTW', NULL, NULL, NULL, NULL, '10001', 'P', 'New York', 'NY'),
        (4, '5th Ave', 'FTF', 'Ave', NULL, NULL, NULL, '10001', 'P', 'New York', 'NY'),
        (5, 'Michigan Ave', 'MXKN', 'Ave', NULL, 'N', NULL, '60601', 'P', 'Chicago', 'IL')
    """)
    
    conn.close()
    print("✓ Sample database created")


def verify_sqlite_database(db_path: Path):
    """Verify the exported SQLite database."""
    print(f"\nVerifying SQLite database: {db_path}")
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    # Check tables exist
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [row[0] for row in cursor.fetchall()]
    print(f"  Tables: {', '.join(tables)}")
    
    # Check data counts
    cursor.execute("SELECT COUNT(*) FROM place")
    place_count = cursor.fetchone()[0]
    print(f"  Places: {place_count} rows")
    
    cursor.execute("SELECT COUNT(*) FROM feature")
    feature_count = cursor.fetchone()[0]
    print(f"  Features: {feature_count} rows")
    
    # Check sample data
    cursor.execute("SELECT city, state, zip FROM place WHERE city = 'San Francisco' ORDER BY zip")
    sf_places = cursor.fetchall()
    print(f"  San Francisco places: {len(sf_places)}")
    for city, state, zip_code in sf_places:
        print(f"    - {city}, {state} {zip_code}")
    
    # Check indexes
    cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'place%'")
    place_indexes = [row[0] for row in cursor.fetchall()]
    print(f"  Place indexes: {len(place_indexes)}")
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'feature%'")
    feature_indexes = [row[0] for row in cursor.fetchall()]
    print(f"  Feature indexes: {len(feature_indexes)}")
    
    conn.close()
    print("✓ Verification complete")


def main():
    """Run the complete export example."""
    print("=" * 70)
    print("DuckDB to SQLite Export Example")
    print("=" * 70)
    
    # Create temporary directory
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        source_db = tmpdir / "geocoder.duckdb"
        dest_db = tmpdir / "geocoder.db"
        
        # Step 1: Create sample DuckDB database
        print("\nStep 1: Creating sample DuckDB database")
        print("-" * 70)
        create_sample_duckdb_database(source_db)
        
        # Step 2: Export to SQLite
        print("\nStep 2: Exporting to SQLite format")
        print("-" * 70)
        result = export_duckdb_to_sqlite(
            str(source_db),
            str(dest_db),
            verbose=True
        )
        
        if result != 0:
            print("✗ Export failed")
            return 1
        
        # Step 3: Verify SQLite database
        print("\nStep 3: Verifying exported database")
        print("-" * 70)
        verify_sqlite_database(dest_db)
        
        # Show file sizes
        duckdb_size = source_db.stat().st_size / 1024
        sqlite_size = dest_db.stat().st_size / 1024
        
        print("\n" + "=" * 70)
        print("Summary")
        print("=" * 70)
        print(f"  DuckDB size:  {duckdb_size:.2f} KB")
        print(f"  SQLite size:  {sqlite_size:.2f} KB")
        print(f"  Compression:  {(1 - sqlite_size/duckdb_size)*100:.1f}%")
        print("=" * 70)
        print("\n✓ Export workflow completed successfully!")
        print("\nThe exported SQLite database is compatible with:")
        print("  - Ruby Geocoder::US::Database")
        print("  - Original tiger_import scripts")
        print("  - All Ruby-based geocoding tools")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
