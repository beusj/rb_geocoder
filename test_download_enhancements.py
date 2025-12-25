#!/usr/bin/env python3
"""
Unit tests for download state tracking and partial resume functionality.
Run with: pytest test_download_enhancements.py -v
"""

import pytest
import json
import tempfile
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from census.zip_dl import DownloadState


class TestDownloadState:
    """Test the enhanced DownloadState class."""
    
    @pytest.fixture
    def state_file(self):
        """Create a temporary state file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = Path(f.name)
        yield temp_path
        if temp_path.exists():
            temp_path.unlink()
    
    @pytest.fixture
    def download_state(self, state_file):
        """Create a DownloadState instance."""
        return DownloadState(state_file)
    
    def test_initialization(self, download_state, state_file):
        """Test DownloadState initialization."""
        assert state_file.exists()
        assert download_state.data is not None
        assert 'files' in download_state.data
        assert 'states' in download_state.data
        assert 'completed' in download_state.data
        assert 'failed' in download_state.data
    
    def test_mark_completed(self, download_state):
        """Test marking files as completed."""
        url = "https://example.com/file.zip"
        path = "/tmp/test/file.zip"
        
        download_state.mark_completed(url, path, state_fips="06", file_size=1024000)
        
        assert download_state.is_completed(path)
        assert url in download_state.data['completed']
        assert path in download_state.data['files']
        assert download_state.data['files'][path]['status'] == 'completed'
        assert download_state.data['files'][path]['size'] == 1024000
        assert download_state.data['files'][path]['state'] == '06'
    
    def test_mark_failed(self, download_state):
        """Test marking files as failed."""
        url = "https://example.com/file.zip"
        path = "/tmp/test/file.zip"
        error = "Connection timeout"
        
        download_state.mark_failed(url, path, error, state_fips="06")
        
        assert url in download_state.data['failed']
        assert path in download_state.data['files']
        assert download_state.data['files'][path]['status'] == 'failed'
        assert download_state.data['files'][path]['error'] == error
        assert download_state.data['files'][path]['state'] == '06'
    
    def test_mark_partial(self, download_state):
        """Test marking files as partial."""
        url = "https://example.com/file.zip"
        path = "/tmp/test/file.zip"
        bytes_downloaded = 524288
        
        download_state.mark_partial(url, path, bytes_downloaded, state_fips="06")
        
        assert path in download_state.data['files']
        assert download_state.data['files'][path]['status'] == 'partial'
        assert download_state.data['files'][path]['bytes_downloaded'] == bytes_downloaded
        assert download_state.data['files'][path]['state'] == '06'
    
    def test_get_partial_size(self, download_state):
        """Test retrieving partial download size."""
        url = "https://example.com/file.zip"
        path = "/tmp/test/file.zip"
        bytes_downloaded = 524288
        
        # Initially should return 0
        assert download_state.get_partial_size(path) == 0
        
        # After marking as partial
        download_state.mark_partial(url, path, bytes_downloaded, state_fips="06")
        assert download_state.get_partial_size(path) == bytes_downloaded
        
        # After completing, should return 0
        download_state.mark_completed(url, path, state_fips="06", file_size=1024000)
        assert download_state.get_partial_size(path) == 0
    
    def test_state_tracking(self, download_state):
        """Test state/territory level tracking."""
        # Add files for California
        download_state.mark_completed(
            "https://example.com/ca1.zip",
            "/tmp/test/ca1.zip",
            state_fips="06",
            file_size=1024000
        )
        download_state.mark_completed(
            "https://example.com/ca2.zip",
            "/tmp/test/ca2.zip",
            state_fips="06",
            file_size=2048000
        )
        download_state.mark_failed(
            "https://example.com/ca3.zip",
            "/tmp/test/ca3.zip",
            "Connection timeout",
            state_fips="06"
        )
        
        # Add files for New York
        download_state.mark_completed(
            "https://example.com/ny1.zip",
            "/tmp/test/ny1.zip",
            state_fips="36",
            file_size=512000
        )
        
        # Check states tracked
        states = download_state.list_states_requested()
        assert '06' in states
        assert '36' in states
        assert len(states) == 2
    
    def test_get_state_summary(self, download_state):
        """Test getting state summary."""
        # Add some files
        download_state.mark_completed(
            "https://example.com/ca1.zip",
            "/tmp/test/ca1.zip",
            state_fips="06",
            file_size=1024000
        )
        download_state.mark_completed(
            "https://example.com/ca2.zip",
            "/tmp/test/ca2.zip",
            state_fips="06",
            file_size=2048000
        )
        download_state.mark_failed(
            "https://example.com/ca3.zip",
            "/tmp/test/ca3.zip",
            "Connection timeout",
            state_fips="06"
        )
        
        # Get summary for California
        summary = download_state.get_state_summary("06")
        assert summary['name'] == 'California'
        assert summary['completed'] == 2
        assert summary['failed'] == 1
    
    def test_get_urls_for_state(self, download_state):
        """Test getting URLs for a specific state."""
        # Add some files
        url1 = "https://example.com/ca1.zip"
        url2 = "https://example.com/ca2.zip"
        url3 = "https://example.com/ca3.zip"
        
        download_state.mark_completed(url1, "/tmp/test/ca1.zip", state_fips="06", file_size=1024000)
        download_state.mark_completed(url2, "/tmp/test/ca2.zip", state_fips="06", file_size=2048000)
        download_state.mark_failed(url3, "/tmp/test/ca3.zip", "Connection timeout", state_fips="06")
        
        # Get URLs
        urls = download_state.get_urls_for_state("06")
        assert len(urls['completed']) == 2
        assert len(urls['failed']) == 1
        assert url1 in urls['completed']
        assert url2 in urls['completed']
        assert url3 in urls['failed']
    
    def test_get_summary(self, download_state):
        """Test overall summary."""
        # Add various files
        download_state.mark_completed(
            "https://example.com/file1.zip",
            "/tmp/test/file1.zip",
            state_fips="06",
            file_size=1024000
        )
        download_state.mark_completed(
            "https://example.com/file2.zip",
            "/tmp/test/file2.zip",
            state_fips="06",
            file_size=2048000
        )
        download_state.mark_failed(
            "https://example.com/file3.zip",
            "/tmp/test/file3.zip",
            "Connection timeout",
            state_fips="06"
        )
        download_state.mark_partial(
            "https://example.com/file4.zip",
            "/tmp/test/file4.zip",
            524288,
            state_fips="06"
        )
        
        summary = download_state.get_summary()
        assert summary['completed'] == 2
        assert summary['failed'] == 1
        assert summary['total'] == 4
    
    def test_state_persistence(self, download_state, state_file):
        """Test that state persists across instances."""
        # Add some data
        download_state.mark_completed(
            "https://example.com/file.zip",
            "/tmp/test/file.zip",
            state_fips="06",
            file_size=1024000
        )
        
        # Create new instance with same file
        new_state = DownloadState(state_file)
        
        # Verify data persisted
        assert "/tmp/test/file.zip" in new_state.data['files']
        assert new_state.data['files']["/tmp/test/file.zip"]['status'] == 'completed'
        assert '06' in new_state.list_states_requested()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
