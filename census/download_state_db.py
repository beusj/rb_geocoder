#!/usr/bin/env python3
"""
DuckDB-based download state tracking for improved scalability and concurrent access.

This module provides a DuckDB backend for tracking download state, offering:
- Better scalability for tracking thousands of files
- Concurrent access from multiple processes
- Rich SQL querying capabilities
- Integration with the main geocoder database workflow
"""

import time
from pathlib import Path
from typing import Dict, List, Set, Optional
import json

try:
    import duckdb
    DUCKDB_AVAILABLE = True
except ImportError:
    DUCKDB_AVAILABLE = False


class DownloadStateDB:
    """
    Track download state using DuckDB for better scalability and query capabilities.
    
    Database Schema:
    - files: Individual file tracking (path, url, status, state, size, bytes_downloaded, timestamp)
    - states: State/territory level summary (state_fips, name, completed, failed, discovered)
    - discovered_urls: All discovered URLs per state
    """
    
    def __init__(self, db_path: Path):
        """
        Initialize DuckDB state tracker.
        
        Args:
            db_path: Path to DuckDB database file
        """
        if not DUCKDB_AVAILABLE:
            raise ImportError("DuckDB is not available. Install with: pip install duckdb>=0.9.0")
        
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize database connection
        self.conn = duckdb.connect(str(self.db_path))
        self._create_schema()
    
    def _create_schema(self):
        """Create database schema if it doesn't exist."""
        # Files table - tracks individual file downloads
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS files (
                path VARCHAR PRIMARY KEY,
                url VARCHAR NOT NULL,
                status VARCHAR NOT NULL,
                state_fips VARCHAR,
                size BIGINT,
                bytes_downloaded BIGINT,
                error VARCHAR,
                timestamp DOUBLE NOT NULL
            )
        """)
        
        # Create indexes separately
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_status ON files(status)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_state ON files(state_fips)")
        
        # States table - summary statistics per state
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS states (
                state_fips VARCHAR PRIMARY KEY,
                name VARCHAR NOT NULL,
                completed INTEGER DEFAULT 0,
                failed INTEGER DEFAULT 0,
                discovered INTEGER DEFAULT 0,
                last_updated DOUBLE
            )
        """)
        
        # Discovered URLs table - all URLs found for each state
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS discovered_urls (
                state_fips VARCHAR NOT NULL,
                url VARCHAR NOT NULL,
                discovered_at DOUBLE NOT NULL,
                PRIMARY KEY (state_fips, url)
            )
        """)
        
        # Completed/failed URL lists (for compatibility with JSON format)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS url_lists (
                url VARCHAR PRIMARY KEY,
                list_type VARCHAR NOT NULL,  -- completed or failed
                added_at DOUBLE NOT NULL
            )
        """)
    
    def mark_completed(self, url: str, output_path: str, state_fips: str = None, file_size: int = None):
        """Mark a file as successfully downloaded."""
        timestamp = time.time()
        
        # Upsert file record
        self.conn.execute("""
            INSERT INTO files (path, url, status, state_fips, size, bytes_downloaded, error, timestamp)
            VALUES (?, ?, 'completed', ?, ?, NULL, NULL, ?)
            ON CONFLICT (path) DO UPDATE SET
                status = 'completed',
                url = EXCLUDED.url,
                state_fips = EXCLUDED.state_fips,
                size = EXCLUDED.size,
                bytes_downloaded = NULL,
                error = NULL,
                timestamp = EXCLUDED.timestamp
        """, [output_path, url, state_fips, file_size, timestamp])
        
        # Add to completed list
        self.conn.execute("""
            INSERT INTO url_lists (url, list_type, added_at)
            VALUES (?, 'completed', ?)
            ON CONFLICT (url) DO UPDATE SET list_type = 'completed', added_at = EXCLUDED.added_at
        """, [url, timestamp])
        
        # Remove from failed list if exists
        self.conn.execute("DELETE FROM url_lists WHERE url = ? AND list_type = 'failed'", [url])
        
        # Update state statistics
        if state_fips:
            self._update_state_stats(state_fips, 'completed')
    
    def mark_failed(self, url: str, output_path: str, error: str, state_fips: str = None):
        """Mark a file as failed."""
        timestamp = time.time()
        
        # Upsert file record
        self.conn.execute("""
            INSERT INTO files (path, url, status, state_fips, size, bytes_downloaded, error, timestamp)
            VALUES (?, ?, 'failed', ?, NULL, NULL, ?, ?)
            ON CONFLICT (path) DO UPDATE SET
                status = 'failed',
                url = EXCLUDED.url,
                state_fips = EXCLUDED.state_fips,
                error = EXCLUDED.error,
                timestamp = EXCLUDED.timestamp
        """, [output_path, url, state_fips, error, timestamp])
        
        # Add to failed list
        self.conn.execute("""
            INSERT INTO url_lists (url, list_type, added_at)
            VALUES (?, 'failed', ?)
            ON CONFLICT (url) DO UPDATE SET list_type = 'failed', added_at = EXCLUDED.added_at
        """, [url, timestamp])
        
        # Update state statistics
        if state_fips:
            self._update_state_stats(state_fips, 'failed')
    
    def mark_partial(self, url: str, output_path: str, bytes_downloaded: int, state_fips: str = None):
        """Mark a file as partially downloaded."""
        timestamp = time.time()
        
        # Upsert file record
        self.conn.execute("""
            INSERT INTO files (path, url, status, state_fips, size, bytes_downloaded, error, timestamp)
            VALUES (?, ?, 'partial', ?, NULL, ?, NULL, ?)
            ON CONFLICT (path) DO UPDATE SET
                status = 'partial',
                url = EXCLUDED.url,
                state_fips = EXCLUDED.state_fips,
                bytes_downloaded = EXCLUDED.bytes_downloaded,
                timestamp = EXCLUDED.timestamp
        """, [output_path, url, state_fips, bytes_downloaded, timestamp])
        
        # Ensure state exists in tracking
        if state_fips:
            self._ensure_state_exists(state_fips)
    
    def get_partial_size(self, output_path: str) -> int:
        """Get the number of bytes already downloaded for a partial file."""
        result = self.conn.execute("""
            SELECT bytes_downloaded FROM files
            WHERE path = ? AND status = 'partial'
        """, [output_path]).fetchone()
        
        return result[0] if result and result[0] is not None else 0
    
    def is_completed(self, output_path: str) -> bool:
        """Check if a file is marked as completed."""
        result = self.conn.execute("""
            SELECT 1 FROM files WHERE path = ? AND status = 'completed'
        """, [output_path]).fetchone()
        
        return result is not None
    
    def _ensure_state_exists(self, state_fips: str):
        """Ensure a state exists in the states table."""
        from census.zip_dl import STATES
        
        self.conn.execute("""
            INSERT INTO states (state_fips, name, completed, failed, discovered, last_updated)
            VALUES (?, ?, 0, 0, 0, ?)
            ON CONFLICT (state_fips) DO NOTHING
        """, [state_fips, STATES.get(state_fips, f"State {state_fips}"), time.time()])
    
    def _update_state_stats(self, state_fips: str, status: str):
        """Update statistics for a state/territory."""
        from census.zip_dl import STATES
        
        timestamp = time.time()
        
        # Ensure state exists
        self._ensure_state_exists(state_fips)
        
        # Increment appropriate counter
        if status == 'completed':
            self.conn.execute("""
                UPDATE states SET completed = completed + 1, last_updated = ?
                WHERE state_fips = ?
            """, [timestamp, state_fips])
        elif status == 'failed':
            self.conn.execute("""
                UPDATE states SET failed = failed + 1, last_updated = ?
                WHERE state_fips = ?
            """, [timestamp, state_fips])
    
    def get_summary(self) -> Dict:
        """Get overall download summary."""
        result = self.conn.execute("""
            SELECT
                COUNT(*) as total,
                COUNT(CASE WHEN list_type = 'completed' THEN 1 END) as completed,
                COUNT(CASE WHEN list_type = 'failed' THEN 1 END) as failed
            FROM url_lists
        """).fetchone()
        
        if result:
            return {
                'total': self.conn.execute("SELECT COUNT(*) FROM files").fetchone()[0],
                'completed': result[1] or 0,
                'failed': result[2] or 0
            }
        
        return {'total': 0, 'completed': 0, 'failed': 0}
    
    def get_state_summary(self, state_fips: str = None) -> Dict:
        """Get detailed summary for a specific state or all states."""
        if state_fips:
            result = self.conn.execute("""
                SELECT state_fips, name, completed, failed, discovered
                FROM states WHERE state_fips = ?
            """, [state_fips]).fetchone()
            
            if result:
                return {
                    'name': result[1],
                    'completed': result[2],
                    'failed': result[3],
                    'discovered': result[4],
                    'urls': []
                }
            else:
                from census.zip_dl import STATES
                return {
                    'name': STATES.get(state_fips, f"State {state_fips}"),
                    'completed': 0,
                    'failed': 0,
                    'discovered': 0,
                    'urls': []
                }
        else:
            # Return all states
            results = self.conn.execute("""
                SELECT state_fips, name, completed, failed, discovered
                FROM states
            """).fetchall()
            
            return {
                row[0]: {
                    'name': row[1],
                    'completed': row[2],
                    'failed': row[3],
                    'discovered': row[4],
                    'urls': []
                }
                for row in results
            }
    
    def list_states_requested(self) -> List[str]:
        """Get a list of all states/territories that have been requested for download."""
        results = self.conn.execute("SELECT state_fips FROM states ORDER BY state_fips").fetchall()
        return [row[0] for row in results]
    
    def get_urls_for_state(self, state_fips: str) -> Dict[str, List[str]]:
        """Get categorized URL lists for a specific state/territory."""
        completed = self.conn.execute("""
            SELECT url FROM files
            WHERE state_fips = ? AND status = 'completed'
        """, [state_fips]).fetchall()
        
        failed = self.conn.execute("""
            SELECT url FROM files
            WHERE state_fips = ? AND status = 'failed'
        """, [state_fips]).fetchall()
        
        return {
            'completed': [row[0] for row in completed],
            'failed': [row[0] for row in failed]
        }
    
    def set_discovered_urls(self, state_fips: str, urls: Set[str]):
        """Store the list of all discovered URLs for a state/territory."""
        timestamp = time.time()
        
        # Ensure state exists
        self._ensure_state_exists(state_fips)
        
        # Batch insert discovered URLs
        if urls:
            values = [(state_fips, url, timestamp) for url in urls]
            self.conn.executemany("""
                INSERT INTO discovered_urls (state_fips, url, discovered_at)
                VALUES (?, ?, ?)
                ON CONFLICT (state_fips, url) DO NOTHING
            """, values)
        
        # Update discovered count
        count = len(urls)
        self.conn.execute("""
            UPDATE states SET discovered = ?, last_updated = ?
            WHERE state_fips = ?
        """, [count, timestamp, state_fips])
    
    def get_pending_urls(self, state_fips: str) -> List[str]:
        """Get list of URLs that still need to be downloaded for a state."""
        results = self.conn.execute("""
            SELECT d.url
            FROM discovered_urls d
            LEFT JOIN url_lists u ON d.url = u.url AND u.list_type = 'completed'
            WHERE d.state_fips = ? AND u.url IS NULL
        """, [state_fips]).fetchall()
        
        return [row[0] for row in results]
    
    def get_download_progress(self, state_fips: str) -> Dict:
        """Get detailed download progress for a state including discovered files."""
        # Get state summary
        summary = self.get_state_summary(state_fips)
        urls = self.get_urls_for_state(state_fips)
        pending = self.get_pending_urls(state_fips)
        
        return {
            'discovered': summary.get('discovered', 0),
            'completed': len(urls['completed']),
            'failed': len(urls['failed']),
            'pending': len(pending),
            'pending_urls': pending[:10]  # First 10 pending URLs
        }
    
    def close(self):
        """Close the database connection."""
        if hasattr(self, 'conn') and self.conn:
            self.conn.close()
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
    
    def export_to_json(self, json_path: Path) -> None:
        """
        Export the current state to JSON format for compatibility.
        
        Args:
            json_path: Path to JSON file to export to
        """
        # Get all files
        files_data = {}
        files = self.conn.execute("SELECT * FROM files").fetchall()
        for row in files:
            path, url, status, state_fips, size, bytes_downloaded, error, timestamp = row
            files_data[path] = {
                'url': url,
                'status': status,
                'timestamp': timestamp,
                'path': path
            }
            if state_fips:
                files_data[path]['state'] = state_fips
            if size:
                files_data[path]['size'] = size
            if bytes_downloaded:
                files_data[path]['bytes_downloaded'] = bytes_downloaded
            if error:
                files_data[path]['error'] = error
        
        # Get completed and failed lists
        completed = [row[0] for row in self.conn.execute(
            "SELECT url FROM url_lists WHERE list_type = 'completed'"
        ).fetchall()]
        
        failed = [row[0] for row in self.conn.execute(
            "SELECT url FROM url_lists WHERE list_type = 'failed'"
        ).fetchall()]
        
        # Get states
        states_data = {}
        states = self.conn.execute("SELECT * FROM states").fetchall()
        for row in states:
            state_fips, name, completed_count, failed_count, discovered, last_updated = row
            states_data[state_fips] = {
                'name': name,
                'completed': completed_count,
                'failed': failed_count,
                'urls': []
            }
        
        # Get discovered URLs
        discovered_urls = {}
        discovered = self.conn.execute("SELECT state_fips, url FROM discovered_urls").fetchall()
        for state_fips, url in discovered:
            if state_fips not in discovered_urls:
                discovered_urls[state_fips] = []
            discovered_urls[state_fips].append(url)
        
        # Build JSON structure
        data = {
            'files': files_data,
            'completed': completed,
            'failed': failed,
            'states': states_data,
            'discovered_urls': discovered_urls
        }
        
        # Write to JSON file
        with open(json_path, 'w') as f:
            json.dump(data, f, indent=2)


def migrate_json_to_db(json_path: Path, db_path: Path) -> None:
    """
    Migrate a JSON state file to DuckDB format.
    
    Args:
        json_path: Path to existing JSON state file
        db_path: Path to DuckDB database file to create
    """
    if not json_path.exists():
        raise FileNotFoundError(f"JSON state file not found: {json_path}")
    
    # Load JSON data
    with open(json_path, 'r') as f:
        data = json.load(f)
    
    # Create new DB instance
    db = DownloadStateDB(db_path)
    
    try:
        # Migrate files
        for path, file_data in data.get('files', {}).items():
            status = file_data.get('status')
            url = file_data.get('url', '')
            state_fips = file_data.get('state')
            
            if status == 'completed':
                db.mark_completed(url, path, state_fips, file_data.get('size'))
            elif status == 'failed':
                db.mark_failed(url, path, file_data.get('error', 'Unknown error'), state_fips)
            elif status == 'partial':
                db.mark_partial(url, path, file_data.get('bytes_downloaded', 0), state_fips)
        
        # Migrate discovered URLs
        for state_fips, urls in data.get('discovered_urls', {}).items():
            db.set_discovered_urls(state_fips, set(urls))
        
        print(f"Successfully migrated {len(data.get('files', {}))} files from JSON to DuckDB")
        
    finally:
        db.close()
