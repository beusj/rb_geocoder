#!/usr/bin/env python3
"""
Example usage of Geocoder-US Python port.
Demonstrates basic address parsing and geocoding functionality.
"""

from geocoder_us import Address, Database

def demo_address_parsing():
    """Demonstrate address parsing capabilities."""
    print("=" * 70)
    print("ADDRESS PARSING DEMO")
    print("=" * 70)
    
    test_addresses = [
        "1600 Pennsylvania Ave, Washington DC 20502",
        "350 5th Ave, New York NY 10118",
        "1 Infinite Loop, Cupertino CA 95014",
        "Seattle, WA",
        "90210",
        "PO Box 123, Portland OR 97201",
        "Main St & 1st Ave, Springfield IL",
    ]
    
    for addr_str in test_addresses:
        print(f"\nInput: {addr_str}")
        addr = Address(addr_str)
        print(f"  Number: {addr.number}")
        print(f"  Street: {addr.street[:2] if len(addr.street) > 2 else addr.street}")
        print(f"  City:   {addr.city}")
        print(f"  State:  {addr.state}")
        print(f"  ZIP:    {addr.zip}")
        
        if addr.po_box():
            print("  [PO Box detected]")
        if addr.intersection():
            print("  [Intersection detected]")


def demo_geocoding(db_path: str):
    """Demonstrate geocoding with a database."""
    print("\n" + "=" * 70)
    print("GEOCODING DEMO")
    print("=" * 70)
    
    try:
        with Database(db_path, debug=False) as db:
            test_addresses = [
                "1600 Pennsylvania Ave, Washington DC",
                "New York NY",
                "90210",
            ]
            
            for addr_str in test_addresses:
                print(f"\nGeocoding: {addr_str}")
                results = db.geocode(addr_str)
                
                if results:
                    for i, result in enumerate(results[:3], 1):  # Show top 3
                        print(f"  Result {i}:")
                        print(f"    Lat/Lon: {result.get('lat', 'N/A')}, {result.get('lon', 'N/A')}")
                        print(f"    Precision: {result.get('precision', 'N/A')}")
                        print(f"    Score: {result.get('score', 'N/A')}")
                        print(f"    City: {result.get('city', 'N/A')}, {result.get('state', 'N/A')} {result.get('zip', '')}")
                else:
                    print("  No results found")
                    
    except FileNotFoundError:
        print(f"\nDatabase not found at: {db_path}")
        print("Skipping geocoding demo (database required)")
    except Exception as e:
        print(f"\nError during geocoding: {e}")
        print("Skipping geocoding demo")


def demo_comparison():
    """Show comparison with Ruby version."""
    print("\n" + "=" * 70)
    print("PYTHON vs RUBY COMPARISON")
    print("=" * 70)
    
    print("""
Ruby Version:
-------------
require 'geocoder/us'
db = Geocoder::US::Database.new("/path/to/geocoder.db")
results = db.geocode("1600 Pennsylvania Ave, Washington DC")
puts results[0][:lat]  # Access as hash

Python Version:
--------------
from geocoder_us import Database
db = Database("/path/to/geocoder.db")
results = db.geocode("1600 Pennsylvania Ave, Washington DC")
print(results[0]['lat'])  # Access as dict

Key Differences:
----------------
1. No custom C extensions needed (DuckDB has built-in spatial support)
2. Better performance with parallel queries (DuckDB uses multiple cores)
3. Context manager support (with statement)
4. Type hints for better IDE support
5. More pythonic API (snake_case, list of dicts)
    """)


def main():
    """Run all demos."""
    import sys
    
    # Always run address parsing demo (no database needed)
    demo_address_parsing()
    
    # Show comparison
    demo_comparison()
    
    # Try geocoding if database path provided
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
        demo_geocoding(db_path)
    else:
        print("\n" + "=" * 70)
        print("To test geocoding, run:")
        print(f"  python {sys.argv[0]} /path/to/geocoder.db")
        print("=" * 70)


if __name__ == "__main__":
    main()
