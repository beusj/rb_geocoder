#!/usr/bin/env python3
"""
Demonstration of the --discover-only feature for populating the state database
with TIGER/Line URLs without downloading files.

This script demonstrates how to:
1. Use --discover-only to populate the state database with URLs
2. Check the status of discovered URLs
3. Download the discovered files using --resume

Note: This is a demonstration that simulates the workflow. 
In production, you would use the actual Census Bureau website.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from rb_geocoder.census.census_db_dl import DownloadState, discover_and_populate_state, STATES
from unittest.mock import patch


def demo_discover_only():
    """Demonstrate the discover-only workflow."""
    
    print("=" * 80)
    print("TIGER/Line Discover-Only Feature Demonstration")
    print("=" * 80)
    print()
    
    # Create a temporary state file
    state_file = Path('/tmp/demo_state.json')
    if state_file.exists():
        state_file.unlink()
    
    # Create state tracker
    state = DownloadState(state_file)
    
    print("STEP 1: Discover available files for Delaware (FIPS: 10)")
    print("-" * 80)
    
    # Mock the discover_state_files function to simulate discovering URLs
    with patch('census.zip_dl.discover_state_files') as mock_discover:
        # Simulate discovering some PLACE files
        mock_urls = {
            'https://www2.census.gov/geo/tiger/TIGER2024/PLACE/tl_2024_10_place.zip',
            'https://www2.census.gov/geo/tiger/TIGER2024/PLACE/tl_2024_10_cousub.zip',
        }
        mock_discover.return_value = {'PLACE': mock_urls}
        
        # Call discover_and_populate_state
        count = discover_and_populate_state(
            state_fips='10',
            year=2024,
            dataset_types=['PLACE'],
            timeout=30,
            state=state
        )
    
    print(f"✓ Discovered {count} files for Delaware")
    print()
    
    print("STEP 2: Check the state database")
    print("-" * 80)
    
    # Get state summary
    summary = state.get_state_summary('10')
    print(f"State: {summary['name']}")
    print(f"Discovered: {len(state.data['discovered_urls']['10'])} URLs")
    print(f"Completed:  {summary['completed']} files")
    print(f"Failed:     {summary['failed']} files")
    print()
    
    print("Discovered URLs:")
    for url in state.data['discovered_urls']['10']:
        print(f"  • {url}")
    print()
    
    print("STEP 3: Check download progress")
    print("-" * 80)
    
    progress = state.get_download_progress('10')
    print(f"Discovered: {progress['discovered']}")
    print(f"Completed:  {progress['completed']}")
    print(f"Failed:     {progress['failed']}")
    print(f"Pending:    {progress['pending']}")
    print()
    
    print("STEP 4: Simulate downloading one file")
    print("-" * 80)
    
    # Mark one URL as completed
    first_url = list(state.data['discovered_urls']['10'])[0]
    state.mark_completed(
        first_url,
        '/tmp/demo/file.zip',
        state_fips='10',
        file_size=1024000
    )
    
    print(f"✓ Marked as completed: {first_url}")
    print()
    
    print("STEP 5: Check progress again")
    print("-" * 80)
    
    progress = state.get_download_progress('10')
    print(f"Discovered: {progress['discovered']}")
    print(f"Completed:  {progress['completed']}")
    print(f"Failed:     {progress['failed']}")
    print(f"Pending:    {progress['pending']}")
    print()
    
    print("Pending URLs:")
    for url in progress['pending_urls']:
        print(f"  ⊙ {url}")
    print()
    
    print("=" * 80)
    print("Demonstration Complete!")
    print("=" * 80)
    print()
    print("In production, you would use these commands:")
    print()
    print("  # Step 1: Discover files")
    print("  python census/zip_dl.py --discover-only --states 10 --types PLACE")
    print()
    print("  # Step 2: Check status")
    print("  python census/zip_dl.py --show-status")
    print()
    print("  # Step 3: Download discovered files")
    print("  python census/zip_dl.py --states 10 --discover --resume")
    print()
    
    # Cleanup
    state_file.unlink()


if __name__ == '__main__':
    demo_discover_only()
