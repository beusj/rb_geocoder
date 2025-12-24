#!/usr/bin/env python3
"""
Unified TIGER/Line Download and Import Workflow

This script provides an integrated workflow that:
1. Downloads TIGER/Line files with robust error handling
2. Progressively imports files into the database as they are downloaded
3. Tracks the complete state: download → extract → load
4. Provides resume capability for interrupted workflows
5. Optionally cleans up ZIP files after successful import

Usage:
    python tiger_download_and_import.py <database> <output_dir> [options]

Example:
    # Download and import California data
    python tiger_download_and_import.py geocoder.duckdb ./tiger --states 06 --verbose
    
    # Resume interrupted workflow
    python tiger_download_and_import.py geocoder.duckdb ./tiger --resume --verbose
    
    # Progressive download and import with cleanup
    python tiger_download_and_import.py geocoder.duckdb ./tiger --states 06,36 --cleanup
"""

import sys
import os
import argparse
from pathlib import Path
import subprocess
import json
import time
from typing import Optional

# Add parent directory to path to import from census and tools
sys.path.insert(0, str(Path(__file__).parent.parent))

from census.zip_dl import download_county_data, DownloadState, STATES, DATASET_TYPES, COUNTY_LEVEL_TYPES
from tools.tiger_import_duckdb import import_tiger_data
from tools.utils import validate_database_extension


class WorkflowState:
    """Track the complete workflow state."""
    
    def __init__(self, state_file: Path):
        self.state_file = state_file
        self.data = self._load()
    
    def _load(self) -> dict:
        """Load state from file."""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    return json.load(f)
            except Exception:
                return self._default_state()
        return self._default_state()
    
    def _default_state(self) -> dict:
        return {
            'workflow': 'tiger_download_and_import',
            'version': '1.0',
            'started': time.time(),
            'states': {},
            'statistics': {
                'downloaded': 0,
                'imported': 0,
                'failed_download': 0,
                'failed_import': 0
            }
        }
    
    def save(self):
        """Save state to file."""
        try:
            self.data['last_updated'] = time.time()
            with open(self.state_file, 'w') as f:
                json.dump(self.data, f, indent=2)
        except Exception as e:
            print(f"Warning: Could not save workflow state: {e}")
    
    def update_state_status(self, state_code: str, status: str):
        """Update the status of a state."""
        if state_code not in self.data['states']:
            self.data['states'][state_code] = {}
        self.data['states'][state_code]['status'] = status
        self.data['states'][state_code]['timestamp'] = time.time()
        self.save()
    
    def mark_downloaded(self, state_code: str, count: int):
        """Mark files as downloaded for a state."""
        if state_code not in self.data['states']:
            self.data['states'][state_code] = {}
        self.data['states'][state_code]['downloaded'] = count
        self.data['statistics']['downloaded'] += count
        self.save()
    
    def mark_imported(self, state_code: str, count: int):
        """Mark files as imported for a state."""
        if state_code not in self.data['states']:
            self.data['states'][state_code] = {}
        self.data['states'][state_code]['imported'] = count
        self.data['statistics']['imported'] += count
        self.save()
    
    def get_summary(self) -> dict:
        """Get workflow summary."""
        return self.data['statistics']


def run_workflow(database: str, output_dir: str, states: Optional[list] = None,
                types: Optional[list] = None, parallel: int = 3, timeout: int = 60,
                verbose: bool = False, resume: bool = False, cleanup: bool = False):
    """
    Run the complete download and import workflow.
    
    Args:
        database: Path to DuckDB database
        output_dir: Output directory for TIGER files
        states: List of state FIPS codes (None = all states)
        types: List of dataset types (None = default geocoding types)
        parallel: Number of parallel downloads
        timeout: Download timeout in seconds
        verbose: Verbose output
        resume: Resume from previous workflow
        cleanup: Remove ZIP files after import
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Initialize workflow state
    workflow_state_file = output_path / '.tiger_workflow_state.json'
    workflow_state = WorkflowState(workflow_state_file)
    
    # Initialize download state
    download_state_file = output_path / '.tiger_download_state.json'
    download_state = DownloadState(download_state_file)
    
    # Initialize import state
    import_state_file = output_path / '.tiger_import_state.json'
    
    if resume:
        summary = workflow_state.get_summary()
        print(f"\n{'='*70}")
        print(f"Resuming workflow from previous session")
        print(f"{'='*70}")
        print(f"Downloaded: {summary['downloaded']}")
        print(f"Imported:   {summary['imported']}")
        print(f"{'='*70}\n")
    
    # Determine which states to process
    if states:
        state_list = states
    else:
        state_list = list(STATES.keys())
    
    # Determine dataset types
    if types:
        type_list = types
    else:
        type_list = COUNTY_LEVEL_TYPES
    
    print(f"\n{'='*70}")
    print(f"TIGER/Line Download and Import Workflow")
    print(f"{'='*70}")
    print(f"Database:      {database}")
    print(f"Output Dir:    {output_path.absolute()}")
    print(f"States:        {len(state_list)} state(s)")
    print(f"Dataset Types: {', '.join(type_list)}")
    print(f"Parallel DLs:  {parallel}")
    print(f"Timeout:       {timeout}s")
    print(f"Cleanup:       {cleanup}")
    print(f"{'='*70}\n")
    
    start_time = time.time()
    
    # Process each state
    for state_fips in state_list:
        state_name = STATES.get(state_fips, f"State {state_fips}")
        workflow_state.update_state_status(state_fips, 'downloading')
        
        print(f"\n{'='*70}")
        print(f"Processing {state_name} ({state_fips})")
        print(f"{'='*70}")
        
        # Download state data
        print(f"\nPhase 1: Downloading...")
        from census.zip_dl import get_county_list
        year = 2024
        successful, failed, not_found = download_county_data(
            state_fips, year, output_path, type_list, parallel, timeout, download_state
        )
        
        workflow_state.mark_downloaded(state_fips, successful)
        workflow_state.update_state_status(state_fips, 'importing')
        
        # Import state data progressively
        print(f"\nPhase 2: Importing into database...")
        state_output_dir = output_path / state_fips
        if state_output_dir.exists():
            result = import_tiger_data(
                database, str(state_output_dir), None, verbose, 
                progressive=True, cleanup=cleanup, state_file=str(import_state_file)
            )
            
            if result == 0:
                workflow_state.update_state_status(state_fips, 'completed')
                print(f"✓ {state_name} completed successfully")
            else:
                workflow_state.update_state_status(state_fips, 'import_failed')
                print(f"✗ {state_name} import failed")
        else:
            print(f"Warning: No files downloaded for {state_name}")
            workflow_state.update_state_status(state_fips, 'no_files')
    
    elapsed = time.time() - start_time
    
    # Final summary
    summary = workflow_state.get_summary()
    print(f"\n{'='*70}")
    print(f"WORKFLOW COMPLETE")
    print(f"{'='*70}")
    print(f"Files Downloaded: {summary['downloaded']}")
    print(f"Files Imported:   {summary['imported']}")
    print(f"Failed Downloads: {summary['failed_download']}")
    print(f"Failed Imports:   {summary['failed_import']}")
    print(f"Elapsed Time:     {elapsed:.1f} seconds ({elapsed/60:.1f} minutes)")
    print(f"Database:         {database}")
    print(f"Output Directory: {output_path.absolute()}")
    print(f"{'='*70}\n")
    
    return 0


def main():
    parser = argparse.ArgumentParser(
        description='Unified TIGER/Line download and import workflow',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument('database', help='Path to DuckDB database file (.duckdb or .db extension required)')
    parser.add_argument('output_dir', help='Output directory for TIGER/Line files')
    parser.add_argument('--states', type=str,
                       help='Comma-separated state FIPS codes (e.g., "06,36,48")')
    parser.add_argument('--types', type=str,
                       help='Comma-separated dataset types (e.g., "EDGES,ADDR")')
    parser.add_argument('--parallel', type=int, default=3,
                       help='Number of parallel downloads (default: 3, reduced from 4 for reliability)')
    parser.add_argument('--timeout', type=int, default=60,
                       help='Download timeout in seconds (default: 60)')
    parser.add_argument('-v', '--verbose', action='store_true',
                       help='Verbose output')
    parser.add_argument('--resume', action='store_true',
                       help='Resume from previous workflow')
    parser.add_argument('--cleanup', action='store_true',
                       help='Remove ZIP files after successful import')
    
    args = parser.parse_args()
    
    # Validate database extension
    try:
        validate_database_extension(args.database)
    except ValueError as e:
        parser.error(str(e))
    
    # Parse states
    state_list = None
    if args.states:
        state_list = [s.strip().zfill(2) for s in args.states.split(',')]
        invalid = [s for s in state_list if s not in STATES]
        if invalid:
            print(f"Error: Invalid state FIPS codes: {invalid}")
            return 1
    
    # Parse types
    type_list = None
    if args.types:
        type_list = [t.strip().upper() for t in args.types.split(',')]
        invalid = [t for t in type_list if t not in DATASET_TYPES]
        if invalid:
            print(f"Error: Invalid dataset types: {invalid}")
            return 1
    
    return run_workflow(
        args.database, args.output_dir, state_list, type_list,
        args.parallel, args.timeout, args.verbose, args.resume, args.cleanup
    )


if __name__ == '__main__':
    sys.exit(main())
