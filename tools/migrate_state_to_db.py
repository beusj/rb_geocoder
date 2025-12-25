#!/usr/bin/env python3
"""
Migrate download state from JSON to DuckDB format.

Usage:
    python migrate_state_to_db.py <json_file> [db_file]
    
Example:
    python migrate_state_to_db.py ./tiger/.tiger_download_state.json
    python migrate_state_to_db.py old_state.json new_state.duckdb
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from census.download_state_db import migrate_json_to_db


def main():
    if len(sys.argv) < 2:
        print("Usage: python migrate_state_to_db.py <json_file> [db_file]")
        print("\nMigrate a JSON download state file to DuckDB format for better performance.")
        print("\nExamples:")
        print("  python migrate_state_to_db.py ./tiger/.tiger_download_state.json")
        print("  python migrate_state_to_db.py old_state.json new_state.duckdb")
        return 1
    
    json_path = Path(sys.argv[1])
    
    if not json_path.exists():
        print(f"Error: JSON file not found: {json_path}")
        return 1
    
    # Determine output path
    if len(sys.argv) >= 3:
        db_path = Path(sys.argv[2])
    else:
        # Use same name with .duckdb extension
        db_path = json_path.with_suffix('.duckdb')
    
    if db_path.exists():
        response = input(f"Database file {db_path} already exists. Overwrite? [y/N]: ")
        if response.lower() != 'y':
            print("Migration cancelled.")
            return 1
        db_path.unlink()
    
    print(f"\n{'='*70}")
    print(f"Migrating JSON to DuckDB")
    print(f"{'='*70}")
    print(f"Source: {json_path}")
    print(f"Target: {db_path}")
    print(f"{'='*70}\n")
    
    try:
        migrate_json_to_db(json_path, db_path)
        print(f"\n{'='*70}")
        print(f"Migration completed successfully!")
        print(f"{'='*70}")
        print(f"\nYou can now use the DuckDB state file with:")
        print(f"  python census/zip_dl.py --state-file {db_path.stem} --use-db ...")
        print(f"\nOr it will be auto-detected if you use the same base name.")
        return 0
    
    except Exception as e:
        print(f"\nError during migration: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
