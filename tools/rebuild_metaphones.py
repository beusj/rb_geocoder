#!/usr/bin/env python3
"""
Rebuild Metaphones for Geocoding Database

This script regenerates metaphone phonetic codes for city names and street names
in a geocoding database. This is equivalent to the Ruby bin/rebuild_metaphones script.

Metaphones are used for fuzzy matching of street and city names during geocoding.

Usage:
    python rebuild_metaphones.py <database_file> [options]

Example:
    python rebuild_metaphones.py geocoder.duckdb --verbose
"""

import sys
import argparse
import duckdb
import jellyfish
from pathlib import Path


# Import database validation utility
sys.path.insert(0, str(Path(__file__).parent.parent))
from tools.utils import validate_database_extension


def metaphone_function(text: str, length: int = 5) -> str:
    """
    Generate metaphone phonetic code for text.
    
    Args:
        text: Input text to encode
        length: Maximum length of metaphone code (default: 5)
        
    Returns:
        Metaphone code string
    """
    if not text:
        return ""
    
    # Clean the text - remove non-alphanumeric characters
    text = ''.join(c for c in text if c.isalnum())
    
    # Handle pure numeric strings
    if text.isdigit():
        return text[:length]
    
    # Handle single letters W and Y
    if len(text) == 1 and text.lower() in ['w', 'y']:
        return text.lower()
    
    # Use jellyfish metaphone algorithm
    try:
        result = jellyfish.metaphone(text)
        return result[:length] if result else ""
    except (ValueError, TypeError):
        # Fallback to truncated input if metaphone fails
        return text[:length]


def rebuild_metaphones(database_path: str, verbose: bool = False, dry_run: bool = False):
    """
    Rebuild all metaphone codes in the database.
    
    Args:
        database_path: Path to DuckDB or SQLite database
        verbose: Print detailed progress information
        dry_run: Preview changes without applying them
        
    Returns:
        Exit code (0 for success, 1 for error)
    """
    db_path = Path(database_path)
    
    if not db_path.exists():
        print(f"Error: Database file not found: {database_path}")
        return 1
    
    if verbose:
        print(f"Opening database: {database_path}")
    
    try:
        # Connect to database
        conn = duckdb.connect(str(db_path), read_only=dry_run)
        
        # Register metaphone function
        conn.create_function("metaphone", metaphone_function, parameters=[str, int], return_type=str)
        
        # Check if tables exist
        tables = conn.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'main' 
            AND table_name IN ('place', 'feature')
        """).fetchall()
        
        table_names = [t[0] for t in tables]
        
        if not table_names:
            print("Error: No 'place' or 'feature' tables found in database")
            return 1
        
        # Update place table (cities)
        if 'place' in table_names:
            if verbose:
                print("\nUpdating city metaphones in 'place' table...")
            
            # Count records to update
            count_query = "SELECT COUNT(*) FROM place WHERE city IS NOT NULL"
            total_cities = conn.execute(count_query).fetchone()[0]
            
            if verbose:
                print(f"  Found {total_cities} city records")
            
            if not dry_run:
                # Update metaphones
                update_query = """
                    UPDATE place 
                    SET city_phone = metaphone(city, 5)
                    WHERE city IS NOT NULL
                """
                conn.execute(update_query)
                
                # Verify updates
                updated = conn.execute("""
                    SELECT COUNT(*) FROM place 
                    WHERE city_phone IS NOT NULL AND city_phone != ''
                """).fetchone()[0]
                
                if verbose:
                    print(f"  ✓ Updated {updated} city metaphones")
            else:
                print(f"  [DRY RUN] Would update {total_cities} city metaphones")
        
        # Update feature table (streets)
        if 'feature' in table_names:
            if verbose:
                print("\nUpdating street metaphones in 'feature' table...")
            
            # Count records to update
            count_query = "SELECT COUNT(*) FROM feature WHERE street IS NOT NULL"
            total_streets = conn.execute(count_query).fetchone()[0]
            
            if verbose:
                print(f"  Found {total_streets} street records")
            
            if not dry_run:
                # Update metaphones
                update_query = """
                    UPDATE feature 
                    SET street_phone = metaphone(street, 5)
                    WHERE street IS NOT NULL
                """
                conn.execute(update_query)
                
                # Verify updates
                updated = conn.execute("""
                    SELECT COUNT(*) FROM feature 
                    WHERE street_phone IS NOT NULL AND street_phone != ''
                """).fetchone()[0]
                
                if verbose:
                    print(f"  ✓ Updated {updated} street metaphones")
            else:
                print(f"  [DRY RUN] Would update {total_streets} street metaphones")
        
        # Show some examples
        if verbose and not dry_run:
            print("\nExample metaphones:")
            print("  Cities:")
            examples = conn.execute("""
                SELECT city, city_phone 
                FROM place 
                WHERE city_phone IS NOT NULL AND city_phone != ''
                LIMIT 5
            """).fetchall()
            for city, phone in examples:
                print(f"    {city:20s} → {phone}")
            
            print("  Streets:")
            examples = conn.execute("""
                SELECT DISTINCT street, street_phone 
                FROM feature 
                WHERE street_phone IS NOT NULL AND street_phone != ''
                LIMIT 5
            """).fetchall()
            for street, phone in examples:
                print(f"    {street:20s} → {phone}")
        
        # Close connection
        conn.close()
        
        if dry_run:
            print("\n✓ Dry run complete - no changes made")
        else:
            print("\n✓ Metaphones rebuilt successfully!")
        
        return 0
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        if verbose:
            traceback.print_exc()
        return 1


def main():
    parser = argparse.ArgumentParser(
        description='Rebuild metaphone phonetic codes for geocoding database',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
About Metaphones:
  Metaphones are phonetic codes that represent how words sound. They're used
  for fuzzy matching of street and city names during geocoding. For example,
  "Main Street" and "Mane Streat" would both map to similar metaphone codes.

Examples:
  # Rebuild metaphones with progress output
  python rebuild_metaphones.py geocoder.duckdb --verbose

  # Preview changes without applying them
  python rebuild_metaphones.py geocoder.duckdb --dry-run --verbose

  # Quiet mode
  python rebuild_metaphones.py geocoder.duckdb
        """
    )
    
    parser.add_argument('database', help='Path to DuckDB database file (.duckdb or .db extension required)')
    parser.add_argument('-v', '--verbose', action='store_true', 
                       help='Print detailed progress information')
    parser.add_argument('--dry-run', action='store_true',
                       help='Preview changes without applying them')
    
    args = parser.parse_args()
    
    # Validate database extension
    try:
        validate_database_extension(args.database)
    except ValueError as e:
        parser.error(str(e))
    
    return rebuild_metaphones(args.database, args.verbose, args.dry_run)


if __name__ == '__main__':
    sys.exit(main())
