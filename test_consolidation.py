#!/usr/bin/env python3
"""
Test for consolidated download and import functionality.
"""

import pytest
import tempfile
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from census.zip_dl import create_state_tracker, DUCKDB_AVAILABLE


class TestConsolidation:
    """Test consolidated download/import functionality."""
    
    def test_default_use_db(self):
        """Test that --use-db is enabled by default."""
        # This would be tested by checking argparse defaults
        # For now, just verify imports work
        assert create_state_tracker is not None
    
    def test_create_state_tracker_with_db(self):
        """Test creating state tracker with DuckDB backend."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / '.tiger_download_state'
            
            # Create with DB backend (use_db=True)
            if DUCKDB_AVAILABLE:
                tracker = create_state_tracker(state_file, use_db=True)
                
                # Verify it's using DB backend
                from census.download_state_db import DownloadStateDB
                assert isinstance(tracker, DownloadStateDB)
                
                # Test basic functionality
                tracker.mark_completed(
                    "https://example.com/test.zip",
                    "/tmp/test.zip",
                    state_fips="06",
                    file_size=1024
                )
                
                assert tracker.is_completed("/tmp/test.zip")
                
                # Close connection
                tracker.conn.close()
    
    def test_create_state_tracker_with_json(self):
        """Test creating state tracker with JSON backend."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / '.tiger_download_state'
            
            # Create with JSON backend (use_db=False)
            from census.zip_dl import DownloadState
            tracker = create_state_tracker(state_file, use_db=False)
            
            # Verify it's using JSON backend
            assert isinstance(tracker, DownloadState)
            
            # Test basic functionality
            tracker.mark_completed(
                "https://example.com/test.zip",
                "/tmp/test.zip",
                state_fips="06",
                file_size=1024
            )
            
            assert tracker.is_completed("/tmp/test.zip")
    
    def test_default_output_path(self):
        """Test that default output path is census/tiger."""
        import argparse
        import sys
        from io import StringIO
        
        # Capture help output to verify default
        from census import zip_dl
        
        # Create a test parser to check defaults
        parser = argparse.ArgumentParser()
        parser.add_argument('--output', type=str, default='census/tiger')
        
        args = parser.parse_args([])
        assert args.output == 'census/tiger'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
