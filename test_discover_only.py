#!/usr/bin/env python3
"""
Unit tests for --discover-only functionality.
Run with: pytest test_discover_only.py -v
"""

import pytest
import json
import tempfile
from pathlib import Path
import sys
from unittest.mock import patch, MagicMock

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from census.zip_dl import (
    discover_and_populate_state,
    DownloadState,
    discover_state_files,
    STATES
)


class TestDiscoverOnly:
    """Test the --discover-only functionality."""
    
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
    
    def test_discover_and_populate_state_function_exists(self):
        """Test that discover_and_populate_state function exists."""
        assert callable(discover_and_populate_state)
    
    @patch('census.zip_dl.discover_state_files')
    def test_discover_and_populate_state_basic(self, mock_discover, download_state):
        """Test basic discover_and_populate_state functionality."""
        # Mock the discover_state_files to return some URLs
        mock_urls = {
            'https://example.com/file1.zip',
            'https://example.com/file2.zip',
            'https://example.com/file3.zip'
        }
        mock_discover.return_value = {'PLACE': mock_urls}
        
        # Call discover_and_populate_state
        count = discover_and_populate_state(
            state_fips='06',
            year=2024,
            dataset_types=['PLACE'],
            timeout=30,
            state=download_state
        )
        
        # Verify count
        assert count == 3
        
        # Verify state was updated
        assert '06' in download_state.data['states']
        assert download_state.data['states']['06']['name'] == 'California'
        
        # Verify discovered URLs were stored
        assert '06' in download_state.data['discovered_urls']
        assert len(download_state.data['discovered_urls']['06']) == 3
        assert 'https://example.com/file1.zip' in download_state.data['discovered_urls']['06']
    
    @patch('census.zip_dl.discover_state_files')
    def test_discover_multiple_dataset_types(self, mock_discover, download_state):
        """Test discovering multiple dataset types."""
        # Mock different URLs for different dataset types
        mock_discover.return_value = {
            'PLACE': {
                'https://example.com/place1.zip',
                'https://example.com/place2.zip'
            },
            'EDGES': {
                'https://example.com/edges1.zip',
                'https://example.com/edges2.zip',
                'https://example.com/edges3.zip'
            }
        }
        
        # Call discover_and_populate_state
        count = discover_and_populate_state(
            state_fips='06',
            year=2024,
            dataset_types=['PLACE', 'EDGES'],
            timeout=30,
            state=download_state
        )
        
        # Should have all URLs combined
        assert count == 5
        
        # Verify all URLs were stored
        assert len(download_state.data['discovered_urls']['06']) == 5
    
    @patch('census.zip_dl.discover_state_files')
    def test_discover_no_files_found(self, mock_discover, download_state):
        """Test when no files are discovered."""
        # Mock empty results
        mock_discover.return_value = {'PLACE': set()}
        
        # Call discover_and_populate_state
        count = discover_and_populate_state(
            state_fips='10',
            year=2024,
            dataset_types=['PLACE'],
            timeout=30,
            state=download_state
        )
        
        # Should return 0
        assert count == 0
        
        # State should still be tracked
        assert '10' in download_state.data['states']
        assert download_state.data['states']['10']['name'] == 'Delaware'
        
        # Discovered URLs should be empty list
        assert '10' in download_state.data['discovered_urls']
        assert len(download_state.data['discovered_urls']['10']) == 0
    
    @patch('census.zip_dl.discover_state_files')
    def test_discover_multiple_states(self, mock_discover, download_state):
        """Test discovering files for multiple states."""
        # First state
        mock_discover.return_value = {'PLACE': {'https://example.com/ca1.zip'}}
        count1 = discover_and_populate_state(
            state_fips='06',
            year=2024,
            dataset_types=['PLACE'],
            timeout=30,
            state=download_state
        )
        
        # Second state
        mock_discover.return_value = {'PLACE': {'https://example.com/ny1.zip', 'https://example.com/ny2.zip'}}
        count2 = discover_and_populate_state(
            state_fips='36',
            year=2024,
            dataset_types=['PLACE'],
            timeout=30,
            state=download_state
        )
        
        # Verify both states were tracked
        assert '06' in download_state.data['states']
        assert '36' in download_state.data['states']
        
        # Verify URLs are separate
        assert len(download_state.data['discovered_urls']['06']) == 1
        assert len(download_state.data['discovered_urls']['36']) == 2
    
    def test_set_discovered_urls_creates_state(self, download_state):
        """Test that set_discovered_urls creates state entry."""
        urls = {
            'https://example.com/file1.zip',
            'https://example.com/file2.zip'
        }
        
        # Set discovered URLs
        download_state.set_discovered_urls('48', urls)
        
        # Verify state was created
        assert '48' in download_state.data['states']
        assert download_state.data['states']['48']['name'] == 'Texas'
        
        # Verify URLs were stored
        assert '48' in download_state.data['discovered_urls']
        assert len(download_state.data['discovered_urls']['48']) == 2
    
    def test_get_pending_urls(self, download_state):
        """Test getting pending URLs (discovered but not downloaded)."""
        urls = {
            'https://example.com/file1.zip',
            'https://example.com/file2.zip',
            'https://example.com/file3.zip'
        }
        
        # Set discovered URLs
        download_state.set_discovered_urls('06', urls)
        
        # Mark one as completed
        download_state.mark_completed(
            'https://example.com/file1.zip',
            '/tmp/file1.zip',
            state_fips='06',
            file_size=1024
        )
        
        # Get pending URLs
        pending = download_state.get_pending_urls('06')
        
        # Should have 2 pending URLs
        assert len(pending) == 2
        assert 'https://example.com/file1.zip' not in pending
        assert 'https://example.com/file2.zip' in pending
        assert 'https://example.com/file3.zip' in pending
    
    def test_get_download_progress(self, download_state):
        """Test getting download progress with discovered files."""
        urls = {
            'https://example.com/file1.zip',
            'https://example.com/file2.zip',
            'https://example.com/file3.zip',
            'https://example.com/file4.zip'
        }
        
        # Set discovered URLs
        download_state.set_discovered_urls('06', urls)
        
        # Mark some as completed
        download_state.mark_completed(
            'https://example.com/file1.zip',
            '/tmp/file1.zip',
            state_fips='06',
            file_size=1024
        )
        download_state.mark_completed(
            'https://example.com/file2.zip',
            '/tmp/file2.zip',
            state_fips='06',
            file_size=2048
        )
        
        # Mark one as failed
        download_state.mark_failed(
            'https://example.com/file3.zip',
            '/tmp/file3.zip',
            'Connection timeout',
            state_fips='06'
        )
        
        # Get progress
        progress = download_state.get_download_progress('06')
        
        # Verify progress counts
        assert progress['discovered'] == 4
        assert progress['completed'] == 2
        assert progress['failed'] == 1
        assert progress['pending'] == 1
        assert 'https://example.com/file4.zip' in progress['pending_urls']


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
