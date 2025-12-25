"""
Tests for DuckDB to SQLite export functionality.
"""

import pytest
import tempfile
import sqlite3
import duckdb
import struct
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from tools.export_duckdb_to_sqlite import (
    compress_wkb_linestring,
    create_sqlite_schema,
    export_duckdb_to_sqlite
)


class TestGeometryCompression:
    """Tests for WKB to compressed format conversion."""
    
    def test_compress_linestring_simple(self):
        """Test compressing a simple 2-point LineString."""
        # Create WKB for LineString with 2 points: (0.0, 0.0), (1.0, 1.0)
        wkb = bytearray()
        wkb.append(1)  # Little-endian
        wkb.extend(struct.pack('<I', 2))  # LineString type
        wkb.extend(struct.pack('<I', 2))  # Number of points
        wkb.extend(struct.pack('<dd', 0.0, 0.0))  # Point 1
        wkb.extend(struct.pack('<dd', 1.0, 1.0))  # Point 2
        
        compressed = compress_wkb_linestring(bytes(wkb))
        
        # Should be 4 int32 values (x1, y1, x2, y2)
        assert len(compressed) == 16
        
        # Unpack and verify
        x1, y1, x2, y2 = struct.unpack('<iiii', compressed)
        assert x1 == 0
        assert y1 == 0
        assert x2 == 1_000_000  # 1.0 * 1,000,000
        assert y2 == 1_000_000
    
    def test_compress_linestring_negative_coords(self):
        """Test compressing LineString with negative coordinates."""
        # Create WKB for LineString with negative coordinates
        wkb = bytearray()
        wkb.append(1)  # Little-endian
        wkb.extend(struct.pack('<I', 2))  # LineString type
        wkb.extend(struct.pack('<I', 2))  # Number of points
        wkb.extend(struct.pack('<dd', -122.4194, 37.7749))  # SF coords
        wkb.extend(struct.pack('<dd', -122.4183, 37.7750))  # Nearby point
        
        compressed = compress_wkb_linestring(bytes(wkb))
        
        # Should be 4 int32 values
        assert len(compressed) == 16
        
        # Unpack and verify
        x1, y1, x2, y2 = struct.unpack('<iiii', compressed)
        
        # Check that negative values are preserved
        assert x1 < 0
        assert y1 > 0
        
        # Verify precision (within 1 meter)
        assert abs(x1 / 1_000_000 - (-122.4194)) < 0.000001
        assert abs(y1 / 1_000_000 - 37.7749) < 0.000001
    
    def test_compress_empty_geometry(self):
        """Test compressing empty geometry."""
        compressed = compress_wkb_linestring(b'')
        assert compressed == b''
    
    def test_compress_point_geometry(self):
        """Test compressing Point geometry (fallback)."""
        # Create WKB for Point
        wkb = bytearray()
        wkb.append(1)  # Little-endian
        wkb.extend(struct.pack('<I', 1))  # Point type
        wkb.extend(struct.pack('<dd', -122.4194, 37.7749))
        
        compressed = compress_wkb_linestring(bytes(wkb))
        
        # Should be 2 int32 values (x, y)
        assert len(compressed) == 8
        
        x, y = struct.unpack('<ii', compressed)
        assert abs(x / 1_000_000 - (-122.4194)) < 0.000001
        assert abs(y / 1_000_000 - 37.7749) < 0.000001


class TestSQLiteSchema:
    """Tests for SQLite schema creation."""
    
    def test_create_schema(self):
        """Test creating SQLite schema."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        try:
            conn = sqlite3.connect(db_path)
            create_sqlite_schema(conn)
            
            # Verify tables exist
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
            tables = [row[0] for row in cursor.fetchall()]
            
            assert 'place' in tables
            assert 'feature' in tables
            assert 'edge' in tables
            assert 'range' in tables
            assert 'feature_edge' in tables
            
            # Verify place table schema
            cursor.execute("PRAGMA table_info(place)")
            columns = {row[1]: row[2] for row in cursor.fetchall()}
            
            assert 'zip' in columns
            assert 'city' in columns
            assert 'state' in columns
            assert 'city_phone' in columns
            
            conn.close()
        finally:
            Path(db_path).unlink(missing_ok=True)


class TestExport:
    """Tests for full export functionality."""
    
    def test_export_empty_database(self):
        """Test exporting an empty DuckDB database."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source_path = Path(tmpdir) / "source.duckdb"
            dest_path = Path(tmpdir) / "dest.db"
            
            # Create empty DuckDB database with schema
            duck_conn = duckdb.connect(str(source_path))
            duck_conn.execute("""
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
            duck_conn.execute("""
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
            duck_conn.execute("""
                CREATE TABLE edge (
                    tlid BIGINT PRIMARY KEY,
                    geometry BLOB
                )
            """)
            duck_conn.execute("""
                CREATE TABLE range (
                    tlid BIGINT,
                    side VARCHAR(1),
                    fromhn INTEGER,
                    tohn INTEGER,
                    prenum VARCHAR,
                    PRIMARY KEY (tlid, side, fromhn, tohn)
                )
            """)
            duck_conn.execute("""
                CREATE TABLE feature_edge (
                    fid INTEGER,
                    tlid BIGINT,
                    PRIMARY KEY (fid, tlid)
                )
            """)
            duck_conn.close()
            
            # Export
            result = export_duckdb_to_sqlite(
                str(source_path),
                str(dest_path),
                verbose=False
            )
            
            assert result == 0
            assert dest_path.exists()
            
            # Verify SQLite database
            sqlite_conn = sqlite3.connect(str(dest_path))
            cursor = sqlite_conn.cursor()
            
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
            assert 'place' in tables
            assert 'feature' in tables
            assert 'edge' in tables
            
            sqlite_conn.close()
    
    def test_export_with_data(self):
        """Test exporting database with sample data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source_path = Path(tmpdir) / "source.duckdb"
            dest_path = Path(tmpdir) / "dest.db"
            
            # Create DuckDB database with sample data
            duck_conn = duckdb.connect(str(source_path))
            
            # Create tables
            duck_conn.execute("""
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
            duck_conn.execute("""
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
            duck_conn.execute("""
                CREATE TABLE edge (
                    tlid BIGINT PRIMARY KEY,
                    geometry BLOB
                )
            """)
            duck_conn.execute("""
                CREATE TABLE range (
                    tlid BIGINT,
                    side VARCHAR(1),
                    fromhn INTEGER,
                    tohn INTEGER,
                    prenum VARCHAR
                )
            """)
            duck_conn.execute("""
                CREATE TABLE feature_edge (
                    fid INTEGER,
                    tlid BIGINT
                )
            """)
            
            # Insert sample data
            duck_conn.execute("""
                INSERT INTO place VALUES 
                ('94102', 'San Francisco', 'CA', 'SNFRNSK', '075', 'C1', '67000', 1),
                ('10001', 'New York', 'NY', 'NYRK', '061', 'C1', '51000', 1)
            """)
            
            duck_conn.execute("""
                INSERT INTO feature VALUES 
                (1, 'Main St', 'MN', 'St', NULL, NULL, NULL, '94102', 'P', 'San Francisco', 'CA'),
                (2, 'Broadway', 'BRTW', 'Ave', NULL, NULL, NULL, '10001', 'P', 'New York', 'NY')
            """)
            
            duck_conn.close()
            
            # Export
            result = export_duckdb_to_sqlite(
                str(source_path),
                str(dest_path),
                verbose=True
            )
            
            assert result == 0
            assert dest_path.exists()
            
            # Verify data was exported
            sqlite_conn = sqlite3.connect(str(dest_path))
            cursor = sqlite_conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM place")
            assert cursor.fetchone()[0] == 2
            
            cursor.execute("SELECT COUNT(*) FROM feature")
            assert cursor.fetchone()[0] == 2
            
            cursor.execute("SELECT city, state FROM place WHERE zip = '94102'")
            row = cursor.fetchone()
            assert row[0] == 'San Francisco'
            assert row[1] == 'CA'
            
            sqlite_conn.close()
    
    def test_export_overwrite(self):
        """Test overwriting existing database."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source_path = Path(tmpdir) / "source.duckdb"
            dest_path = Path(tmpdir) / "dest.db"
            
            # Create source database with all required tables
            duck_conn = duckdb.connect(str(source_path))
            duck_conn.execute("CREATE TABLE place (zip VARCHAR PRIMARY KEY, city VARCHAR, state VARCHAR, city_phone VARCHAR, fips_county VARCHAR, fips_class VARCHAR, fips_place VARCHAR, priority INTEGER)")
            duck_conn.execute("CREATE TABLE feature (fid INTEGER PRIMARY KEY, street VARCHAR, street_phone VARCHAR, suftyp VARCHAR, sufdir VARCHAR, predir VARCHAR, pretyp VARCHAR, zip VARCHAR, paflag VARCHAR, city VARCHAR, state VARCHAR)")
            duck_conn.execute("CREATE TABLE edge (tlid BIGINT PRIMARY KEY, geometry BLOB)")
            duck_conn.execute("CREATE TABLE range (tlid BIGINT, side VARCHAR, fromhn INTEGER, tohn INTEGER, prenum VARCHAR)")
            duck_conn.execute("CREATE TABLE feature_edge (fid INTEGER, tlid BIGINT)")
            duck_conn.close()
            
            # Create existing destination
            dest_path.touch()
            
            # Try export without overwrite
            result = export_duckdb_to_sqlite(
                str(source_path),
                str(dest_path),
                overwrite=False,
                verbose=False
            )
            assert result == 1  # Should fail
            
            # Export with overwrite
            result = export_duckdb_to_sqlite(
                str(source_path),
                str(dest_path),
                overwrite=True,
                verbose=False
            )
            assert result == 0  # Should succeed


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
