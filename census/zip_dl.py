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
                return {'files': {}, 'completed': [], 'failed': []}
        return {'files': {}, 'completed': [], 'failed': []}
    
    def save(self):
        """Save state to file."""
        try:
            with open(self.state_file, 'w') as f:
                json.dump(self.data, f, indent=2)
        except Exception as e:
            print(f"Warning: Could not save state file: {e}")
    
    def mark_completed(self, url: str, output_path: str):
        """Mark a file as successfully downloaded."""
        file_key = str(output_path)
        self.data['files'][file_key] = {
            'url': url,
            'status': 'completed',
            'timestamp': time.time(),
            'path': str(output_path)
        }
        if url not in self.data['completed']:
            self.data['completed'].append(url)
        if url in self.data['failed']:
            self.data['failed'].remove(url)
        self.save()
    
    def mark_failed(self, url: str, output_path: str, error: str):
        """Mark a file as failed."""
        file_key = str(output_path)
        self.data['files'][file_key] = {
            'url': url,
            'status': 'failed',
            'timestamp': time.time(),
            'error': error,
            'path': str(output_path)
        }
        if url not in self.data['failed']:
            self.data['failed'].append(url)
        self.save()
    
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


def download_file(url: str, output_path: Path, retries: int = 8, timeout: int = 60, 
                 state: DownloadState = None) -> tuple:
    """
    Download a file with enhanced retry logic for 520/523 errors.
    Returns (success: bool, url: str, message: str)
    
    Args:
        url: URL to download
        output_path: Path to save file
        retries: Number of retry attempts (default: 8)
        timeout: Request timeout in seconds (default: 60)
        state: DownloadState object for tracking (optional)
    """
    base_delay = 2  # seconds - increased from 1
    max_delay = 60  # seconds - increased from 30
    
    # Check if already downloaded and valid
    if output_path.exists():
        file_size = output_path.stat().st_size
        if file_size > 0:
            if state:
                state.mark_completed(url, str(output_path))
            return (True, url, f"Already exists: {output_path.name} ({file_size:,} bytes)")

    for attempt in range(retries):
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Add timeout to urllib request
            req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
            
            with urllib.request.urlopen(req, timeout=timeout) as response:
                # Download to temporary file first
                temp_path = output_path.with_suffix('.tmp')
                with open(temp_path, 'wb') as f:
                    f.write(response.read())
                
                # Verify file size
                file_size = temp_path.stat().st_size
                if file_size == 0:
                    temp_path.unlink()
                    raise ValueError("Downloaded file is empty")
                
                # Move to final location
                temp_path.rename(output_path)
            
            # Mark as completed in state
            if state:
                state.mark_completed(url, str(output_path))
            
            return (True, url, f"Downloaded: {output_path.name} ({file_size:,} bytes)")
            
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
                        state.mark_failed(url, str(output_path), error_msg)
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
                        state.mark_failed(url, str(output_path), error_msg)
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
                        state.mark_failed(url, str(output_path), error_msg)
                    return (False, url, error_msg)
        except Exception as e:
            # Clean up temp file if it exists
            temp_path = output_path.with_suffix('.tmp')
            if temp_path.exists():
                temp_path.unlink()
            
            if attempt < retries - 1:
                delay = min(base_delay * (2 ** attempt), max_delay)
                jitter = delay * 0.5 * random.random()
                print(f"    Error: {str(e)}, retrying in {delay + jitter:.1f}s (attempt {attempt + 1}/{retries})")
                time.sleep(delay + jitter)
            else:
                error_msg = f"Error: {str(e)}"
                if state:
                    state.mark_failed(url, str(output_path), error_msg)
                return (False, url, error_msg)
    
    error_msg = "Failed after all retry attempts"
    if state:
        state.mark_failed(url, str(output_path), error_msg)
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
        futures = {executor.submit(download_file, url, path, 8, timeout, state): (url, path) 
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
    
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Initialize state tracking
    state_file = output_dir / args.state_file
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
