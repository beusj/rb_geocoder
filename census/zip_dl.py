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
    --output DIR        Output directory (default: census/tiger)
    --states STATE      Download specific state(s) (comma-separated FIPS codes)
    --types TYPE        Download specific types (comma-separated, defaults to EDGES,ADDR,FEATNAMES with --discover-only)
    --list-types        List available dataset types
    --list-states       List all state FIPS codes
    --show-status       Show download status for all states/territories
    --discover          Discover available files by scraping Census Bureau directories
    --discover-only     Only discover and populate URLs in state database, do not download
    --parallel N        Number of parallel downloads (default: 4)
    --resume            Resume from previous download session
    --state-file FILE   Path to state file (default: .tiger_download_state.json or .duckdb)
    --use-db            Use DuckDB for state tracking (default: enabled)
    --no-use-db         Use JSON for state tracking instead of DuckDB
    --timeout N         Download timeout in seconds (default: 60)

Examples:
    # Discover and populate URLs without downloading (defaults to EDGES,ADDR,FEATNAMES):
    python zip_dl.py --discover-only --states 13
    
    # Discover and populate URLs with specific types:
    python zip_dl.py --discover-only --states 13 --types EDGES,ADDR
    
    # Check discovered URLs:
    python zip_dl.py --show-status
    
    # Download discovered files:
    python zip_dl.py --states 13 --discover --resume
"""

import os
import sys
import argparse
import urllib.request
import urllib.error
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Set, Union
import time
import random
import json
import hashlib
import re
from html.parser import HTMLParser

# Ensure parent directory is in sys.path for imports, particularly from download_state_db
sys.path.append(str(Path(__file__).parent.parent))

# Try to import DuckDB backend
try:
    from census.download_state_db import DownloadStateDB, DUCKDB_AVAILABLE
    print("download_state_db.py: DUCKDB_AVAILABLE =", DUCKDB_AVAILABLE)
except ImportError:
    DUCKDB_AVAILABLE = False
    DownloadStateDB = None

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

class DirectoryParser(HTMLParser):
    """Parse HTML directory listings to extract file links."""
    
    def __init__(self):
        super().__init__()
        self.links = []
        self.in_link = False
        
    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.in_link = True
            for attr, value in attrs:
                if attr == 'href' and value.endswith('.zip'):
                    self.links.append(value)
    
    def handle_endtag(self, tag):
        if tag == 'a':
            self.in_link = False


def scrape_directory(url: str, timeout: int = 30) -> Set[str]:
    """
    Scrape a Census Bureau directory page to discover available files.
    
    Args:
        url: Directory URL to scrape
        timeout: Request timeout in seconds
        
    Returns:
        Set of file URLs found in the directory
    """
    try:
        req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
        with urllib.request.urlopen(req, timeout=timeout) as response:
            html = response.read().decode('utf-8')
            
        parser = DirectoryParser()
        parser.feed(html)
        
        # Convert relative URLs to absolute URLs
        base_url = url if url.endswith('/') else url + '/'
        absolute_urls = {base_url + link for link in parser.links if link.endswith('.zip')}
        
        return absolute_urls
        
    except Exception as e:
        print(f"Warning: Could not scrape directory {url}: {e}")
        return set()


def discover_state_files(state_fips: str, year: int, dataset_types: List[str], timeout: int = 30) -> Dict[str, Set[str]]:
    """
    Discover all available files for a state by scraping Census Bureau directories.
    
    Args:
        state_fips: State FIPS code
        year: Year to download
        dataset_types: List of dataset types to discover
        timeout: Request timeout in seconds
        
    Returns:
        Dictionary mapping dataset type to set of discovered URLs
    """
    discovered = {}
    base_url = f"https://www2.census.gov/geo/tiger/TIGER{year}"
    
    for dataset_type in dataset_types:
        print(f"  Discovering {dataset_type} files for state {state_fips}...")
        directory_url = f"{base_url}/{dataset_type}/"
        
        all_urls = scrape_directory(directory_url, timeout)
        
        # Filter URLs for this specific state
        state_pattern = re.compile(f"tl_{year}_{state_fips}\\d{{3}}_{dataset_type.lower()}\\.zip")
        state_urls = {url for url in all_urls if state_pattern.search(url)}
        
        discovered[dataset_type] = state_urls
        print(f"    Found {len(state_urls)} {dataset_type} files")
    
    return discovered


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
            'states': {},  # Track state/territory level information
            'discovered_urls': {}  # Track all discovered URLs per state
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
    
    def set_discovered_urls(self, state_fips: str, urls: Set[str]):
        """
        Store the list of all discovered URLs for a state/territory.
        
        Args:
            state_fips: State FIPS code
            urls: Set of discovered URLs
        """
        if 'discovered_urls' not in self.data:
            self.data['discovered_urls'] = {}
        
        self.data['discovered_urls'][state_fips] = list(urls)
        
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
    
    def get_pending_urls(self, state_fips: str) -> List[str]:
        """
        Get list of URLs that still need to be downloaded for a state.
        
        Args:
            state_fips: State FIPS code
            
        Returns:
            List of URLs that haven't been completed or failed yet
        """
        if 'discovered_urls' not in self.data or state_fips not in self.data['discovered_urls']:
            return []
        
        all_discovered = set(self.data['discovered_urls'][state_fips])
        completed = set(self.data.get('completed', []))
        failed = set(self.data.get('failed', []))
        
        # URLs that are discovered but not completed or failed
        pending = all_discovered - completed - failed
        
        return list(pending)
    
    def get_download_progress(self, state_fips: str) -> Dict:
        """
        Get detailed download progress for a state including discovered files.
        
        Args:
            state_fips: State FIPS code
            
        Returns:
            Dictionary with counts of discovered, completed, failed, and pending files
        """
        discovered_count = 0
        if 'discovered_urls' in self.data and state_fips in self.data['discovered_urls']:
            discovered_count = len(self.data['discovered_urls'][state_fips])
        
        urls = self.get_urls_for_state(state_fips)
        pending = self.get_pending_urls(state_fips)
        
        return {
            'discovered': discovered_count,
            'completed': len(urls['completed']),
            'failed': len(urls['failed']),
            'pending': len(pending),
            'pending_urls': pending[:10]  # First 10 pending URLs
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
                            print(f"    Server doesn't support resume, restarting download...")
                            resume_pos = 0
                            mode = 'wb'
                            # Delete temp file to start fresh
                            if temp_path.exists():
                                temp_path.unlink()
                        else:
                            mode = 'wb'
                    else:
                        mode = 'wb'
                    
                    # Download file (or remainder of file)
                    with open(temp_path, mode) as f:
                        chunk_size = 8192
                        total_downloaded = resume_pos
                        last_state_update = time.time()
                        while True:
                            chunk = response.read(chunk_size)
                            if not chunk:
                                break
                            f.write(chunk)
                            total_downloaded += len(chunk)
                            
                            # Periodically update state for very large files (every 5 seconds)
                            if state and time.time() - last_state_update > 5:
                                state.mark_partial(url, str(output_path), total_downloaded, state_fips)
                                last_state_update = time.time()
                    
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
                         timeout: int = 60, state: DownloadState = None, 
                         discover_files: bool = False):
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
        discover_files: If True, scrape directories to discover all available files
    """
    state_name = STATES.get(state_fips, f"State {state_fips}")
    
    print(f"\n{'='*70}")
    print(f"Downloading data for {state_name} (FIPS: {state_fips})")
    print(f"{'='*70}")
    
    download_tasks = []
    
    # If discover_files is True, scrape directories instead of using hardcoded patterns
    if discover_files:
        print(f"\nDiscovering available files from Census Bureau...")
        discovered = discover_state_files(state_fips, year, dataset_types, timeout)
        
        # Store all discovered URLs in state
        all_urls = set()
        for dataset_type, urls in discovered.items():
            all_urls.update(urls)
        
        if state:
            state.set_discovered_urls(state_fips, all_urls)
        
        print(f"Total files discovered: {len(all_urls)}")
        
        # Build download tasks from discovered URLs
        for url in all_urls:
            filename = url.split('/')[-1]
            output_path = output_dir / state_fips / filename
            
            # Skip if already completed
            if state and state.is_completed(str(output_path)):
                continue
            
            download_tasks.append((url, output_path))
    
    else:
        # Original behavior: use hardcoded county list
        counties = get_county_list(state_fips, year)
        
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

def discover_and_populate_state(state_fips: str, year: int, dataset_types: List[str], 
                                 timeout: int, state: Union['DownloadState', 'DownloadStateDB']) -> int:
    """
    Discover available files for a state and populate the state database without downloading.
    
    Args:
        state_fips: State FIPS code
        year: Year to discover
        dataset_types: List of dataset types to discover
        timeout: Request timeout in seconds
        state: DownloadState or DownloadStateDB object for tracking
        
    Returns:
        Number of URLs discovered
    """
    state_name = STATES.get(state_fips, f"State {state_fips}")
    
    print(f"\n{'='*70}")
    print(f"Discovering files for {state_name} (FIPS: {state_fips})")
    print(f"{'='*70}")
    
    print(f"\nDiscovering available files from Census Bureau...")
    discovered = discover_state_files(state_fips, year, dataset_types, timeout)
    
    # Store all discovered URLs in state
    all_urls = set()
    for dataset_type, urls in discovered.items():
        all_urls.update(urls)
    
    if state:
        state.set_discovered_urls(state_fips, all_urls)
    
    print(f"Total files discovered: {len(all_urls)}")
    print(f"URLs populated in state database")
    
    return len(all_urls)


def create_state_tracker(state_file: Path, use_db: bool = None) -> Union['DownloadState', 'DownloadStateDB']:
    """
    Create appropriate state tracker (DuckDB or JSON).
    
    Args:
        state_file: Path to state file (with .json or .duckdb extension)
        use_db: Force DB usage (True), JSON usage (False), or auto-detect (None)
        
    Returns:
        DownloadState or DownloadStateDB instance
    """
    # If use_db is explicitly False, use JSON
    if use_db is False:
        json_path = state_file.with_suffix('.json')
        print(f"Using JSON state tracker: {json_path}")
        return DownloadState(json_path)

    # Otherwise, always try to use DuckDB
    if not DUCKDB_AVAILABLE:
        print("Warning: DuckDB not available. Falling back to JSON.")
        print("Install DuckDB with: pip install duckdb>=0.9.0")
        json_path = state_file.with_suffix('.json')
        return DownloadState(json_path)

    db_path = state_file.with_suffix('.duckdb')
    # Ensure the DuckDB file exists (create if needed)
    if not db_path.exists():
        try:
            import duckdb
            duckdb.connect(str(db_path)).close()
        except Exception as e:
            print(f"Error creating DuckDB file: {e}")
    print(f"Using DuckDB state tracker: {db_path}")
    return DownloadStateDB(db_path)


def main():
    parser = argparse.ArgumentParser(
        description='Download TIGER/Line Shapefiles from US Census Bureau',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument('--year', type=int, default=2024,
                        help='Year to download (default: 2024)')
    parser.add_argument('--output', type=str, default='census/tiger',
                        help='Output directory (default: census/tiger)')
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
    parser.add_argument('--discover', action='store_true',
                        help='Discover available files by scraping Census Bureau directories')
    parser.add_argument('--discover-only', action='store_true',
                        help='Only discover and populate URLs in state database, do not download files')
    parser.add_argument('--use-db', action='store_true', default=True,
                        help='Use DuckDB for state tracking (default: enabled)')
    parser.add_argument('--no-use-db', dest='use_db', action='store_false',
                        help='Use JSON for state tracking instead of DuckDB')
    parser.add_argument('--parallel', type=int, default=4,
                        help='Number of parallel downloads (default: 4)')
    parser.add_argument('--resume', action='store_true',
                        help='Resume from previous download session')
    parser.add_argument('--state-file', type=str, default='.tiger_download_state',
                        help='Path to state file (default: .tiger_download_state, extension added automatically)')
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
    
    # Determine state file path (check for both .json and .duckdb)
    output_dir = Path(args.output)
    state_file_base = output_dir / args.state_file
    
    # Auto-detect existing state file
    json_file = state_file_base.with_suffix('.json')
    db_file = state_file_base.with_suffix('.duckdb')
    
    # Determine which file exists
    existing_file = None
    if db_file.exists():
        existing_file = db_file
    elif json_file.exists():
        existing_file = json_file
    
    if args.show_status:
        if not existing_file:
            print(f"\nNo download state file found")
            print(f"Checked for: {json_file} or {db_file}")
            print("Start a download to create a state file.")
            return 1
        
        # Load existing state
        if existing_file.suffix == '.duckdb':
            download_state = DownloadStateDB(existing_file)
        else:
            download_state = DownloadState(existing_file)
        
        states_list = download_state.list_states_requested()
        
        if not states_list:
            print("\nNo states/territories have been requested for download yet.")
            return 0
        
        print(f"\n{'='*70}")
        print(f"Download Status Summary")
        print(f"{'='*70}")
        print(f"State File: {existing_file}")
        backend = "DuckDB" if existing_file.suffix == '.duckdb' else "JSON"
        print(f"Backend:    {backend}")
        print(f"{'='*70}\n")
        
        for state_fips in sorted(states_list):
            state_summary = download_state.get_state_summary(state_fips)
            urls = download_state.get_urls_for_state(state_fips)
            progress = download_state.get_download_progress(state_fips)
            
            state_name = state_summary.get('name', f"State {state_fips}")
            completed = state_summary.get('completed', 0)
            failed = state_summary.get('failed', 0)
            total = completed + failed
            
            print(f"State: {state_name} (FIPS: {state_fips})")
            
            # Show discovered count if available
            if progress['discovered'] > 0:
                print(f"  Discovered: {progress['discovered']}")
                print(f"  Completed:  {progress['completed']}")
                print(f"  Failed:     {progress['failed']}")
                print(f"  Pending:    {progress['pending']}")
                
                # Show progress percentage
                if progress['discovered'] > 0:
                    pct = (progress['completed'] / progress['discovered']) * 100
                    print(f"  Progress:   {pct:.1f}%")
            else:
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
            
            # Show sample pending URLs if available
            if progress['pending'] > 0 and progress['pending_urls']:
                print(f"  Sample Pending URLs ({min(3, len(progress['pending_urls']))}):")
                for url in progress['pending_urls'][:3]:
                    print(f"    ⊙ {url}")
            
            print()
        
        overall_summary = download_state.get_summary()
        print(f"{'='*70}")
        print(f"Overall Summary:")
        print(f"  Total Files Tracked: {overall_summary['total']}")
        print(f"  Completed:           {overall_summary['completed']}")
        print(f"  Failed:              {overall_summary['failed']}")
        print(f"{'='*70}\n")
        
        return 0
    
    # Validate discover-only mode requirements
    if args.discover_only and not args.states:
        print("Error: --discover-only requires --states to be specified")
        print("Use --list-states to see valid state FIPS codes")
        return 1
    
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
            print("Use --list-types to see valid dataset types")
            return 1
    else:
        # Default types depend on mode
        if args.discover_only:
            # For discover-only mode, default to EDGES, ADDR, FEATNAMES
            type_list = ['EDGES', 'ADDR', 'FEATNAMES']
        else:
            # For download mode, default to all county-level types
            type_list = COUNTY_LEVEL_TYPES
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Initialize state tracking - use appropriate backend
    use_db = args.use_db
    download_state = create_state_tracker(state_file_base, use_db=use_db)
    
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
    # Fix: Only use isinstance if DownloadStateDB is a type
    if DownloadStateDB is not None:
        is_duckdb = isinstance(download_state, DownloadStateDB)
    else:
        is_duckdb = False
    backend = "DuckDB" if is_duckdb else "JSON"
    state_file_actual = state_file_base.with_suffix('.duckdb' if is_duckdb else '.json')
    print(f"State Backend: {backend}")
    print(f"State File:    {state_file_actual}")
    print(f"{'='*70}\n")
    
    # If discover-only mode, populate URLs without downloading
    if args.discover_only:
        print(f"MODE: Discover-only (populating state database without downloading)\n")
        
        total_discovered = 0
        start_time = time.time()
        
        for state_fips in state_list:
            count = discover_and_populate_state(
                state_fips, args.year, type_list, args.timeout, download_state
            )
            total_discovered += count
        
        elapsed = time.time() - start_time
        
        # Final summary for discover-only
        print(f"\n{'='*70}")
        print(f"DISCOVERY SUMMARY")
        print(f"{'='*70}")
        print(f"Total URLs Discovered: {total_discovered}")
        print(f"States Processed:      {len(state_list)}")
        print(f"Elapsed Time:          {elapsed:.1f} seconds")
        print(f"State File:            {state_file_actual}")
        print(f"{'='*70}\n")
        print(f"URLs have been populated in the state database.")
        print(f"Use --show-status to view discovered URLs.")
        print(f"Use --resume to download the discovered files.")
        
        return 0
    
    # Download data for each state
    total_successful = 0
    total_failed = 0
    total_not_found = 0
    
    start_time = time.time()
    
    for state_fips in state_list:
        successful, failed, not_found = download_county_data(
            state_fips, args.year, output_dir, type_list, args.parallel, 
            args.timeout, download_state, discover_files=args.discover
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
    print(f"State File:       {state_file_actual}")
    print(f"{'='*70}\n")
    
    if total_failed > 0:
        print(f"Note: Use --resume to retry failed downloads")
    
    return 0 if total_failed == 0 else 1

if __name__ == '__main__':
    sys.exit(main())
