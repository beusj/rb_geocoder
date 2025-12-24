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

def download_file(url: str, output_path: Path, retries: int = 3) -> tuple:
    """
    Download a file with retry logic.
    Returns (success: bool, url: str, message: str)
    """
    for attempt in range(retries):
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            if output_path.exists():
                return (True, url, f"Already exists: {output_path.name}")
            urllib.request.urlretrieve(url, output_path)
            file_size = output_path.stat().st_size
            return (True, url, f"Downloaded: {output_path.name} ({file_size:,} bytes)")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return (False, url, f"Not found (404): {url}")
            elif e.code == 524:
                # Retry 524 errors more times
                if attempt < retries + 2:
                    time.sleep(5 * (attempt + 1))
                    continue
                else:
                    return (False, url, f"HTTP Error 524 (timeout): {url}")
            elif attempt < retries - 1:
                time.sleep(1 * (attempt + 1))
            else:
                return (False, url, f"HTTP Error {e.code}: {url}")
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(1 * (attempt + 1))
            else:
                return (False, url, f"Error: {str(e)}")
    return (False, url, "Failed after retries")

def download_county_data(state_fips: str, year: int, output_dir: Path, 
                         dataset_types: List[str], parallel: int = 4):
    """
    Download county-level data for a state.
    """
    counties = get_county_list(state_fips, year)
    state_name = STATES.get(state_fips, f"State {state_fips}")
    
    print(f"\n{'='*70}")
    print(f"Downloading data for {state_name} (FIPS: {state_fips})")
    print(f"{'='*70}")
    
    download_tasks = []
    for dataset_type in dataset_types:
        if dataset_type in ['EDGES', 'ADDR', 'FACES', 'FEATNAMES']:
            # County-level datasets
            for county_fips in counties:
                url = construct_url(year, state_fips, county_fips, dataset_type)
                output_path = output_dir / state_fips / f"tl_{year}_{state_fips}{county_fips}_{dataset_type.lower()}.zip"
                download_tasks.append((url, output_path))
        else:
            # State-level or national datasets
            url = construct_url(year, state_fips, None, dataset_type)
            filename = url.split('/')[-1]
            output_path = output_dir / state_fips / filename
            download_tasks.append((url, output_path))
    
    # Download in parallel
    successful = 0
    failed = 0
    not_found = 0
    
    with ThreadPoolExecutor(max_workers=parallel) as executor:
        futures = {executor.submit(download_file, url, path): (url, path) 
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
    print(f"  Not Found: {not_found}")
    print(f"  Failed: {failed}")
    
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
        type_list = ['EDGES', 'ADDR', 'FACES', 'FEATNAMES']
    
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"\n{'='*70}")
    print(f"TIGER/Line Download Configuration")
    print(f"{'='*70}")
    print(f"Year:          {args.year}")
    print(f"Output Dir:    {output_dir.absolute()}")
    print(f"States:        {len(state_list)} state(s)")
    print(f"Dataset Types: {', '.join(type_list)}")
    print(f"Parallel DLs:  {args.parallel}")
    print(f"{'='*70}\n")
    
    # Download data for each state
    total_successful = 0
    total_failed = 0
    total_not_found = 0
    
    start_time = time.time()
    
    for state_fips in state_list:
        successful, failed, not_found = download_county_data(
            state_fips, args.year, output_dir, type_list, args.parallel
        )
        total_successful += successful
        total_failed += failed
        total_not_found += not_found
    
    elapsed = time.time() - start_time
    
    # Final summary
    print(f"\n{'='*70}")
    print(f"FINAL SUMMARY")
    print(f"{'='*70}")
    print(f"Total Successful: {total_successful}")
    print(f"Total Not Found:  {total_not_found}")
    print(f"Total Failed:     {total_failed}")
    print(f"Elapsed Time:     {elapsed:.1f} seconds")
    print(f"Output Directory: {output_dir.absolute()}")
    print(f"{'='*70}\n")
    
    return 0 if total_failed == 0 else 1

if __name__ == '__main__':
    sys.exit(main())
