#!/usr/bin/env python3
"""
Download TIGER/Line Shapefiles from the US Census Bureau for 2024
This script downloads various geographic datasets including:
- EDGES (roads/streets)
- ADDR (address ranges)
- FACES (topological faces)
- FEATNAMES (feature names)
- And other geographic boundaries

Usage:
    python zip_dl.py [options]

Options:
    --year YEAR         Year to download (default: 2024)
    --output DIR        Output directory (default: ./tiger2024)
    --states STATE      Download specific state(s) (comma-separated FIPS codes)
    --types TYPE        Download specific types (comma-separated)
    --list-types        List available dataset types
    --list-states       List all state FIPS codes
    --parallel N        Number of parallel downloads (default: 4)
    --resume            Resume from previous download session
    --state-file FILE   Path to state file (default: .tiger_download_state.json)
    --timeout N         Download timeout in seconds (default: 60)
"""

import os
import sys
import argparse
import urllib.request
import urllib.error
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict
import time
import random
import json
import hashlib

# Constants
USER_AGENT = 'TIGERLine-Downloader/1.0'
COUNTY_LEVEL_TYPES = ['EDGES', 'ADDR', 'FACES', 'FEATNAMES']

# State FIPS codes
STATES = {
    '01': 'Alabama', '02': 'Alaska', '04': 'Arizona', '05': 'Arkansas',
    '06': 'California', '08': 'Colorado', '09': 'Connecticut', '10': 'Delaware',
    '11': 'District of Columbia', '12': 'Florida', '13': 'Georgia', '15': 'Hawaii',
    '16': 'Idaho', '17': 'Illinois', '18': 'Indiana', '19': 'Iowa',
    '20': 'Kansas', '21': 'Kentucky', '22': 'Louisiana', '23': 'Maine',
    '24': 'Maryland', '25': 'Massachusetts', '26': 'Michigan', '27': 'Minnesota',
    '28': 'Mississippi', '29': 'Missouri', '30': 'Montana', '31': 'Nebraska',
    '32': 'Nevada', '33': 'New Hampshire', '34': 'New Jersey', '35': 'New Mexico',
    '36': 'New York', '37': 'North Carolina', '38': 'North Dakota', '39': 'Ohio',
    '40': 'Oklahoma', '41': 'Oregon', '42': 'Pennsylvania', '44': 'Rhode Island',
    '45': 'South Carolina', '46': 'South Dakota', '47': 'Tennessee', '48': 'Texas',
    '49': 'Utah', '50': 'Vermont', '51': 'Virginia', '53': 'Washington',
    '54': 'West Virginia', '55': 'Wisconsin', '56': 'Wyoming',
    '60': 'American Samoa', '66': 'Guam', '69': 'Commonwealth of the Northern Mariana Islands',
    '72': 'Puerto Rico', '78': 'United States Virgin Islands'
}

# Dataset types available in TIGER/Line
DATASET_TYPES = {
    'EDGES': 'All Lines (roads, railroads, etc.)',
    'ADDR': 'Address Ranges',
    'FACES': 'Topological Faces (polygons)',
    'FEATNAMES': 'Feature Names',
    'PLACE': 'Places (cities, towns)',
    'COUSUB': 'County Subdivisions',
    'TRACT': 'Census Tracts',
    'BG': 'Block Groups',
    'TABBLOCK20': 'Tabulation Blocks (2020)',
    'ZCTA520': 'ZIP Code Tabulation Areas (2020)',
    'COUNTY': 'Counties',
    'STATE': 'States',
    'CD118': 'Congressional Districts (118th)',
    'SLDL': 'State Legislative Districts (Lower)',
    'SLDU': 'State Legislative Districts (Upper)',
    'UNSD': 'Unified School Districts',
    'ELSD': 'Elementary School Districts',
    'SCSD': 'Secondary School Districts',
}

def get_county_list(state_fips: str, year: int = 2024) -> List[str]:
    """
    Get list of county FIPS codes for a given state.
    For 2024, we'll use a comprehensive list approach.
    """
    # This is a simplified approach - in reality, you might want to 
    # scrape or use a pre-defined list of counties per state
    # For now, we'll try counties 001-999 and handle 404s gracefully
    return [f"{i:03d}" for i in range(1, 200)]

def construct_url(year: int, state_fips: str, county_fips: str, dataset_type: str) -> str:
    """
    Construct the download URL for a TIGER/Line file.
    
    URL pattern: https://www2.census.gov/geo/tiger/TIGER{year}/{TYPE}/
                 tl_{year}_{statefips}{countyfips}_{type}.zip
    """
    base_url = f"https://www2.census.gov/geo/tiger/TIGER{year}"
    
    # Different dataset types have different URL structures
    if dataset_type in ['EDGES', 'ADDR', 'FACES', 'FEATNAMES']:
        # County-level datasets
        filename = f"tl_{year}_{state_fips}{county_fips}_{dataset_type.lower()}.zip"
        url = f"{base_url}/{dataset_type}/{filename}"
    elif dataset_type in ['PLACE', 'COUSUB', 'TRACT', 'BG']:
        # State-level datasets
        filename = f"tl_{year}_{state_fips}_{dataset_type.lower()}.zip"
        url = f"{base_url}/{dataset_type}/{filename}"
    elif dataset_type == 'COUNTY':
        # National dataset
        filename = f"tl_{year}_us_{dataset_type.lower()}.zip"
        url = f"{base_url}/{dataset_type}/{filename}"
    elif dataset_type == 'STATE':
        # National dataset
        filename = f"tl_{year}_us_{dataset_type.lower()}.zip"
        url = f"{base_url}/{dataset_type}/{filename}"
    else:
        # Generic pattern
        filename = f"tl_{year}_{state_fips}_{dataset_type.lower()}.zip"
        url = f"{base_url}/{dataset_type}/{filename}"
    
    return url

class DownloadState:
    """Track download state for resuming interrupted downloads."""
    
    def __init__(self, state_file: Path):
        self.state_file = state_file
        self.data = self._load()
    
    def _load(self) -> Dict:
        """Load state from file."""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    return json.load(f)
            except Exception:
                return self._default_state()
        return self._default_state()
    
    def _default_state(self) -> Dict:
        """Create default state structure."""
        return {
            'files': {}, 
            'completed': [], 
            'failed': [],
            'states': {}  # Track state/territory level information
        }
    
    def save(self):
        """Save state to file."""
        try:
            with open(self.state_file, 'w') as f:
                json.dump(self.data, f, indent=2)
        except Exception as e:
            print(f"Warning: Could not save state file: {e}")
    
    def mark_completed(self, url: str, output_path: str, state_fips: str = None, file_size: int = None):
        """Mark a file as successfully downloaded."""
        file_key = str(output_path)
        self.data['files'][file_key] = {
            'url': url,
            'status': 'completed',
            'timestamp': time.time(),
            'path': str(output_path),
            'size': file_size
        }
        if state_fips:
            self.data['files'][file_key]['state'] = state_fips
            self._update_state_stats(state_fips, 'completed')
        
        if url not in self.data['completed']:
            self.data['completed'].append(url)
        if url in self.data['failed']:
            self.data['failed'].remove(url)
        self.save()
    
    def mark_failed(self, url: str, output_path: str, error: str, state_fips: str = None):
        """Mark a file as failed."""
        file_key = str(output_path)
        self.data['files'][file_key] = {
            'url': url,
            'status': 'failed',
            'timestamp': time.time(),
            'error': error,
            'path': str(output_path)
        }
        if state_fips:
            self.data['files'][file_key]['state'] = state_fips
            self._update_state_stats(state_fips, 'failed')
        
        if url not in self.data['failed']:
            self.data['failed'].append(url)
        self.save()
    
    def mark_partial(self, url: str, output_path: str, bytes_downloaded: int, state_fips: str = None):
        """Mark a file as partially downloaded."""
        file_key = str(output_path)
        self.data['files'][file_key] = {
            'url': url,
            'status': 'partial',
            'timestamp': time.time(),
            'path': str(output_path),
            'bytes_downloaded': bytes_downloaded
        }
        if state_fips:
            self.data['files'][file_key]['state'] = state_fips
            # Ensure state exists in tracking
            if 'states' not in self.data:
                self.data['states'] = {}
            if state_fips not in self.data['states']:
                self.data['states'][state_fips] = {
                    'name': STATES.get(state_fips, f"State {state_fips}"),
                    'completed': 0,
                    'failed': 0,
                    'urls': []
                }
        self.save()
    
    def get_partial_size(self, output_path: str) -> int:
        """Get the number of bytes already downloaded for a partial file."""
        file_key = str(output_path)
        if file_key in self.data['files'] and self.data['files'][file_key].get('status') == 'partial':
            return self.data['files'][file_key].get('bytes_downloaded', 0)
        return 0
    
    def _update_state_stats(self, state_fips: str, status: str):
        """Update statistics for a state/territory."""
        if 'states' not in self.data:
            self.data['states'] = {}
        
        if state_fips not in self.data['states']:
            self.data['states'][state_fips] = {
                'name': STATES.get(state_fips, f"State {state_fips}"),
                'completed': 0,
                'failed': 0,
                'urls': []
            }
        
        if status == 'completed':
            self.data['states'][state_fips]['completed'] += 1
        elif status == 'failed':
            self.data['states'][state_fips]['failed'] += 1
    
    def is_completed(self, output_path: str) -> bool:
        """Check if a file is marked as completed."""
        file_key = str(output_path)
        return file_key in self.data['files'] and self.data['files'][file_key].get('status') == 'completed'
    
    def get_summary(self) -> Dict:
        """Get download summary."""
        return {
            'completed': len(self.data['completed']),
            'failed': len(self.data['failed']),
            'total': len(self.data['files'])
        }
    
    def get_state_summary(self, state_fips: str = None) -> Dict:
        """
        Get detailed summary for a specific state/territory or all states.
        
        Args:
            state_fips: State FIPS code, or None for all states
            
        Returns:
            Dictionary with state-level download statistics and URL lists
        """
        if 'states' not in self.data:
            self.data['states'] = {}
        
        if state_fips:
            return self.data['states'].get(state_fips, {
                'name': STATES.get(state_fips, f"State {state_fips}"),
                'completed': 0,
                'failed': 0,
                'urls': []
            })
        else:
            return self.data['states']
    
    def list_states_requested(self) -> List[str]:
        """
        Get a list of all states/territories that have been requested for download.
        
        Returns:
            List of state FIPS codes
        """
        if 'states' not in self.data:
            self.data['states'] = {}
        return list(self.data['states'].keys())
    
    def get_urls_for_state(self, state_fips: str) -> Dict[str, List[str]]:
        """
        Get categorized URL lists for a specific state/territory.
        
        Args:
            state_fips: State FIPS code
            
        Returns:
            Dictionary with 'completed', 'failed', and 'pending' URL lists
        """
        completed_urls = []
        failed_urls = []
        
        for file_key, file_data in self.data['files'].items():
            if file_data.get('state') == state_fips:
                url = file_data.get('url', '')
                if file_data.get('status') == 'completed':
                    completed_urls.append(url)
                elif file_data.get('status') == 'failed':
                    failed_urls.append(url)
        
        return {
            'completed': completed_urls,
            'failed': failed_urls
        }


def download_file(url: str, output_path: Path, retries: int = 8, timeout: int = 60, 
                 state: DownloadState = None, state_fips: str = None) -> tuple:
    """
    Download a file with enhanced retry logic and partial download resume support.
    Returns (success: bool, url: str, message: str)
    
    Args:
        url: URL to download
        output_path: Path to save file
        retries: Number of retry attempts (default: 8)
        timeout: Request timeout in seconds (default: 60)
        state: DownloadState object for tracking (optional)
        state_fips: State FIPS code for tracking (optional)
    """
    base_delay = 2  # seconds - increased from 1
    max_delay = 60  # seconds - increased from 30
    
    # Check if already downloaded and valid
    if output_path.exists():
        file_size = output_path.stat().st_size
        if file_size > 0:
            # Check if this is marked as completed in state
            if state and state.is_completed(str(output_path)):
                return (True, url, f"Already exists: {output_path.name} ({file_size:,} bytes)")
            # Otherwise mark it as completed now
            if state:
                state.mark_completed(url, str(output_path), state_fips, file_size)
            return (True, url, f"Already exists: {output_path.name} ({file_size:,} bytes)")

    # Check for partial download
    temp_path = output_path.with_suffix('.tmp')
    resume_pos = 0
    if temp_path.exists():
        resume_pos = temp_path.stat().st_size
        if resume_pos > 0 and state:
            # We have a partial download
            partial_size = state.get_partial_size(str(output_path))
            if partial_size > 0 and partial_size == resume_pos:
                # Valid partial download recorded in state
                pass
            else:
                # Record this as a partial download
                state.mark_partial(url, str(output_path), resume_pos, state_fips)

    for attempt in range(retries):
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Prepare request with optional Range header for resume
            headers = {'User-Agent': USER_AGENT}
            if resume_pos > 0:
                headers['Range'] = f'bytes={resume_pos}-'
            
            req = urllib.request.Request(url, headers=headers)
            
            try:
                with urllib.request.urlopen(req, timeout=timeout) as response:
                    # Check if server supports range requests
                    if resume_pos > 0:
                        if response.status == 206:
                            # Partial content - resume supported
                            mode = 'ab'
                        elif response.status == 200:
                            # Server doesn't support resume, start over
                            resume_pos = 0
                            mode = 'wb'
                        else:
                            mode = 'wb'
                    else:
                        mode = 'wb'
                    
                    # Download file (or remainder of file)
                    with open(temp_path, mode) as f:
                        chunk_size = 8192
                        total_downloaded = resume_pos
                        while True:
                            chunk = response.read(chunk_size)
                            if not chunk:
                                break
                            f.write(chunk)
                            total_downloaded += len(chunk)
                            
                            # Periodically update state for very large files
                            if state and total_downloaded % (chunk_size * 100) == 0:
                                state.mark_partial(url, str(output_path), total_downloaded, state_fips)
                    
                    # Verify file size
                    file_size = temp_path.stat().st_size
                    if file_size == 0:
                        temp_path.unlink()
                        raise ValueError("Downloaded file is empty")
                    
                    # Move to final location
                    temp_path.rename(output_path)
                
                # Mark as completed in state
                if state:
                    state.mark_completed(url, str(output_path), state_fips, file_size)
                
                resume_msg = f" (resumed from {resume_pos:,} bytes)" if resume_pos > 0 else ""
                return (True, url, f"Downloaded: {output_path.name} ({file_size:,} bytes){resume_msg}")
                
            except urllib.error.HTTPError as e:
                if e.code == 416:
                    # Range not satisfiable - file might be complete already
                    if temp_path.exists():
                        file_size = temp_path.stat().st_size
                        temp_path.rename(output_path)
                        if state:
                            state.mark_completed(url, str(output_path), state_fips, file_size)
                        return (True, url, f"Downloaded: {output_path.name} ({file_size:,} bytes) [completed]")
                    raise
                else:
                    raise
            
        except urllib.error.HTTPError as e:
            if e.code == 404:
                # Don't retry 404s - file doesn't exist
                return (False, url, f"Not found (404): {url}")
            elif e.code in [520, 523, 524]:
                # Server errors - retry with longer delays
                if attempt < retries - 1:
                    delay = min(base_delay * (2 ** attempt), max_delay)
                    jitter = delay * 0.5 * random.random()
                    wait_time = delay + jitter
                    print(f"    HTTP {e.code} error, retrying in {wait_time:.1f}s (attempt {attempt + 1}/{retries})")
                    time.sleep(wait_time)
                    continue
                else:
                    error_msg = f"HTTP Error {e.code} (server error): {url}"
                    if state:
                        state.mark_failed(url, str(output_path), error_msg, state_fips)
                    return (False, url, error_msg)
            elif e.code in [502, 503]:
                # Server temporarily unavailable - retry
                if attempt < retries - 1:
                    delay = min(base_delay * (2 ** attempt), max_delay)
                    jitter = delay * 0.5 * random.random()
                    time.sleep(delay + jitter)
                    continue
                else:
                    error_msg = f"HTTP Error {e.code}: {url}"
                    if state:
                        state.mark_failed(url, str(output_path), error_msg, state_fips)
                    return (False, url, error_msg)
            else:
                # Other HTTP errors
                if attempt < retries - 1:
                    delay = min(base_delay * (2 ** attempt), max_delay)
                    jitter = delay * 0.5 * random.random()
                    time.sleep(delay + jitter)
                    continue
                else:
                    error_msg = f"HTTP Error {e.code}: {url}"
                    if state:
                        state.mark_failed(url, str(output_path), error_msg, state_fips)
                    return (False, url, error_msg)
        except Exception as e:
            # Save partial state but keep temp file for resume
            if temp_path.exists():
                partial_size = temp_path.stat().st_size
                if partial_size > 0 and state:
                    state.mark_partial(url, str(output_path), partial_size, state_fips)
            
            if attempt < retries - 1:
                delay = min(base_delay * (2 ** attempt), max_delay)
                jitter = delay * 0.5 * random.random()
                print(f"    Error: {str(e)}, retrying in {delay + jitter:.1f}s (attempt {attempt + 1}/{retries})")
                time.sleep(delay + jitter)
            else:
                error_msg = f"Error: {str(e)}"
                if state:
                    state.mark_failed(url, str(output_path), error_msg, state_fips)
                return (False, url, error_msg)
    
    error_msg = "Failed after all retry attempts"
    if state:
        state.mark_failed(url, str(output_path), error_msg, state_fips)
    return (False, url, error_msg)

def download_county_data(state_fips: str, year: int, output_dir: Path, 
                         dataset_types: List[str], parallel: int = 4, 
                         timeout: int = 60, state: DownloadState = None):
    """
    Download county-level data for a state.
    
    Args:
        state_fips: State FIPS code
        year: Year to download
        output_dir: Output directory
        dataset_types: List of dataset types to download
        parallel: Number of parallel downloads
        timeout: Download timeout in seconds
        state: DownloadState object for tracking
    """
    counties = get_county_list(state_fips, year)
    state_name = STATES.get(state_fips, f"State {state_fips}")
    
    print(f"\n{'='*70}")
    print(f"Downloading data for {state_name} (FIPS: {state_fips})")
    print(f"{'='*70}")
    
    download_tasks = []
    for dataset_type in dataset_types:
        if dataset_type in COUNTY_LEVEL_TYPES:
            # County-level datasets
            for county_fips in counties:
                url = construct_url(year, state_fips, county_fips, dataset_type)
                output_path = output_dir / state_fips / f"tl_{year}_{state_fips}{county_fips}_{dataset_type.lower()}.zip"
                
                # Skip if already completed
                if state and state.is_completed(str(output_path)):
                    continue
                    
                download_tasks.append((url, output_path))
        else:
            # State-level or national datasets
            url = construct_url(year, state_fips, None, dataset_type)
            filename = url.split('/')[-1]
            output_path = output_dir / state_fips / filename
            
            # Skip if already completed
            if state and state.is_completed(str(output_path)):
                continue
                
            download_tasks.append((url, output_path))
    
    # Download in parallel
    successful = 0
    failed = 0
    not_found = 0
    skipped = 0
    
    # Calculate skipped count
    if state:
        total_possible = len(counties) * len([t for t in dataset_types if t in COUNTY_LEVEL_TYPES])
        total_possible += len([t for t in dataset_types if t not in ['EDGES', 'ADDR', 'FACES', 'FEATNAMES']])
        skipped = total_possible - len(download_tasks)
    
    if skipped > 0:
        print(f"Skipping {skipped} already downloaded files")
    
    if not download_tasks:
        print("All files already downloaded")
        return successful, failed, not_found
    
    with ThreadPoolExecutor(max_workers=parallel) as executor:
        futures = {executor.submit(download_file, url, path, 8, timeout, state, state_fips): (url, path)
                   for url, path in download_tasks}
        
        for future in as_completed(futures):
            success, url, message = future.result()
            if success:
                successful += 1
                print(f"✓ {message}")
            else:
                if "404" in message:
                    not_found += 1
                else:
                    failed += 1
                    print(f"✗ {message}")
    
    print(f"\n{state_name} Summary:")
    print(f"  Successful: {successful}")
    if skipped > 0:
        print(f"  Skipped:    {skipped}")
    print(f"  Not Found:  {not_found}")
    print(f"  Failed:     {failed}")
    
    return successful, failed, not_found

def main():
    parser = argparse.ArgumentParser(
        description='Download TIGER/Line Shapefiles from US Census Bureau',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument('--year', type=int, default=2024,
                        help='Year to download (default: 2024)')
    parser.add_argument('--output', type=str, default='./tiger',
                        help='Output directory (default: ./tiger)')
    parser.add_argument('--states', type=str,
                        help='Comma-separated state FIPS codes (e.g., "01,06,48")')
    parser.add_argument('--types', type=str,
                        help='Comma-separated dataset types (e.g., "EDGES,ADDR")')
    parser.add_argument('--list-types', action='store_true',
                        help='List available dataset types and exit')
    parser.add_argument('--list-states', action='store_true',
                        help='List all state FIPS codes and exit')
    parser.add_argument('--show-status', action='store_true',
                        help='Show download status for all states/territories and exit')
    parser.add_argument('--parallel', type=int, default=4,
                        help='Number of parallel downloads (default: 4)')
    parser.add_argument('--resume', action='store_true',
                        help='Resume from previous download session')
    parser.add_argument('--state-file', type=str, default='.tiger_download_state.json',
                        help='Path to state file (default: .tiger_download_state.json)')
    parser.add_argument('--timeout', type=int, default=60,
                        help='Download timeout in seconds (default: 60)')
    
    args = parser.parse_args()
    
    # Handle list commands
    if args.list_types:
        print("\nAvailable Dataset Types:")
        print("=" * 70)
        for dtype, desc in DATASET_TYPES.items():
            print(f"  {dtype:15s} - {desc}")
        return 0
    
    if args.list_states:
        print("\nState FIPS Codes:")
        print("=" * 70)
        for fips, name in sorted(STATES.items()):
            print(f"  {fips} - {name}")
        return 0
    
    # Handle status command
    output_dir = Path(args.output)
    state_file = output_dir / args.state_file
    
    if args.show_status:
        if not state_file.exists():
            print(f"\nNo download state file found at: {state_file}")
            print("Start a download to create a state file.")
            return 1
        
        download_state = DownloadState(state_file)
        states_list = download_state.list_states_requested()
        
        if not states_list:
            print("\nNo states/territories have been requested for download yet.")
            return 0
        
        print(f"\n{'='*70}")
        print(f"Download Status Summary")
        print(f"{'='*70}")
        print(f"State File: {state_file}")
        print(f"{'='*70}\n")
        
        for state_fips in sorted(states_list):
            state_summary = download_state.get_state_summary(state_fips)
            urls = download_state.get_urls_for_state(state_fips)
            
            state_name = state_summary.get('name', f"State {state_fips}")
            completed = state_summary.get('completed', 0)
            failed = state_summary.get('failed', 0)
            total = completed + failed
            
            print(f"State: {state_name} (FIPS: {state_fips})")
            print(f"  Completed: {completed}")
            print(f"  Failed:    {failed}")
            print(f"  Total:     {total}")
            
            if urls['completed']:
                print(f"  Sample Completed URLs ({min(3, len(urls['completed']))}):")
                for url in urls['completed'][:3]:
                    print(f"    ✓ {url}")
            
            if urls['failed']:
                print(f"  Failed URLs ({len(urls['failed'])}):")
                for url in urls['failed'][:5]:
                    print(f"    ✗ {url}")
            
            print()
        
        overall_summary = download_state.get_summary()
        print(f"{'='*70}")
        print(f"Overall Summary:")
        print(f"  Total Files Tracked: {overall_summary['total']}")
        print(f"  Completed:           {overall_summary['completed']}")
        print(f"  Failed:              {overall_summary['failed']}")
        print(f"{'='*70}\n")
        
        return 0
    
    # Determine which states to download
    if args.states:
        state_list = [s.strip().zfill(2) for s in args.states.split(',')]
        # Validate state codes
        invalid = [s for s in state_list if s not in STATES]
        if invalid:
            print(f"Error: Invalid state FIPS codes: {invalid}")
            print("Use --list-states to see valid codes")
            return 1
    else:
        state_list = list(STATES.keys())
    
    # Determine which dataset types to download
    if args.types:
        type_list = [t.strip().upper() for t in args.types.split(',')]
        # Validate types
        invalid = [t for t in type_list if t not in DATASET_TYPES]
        if invalid:
            print(f"Error: Invalid dataset types: {invalid}")
            print("Use --list-types to see valid types")
            return 1
    else:
        # Default to the most commonly used types for geocoding
        type_list = COUNTY_LEVEL_TYPES
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Initialize state tracking
    download_state = DownloadState(state_file)
    
    if args.resume:
        summary = download_state.get_summary()
        print(f"\n{'='*70}")
        print(f"Resuming previous download session")
        print(f"{'='*70}")
        print(f"Previously completed: {summary['completed']}")
        print(f"Previously failed:    {summary['failed']}")
        print(f"{'='*70}\n")
    
    print(f"\n{'='*70}")
    print(f"TIGER/Line Download Configuration")
    print(f"{'='*70}")
    print(f"Year:          {args.year}")
    print(f"Output Dir:    {output_dir.absolute()}")
    print(f"States:        {len(state_list)} state(s)")
    print(f"Dataset Types: {', '.join(type_list)}")
    print(f"Parallel DLs:  {args.parallel}")
    print(f"Timeout:       {args.timeout}s")
    print(f"State File:    {state_file}")
    print(f"{'='*70}\n")
    
    # Download data for each state
    total_successful = 0
    total_failed = 0
    total_not_found = 0
    
    start_time = time.time()
    
    for state_fips in state_list:
        successful, failed, not_found = download_county_data(
            state_fips, args.year, output_dir, type_list, args.parallel, 
            args.timeout, download_state
        )
        total_successful += successful
        total_failed += failed
        total_not_found += not_found
    
    elapsed = time.time() - start_time
    
    # Get final state summary
    state_summary = download_state.get_summary()
    
    # Final summary
    print(f"\n{'='*70}")
    print(f"FINAL SUMMARY")
    print(f"{'='*70}")
    print(f"Total Successful: {total_successful}")
    print(f"Total Not Found:  {total_not_found}")
    print(f"Total Failed:     {total_failed}")
    print(f"Total Tracked:    {state_summary['total']}")
    print(f"Elapsed Time:     {elapsed:.1f} seconds")
    print(f"Output Directory: {output_dir.absolute()}")
    print(f"State File:       {state_file}")
    print(f"{'='*70}\n")
    
    if total_failed > 0:
        print(f"Note: Use --resume to retry failed downloads")
    
    return 0 if total_failed == 0 else 1

if __name__ == '__main__':
    sys.exit(main())
