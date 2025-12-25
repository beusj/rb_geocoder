# Python/DuckDB Implementation Guide

## Quick Start

### Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Or install individually
pip install duckdb jellyfish rapidfuzz pytest
```

### Basic Usage

```python
from geocoder_us import Address, Database

# Parse an address
addr = Address("1600 Pennsylvania Ave, Washington DC 20502")
print(f"Number: {addr.number}")
print(f"Street: {addr.street}")
print(f"City: {addr.city}")
print(f"State: {addr.state}")
print(f"ZIP: {addr.zip}")

# Geocode an address (requires database)
with Database("/path/to/geocoder.db") as db:
    results = db.geocode("1600 Pennsylvania Ave, Washington DC")
    for result in results:
        print(f"Lat: {result['lat']}, Lon: {result['lon']}")
        print(f"Score: {result['score']}")
```

### Run Tests

```bash
# Run all tests
pytest test_geocoder_us.py -v

# Run specific test
pytest test_geocoder_us.py::TestAddress::test_simple_address -v

# Run with coverage
pytest test_geocoder_us.py --cov=geocoder_us --cov-report=html
```

### Run Demo

```bash
# Address parsing only (no database needed)
python examples/demo_python.py

# With geocoding (requires database)
python examples/demo_python.py /path/to/geocoder.db
```

## Architecture

### Module Structure

```
geocoder_us/
├── __init__.py         # Package exports
├── constants.py        # Address constants and mappings
├── address.py          # Address parsing logic
└── database.py         # Database interface with DuckDB
```

### Key Classes

#### Address
Parses US address strings into structured components.

**Attributes:**
- `number` - House number (e.g., "1600")
- `street` - List of street name variations
- `city` - List of city name variations
- `state` - Two-letter state code (e.g., "DC")
- `zip` - 5-digit ZIP code
- `plus4` - 4-digit ZIP+4 extension
- `prenum`, `sufnum` - Number prefixes/suffixes

**Methods:**
- `po_box()` - Check if address is a PO Box
- `intersection()` - Check if address is an intersection
- `street_parts` - Get street substrings for fuzzy matching
- `city_parts` - Get city substrings for fuzzy matching

#### Database
Interface to geocoding database using DuckDB.

**Methods:**
- `geocode(address, canonical_place=False)` - Main geocoding method
- `places_by_zip(city, zip)` - Find places by ZIP code
- `places_by_city(city, parts, state)` - Find places by city name
- `close()` - Close database connection

**Features:**
- Automatic spatial extension loading
- CPU core auto-detection
- Metaphone phonetic matching
- Levenshtein distance scoring
- Context manager support

### Constants

The `constants.py` module provides bidirectional mappings via the `MapDict` class:

- `STATE` - State names ↔ abbreviations
- `DIRECTIONAL` - Compass directions (North → N)
- `PREFIX_TYPE` - Street prefix types (Avenue → Ave)
- `SUFFIX_TYPE` - Street suffix types (Street → St)
- `STD_ABBR` - Combined standard abbreviations
- `NAME_ABBR` - Place name abbreviations

Each MapDict supports:
- Case-insensitive lookup
- Bidirectional mapping (key→value, value→key)
- Regex pattern matching

## Design Decisions

### Why Pre-compute Metaphones?

Instead of calling metaphone() in SQL:
```python
# INSECURE - SQL injection risk
sql = f"WHERE city_phone IN (metaphone('{city}', 5))"
```

We pre-compute metaphones:
```python
# SECURE - parameterized query
metaphones = [self._metaphone(clean(part), 5) for part in city_parts]
sql = f"WHERE city_phone IN ({', '.join(['?'] * len(metaphones))})"
params = metaphones
```

Benefits:
- Prevents SQL injection
- Faster (computed once in Python)
- More testable
- Consistent behavior

### Why DuckDB Over SQLite?

1. **Built-in Spatial Support**: No custom C extensions
2. **Better Performance**: Columnar storage, SIMD, multi-core
3. **Easier Deployment**: Single pip install
4. **Modern Features**: Better SQL, window functions, CTEs
5. **Future-proof**: Active development, strong backing

### Why Jellyfish Library?

Jellyfish provides:
- Metaphone algorithm (phonetic matching)
- Levenshtein distance (fuzzy string matching)
- C-optimized implementations
- Well-tested and maintained

## Performance Tuning

### Database Configuration

```python
# Default settings (good for most use cases)
db = Database("geocoder.db", cache_size_mb=512)

# For high-performance server
db = Database("geocoder.db", cache_size_mb=2048)

# For memory-constrained environments
db = Database("geocoder.db", cache_size_mb=128)
```

### Threading

DuckDB automatically uses all available CPU cores. To limit:

```python
# In database.py __init__
num_threads = 2  # Limit to 2 threads
self.connection.execute(f"SET threads TO {num_threads};")
```

### Batch Geocoding

For geocoding many addresses:

```python
addresses = ["123 Main St, City ST", "456 Oak Ave, Town ST", ...]

with Database("geocoder.db") as db:
    results = [db.geocode(addr) for addr in addresses]
```

Or parallel:

```python
from concurrent.futures import ThreadPoolExecutor

def geocode_one(addr):
    # Each thread needs its own connection
    with Database("geocoder.db") as db:
        return db.geocode(addr)

with ThreadPoolExecutor(max_workers=4) as executor:
    results = list(executor.map(geocode_one, addresses))
```

## Troubleshooting

### Import Errors

```
ModuleNotFoundError: No module named 'geocoder_us'
```

**Solution:**
```bash
# Add current directory to PYTHONPATH
export PYTHONPATH=/path/to/rb_geocoder:$PYTHONPATH
python your_script.py

# Or install as package
pip install -e .
```

### DuckDB Spatial Extension

```
Error: Extension "spatial" is not loaded
```

**Solution:**
```python
# In database.py, spatial extension is loaded automatically
# If manual load needed:
conn.execute("INSTALL spatial;")
conn.execute("LOAD spatial;")
```

### Poor Geocoding Results

If geocoding returns no results or poor matches:

1. **Check input format**: Use standard US address format
2. **Try variations**: Different abbreviations, city names
3. **Check database**: Ensure database has data for the area
4. **Enable debug**: `Database(path, debug=True)` to see SQL queries

### Memory Issues

If running out of memory:

```python
# Reduce cache size
db = Database("geocoder.db", cache_size_mb=128)

# Or limit threads
# Edit database.py: num_threads = 1
```

## Testing

### Unit Tests

```bash
# Run all tests
pytest test_geocoder_us.py -v

# Run specific class
pytest test_geocoder_us.py::TestAddress -v

# Run with coverage
pytest test_geocoder_us.py --cov=geocoder_us
```

### Integration Testing

To test with actual database:

```python
def test_real_geocoding():
    db = Database("/path/to/real/geocoder.db")
    results = db.geocode("1600 Pennsylvania Ave, Washington DC")
    assert len(results) > 0
    assert results[0]['state'] == 'DC'
```

### Performance Testing

```python
import time

addresses = ["123 Main St, City ST"] * 1000

start = time.time()
with Database("geocoder.db") as db:
    for addr in addresses:
        db.geocode(addr)
elapsed = time.time() - start

print(f"Geocoded {len(addresses)} addresses in {elapsed:.2f}s")
print(f"Average: {elapsed/len(addresses)*1000:.2f}ms per address")
```

## Migration from Ruby

### Ruby to Python Equivalents

| Ruby | Python |
|------|--------|
| `require 'geocoder/us'` | `from geocoder_us import Database, Address` |
| `Geocoder::US::Database.new(path)` | `Database(path)` |
| `db.geocode(addr)` | `db.geocode(addr)` |
| `results[0][:lat]` | `results[0]['lat']` |
| `address.city` | `address.city` |
| `address.number.to_i` | `int(address.number)` |

### Database Migration

```python
import duckdb
import sqlite3

# Method 1: Attach SQLite database
duck = duckdb.connect('new_geocoder.db')
duck.execute("ATTACH 'old_geocoder.db' AS sqlite_db (TYPE sqlite);")
duck.execute("CREATE TABLE place AS SELECT * FROM sqlite_db.place;")
# Repeat for other tables

# Method 2: Export/Import via CSV
sqlite_conn = sqlite3.connect('old_geocoder.db')
df = pd.read_sql("SELECT * FROM place", sqlite_conn)
duck_conn = duckdb.connect('new_geocoder.db')
duck_conn.execute("CREATE TABLE place AS SELECT * FROM df;")
```

## Security

### Input Validation

All user inputs are validated:

```python
# Address parsing sanitizes input
addr = Address("1600 Pennsylvania Ave")  # Cleaned automatically

# Database queries use parameterization
# NO: f"WHERE city = '{user_input}'"  # SQL injection!
# YES: execute("WHERE city = ?", [user_input])
```

### SQL Injection Prevention

- All queries use parameterized inputs
- Metaphones pre-computed before SQL
- ZIP codes validated (digits only)
- No string interpolation of user input

### Recommendations

1. **Validate inputs** before geocoding
2. **Rate limit** geocoding API if exposing publicly
3. **Log queries** for security monitoring
4. **Keep dependencies updated** (`pip install -U`)

## Contributing

### Code Style

- Follow PEP 8
- Use type hints
- Add docstrings to public methods
- Write tests for new features

### Running Tests

```bash
# Before committing
pytest test_geocoder_us.py -v
```

### Pull Requests

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Run tests
6. Submit PR with description

## License

GNU General Public License v3.0 or later.

Based on original Geocoder::US by Schuyler Erle.
