# GitHub Copilot Instructions for rb_geocoder

## Project Overview

**Geocoder-US** is a US address geocoding library that parses street addresses and performs fuzzy lookups against TIGER/Line census data. This project includes both Ruby and Python implementations.

### Key Technologies
- **Primary Language**: Python 3.8+ (modern refactor) + Ruby (legacy)
- **Database**: DuckDB (Python) and SQLite3 (Ruby)
- **Spatial Operations**: DuckDB spatial extension (Python) and custom C extensions (Ruby)
- **String Matching**: Jellyfish library (Python) for metaphone and Levenshtein distance

## Architecture

### Python Implementation (Recommended)
The Python/DuckDB implementation is the modern, actively developed version:

```
geocoder_us/
├── __init__.py      # Package exports: Address, Database
├── constants.py     # MapDict class, state/street abbreviations
├── address.py       # Address parsing logic
└── database.py      # DuckDB interface for geocoding
```

### Ruby Implementation (Legacy)
The Ruby/SQLite3 implementation is the original version:

```
lib/geocoder/us/
├── database.rb      # SQLite3 interface
├── address.rb       # Address parsing
└── constants.rb     # Abbreviation mappings
```

### Key Architectural Decisions

1. **Python over Ruby** (see REFACTORING_SUMMARY.md)
   - Better geospatial ecosystem
   - No custom C extensions needed
   - Easier deployment and containerization
   - Better performance (2-6x faster)

2. **DuckDB over SQLite3**
   - Built-in spatial support (no custom C extensions)
   - Multi-core query execution (no global mutex)
   - Columnar storage and SIMD optimizations
   - Modern SQL features (CTEs, window functions)

3. **Security First**
   - All SQL queries use parameterized inputs
   - Metaphones pre-computed in Python (not in SQL)
   - Input sanitization in Address class
   - No string interpolation of user data

## Code Conventions

### Python Code Style
- **Follow PEP 8** for formatting
- **Use type hints** for function signatures (Python 3.8+ syntax)
- **Docstrings**: Use for public methods and classes
- **Naming**: 
  - Classes: `PascalCase` (e.g., `Address`, `Database`)
  - Functions/methods: `snake_case` (e.g., `geocode`, `clean_phone`)
  - Constants: `UPPER_SNAKE_CASE` (e.g., `STATE`, `DIRECTIONAL`)
- **Quotes**: Use double quotes for strings (existing convention)
- **Line length**: 100 characters (flexible, prioritize readability)

### Ruby Code Style
- **Follow Ruby style guide**
- **Use symbols** for hash keys (e.g., `:lat`, `:lon`)
- **Naming**: 
  - Modules: `CamelCase` (e.g., `Geocoder::US`)
  - Methods: `snake_case`
  - Constants: `UPPER_SNAKE_CASE`

### Testing
- **Python**: Use pytest for all Python tests
- **Ruby**: Use Ruby's test framework
- **Test files**: 
  - Python: `test_*.py` or `*_test.py`
  - Ruby: `test/*.rb`
- **Coverage**: Aim for high coverage on core parsing/geocoding logic

## Common Patterns

### Address Parsing
Addresses are parsed into structured components:
```python
from geocoder_us import Address

addr = Address("1600 Pennsylvania Ave, Washington DC 20502")
# Components: number, street, city, state, zip, plus4
# Multiple variations stored for fuzzy matching
```

### Geocoding
Geocoding uses fuzzy matching with metaphone and Levenshtein:
```python
from geocoder_us import Database

with Database("/path/to/geocoder.db") as db:
    results = db.geocode("1600 Pennsylvania Ave, Washington DC")
    # Returns list of matches with lat/lon and confidence scores
```

### Constants and Abbreviations
The `MapDict` class provides bidirectional, case-insensitive lookups:
```python
from geocoder_us.constants import STATE, SUFFIX_TYPE

STATE["California"]  # "CA"
STATE["CA"]          # "California"
SUFFIX_TYPE["Street"]  # "St"
SUFFIX_TYPE["St"]      # "Street"
```

## Building and Testing

### Python Development

#### Setup
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # or: venv\Scripts\activate on Windows

# Install dependencies
pip install -r requirements.txt

# Or install in development mode
pip install -e .
```

#### Running Tests
```bash
# Run all Python tests
pytest test_geocoder_us.py -v

# Run specific test class
pytest test_geocoder_us.py::TestAddress -v

# Run with coverage
pytest test_geocoder_us.py --cov=geocoder_us --cov-report=html
```

#### Running Demo
```bash
# Address parsing only (no database)
python examples/demo_python.py

# With geocoding (requires database)
python examples/demo_python.py /path/to/geocoder.db
```

#### Linting
```bash
# Format with black (if configured)
black geocoder_us/

# Check with flake8 (if configured)
flake8 geocoder_us/

# Type checking with mypy (if configured)
mypy geocoder_us/
```

### Ruby Development

#### Setup
```bash
# Install Ruby dependencies
gem install text fastercsv sqlite3

# Or use bundler
bundle install
```

#### Running Tests
```bash
# Run Ruby tests
ruby test/run.rb

# With database
ruby test/run.rb /path/to/geocoder.db
```

#### Building
```bash
# Build C extensions and gem
make

# Install gem
make install
```

## Database Building

### Python/DuckDB (Recommended)
```bash
# Download TIGER/Line data
python census/zip_dl.py --states 06 --output /data/tiger/

# Import into DuckDB
python tools/tiger_import_duckdb.py geocoder.db /data/tiger/ --verbose

# Generate metaphones
python tools/rebuild_metaphones.py geocoder.db --verbose
```

### Ruby/SQLite3 (Legacy)
```bash
# Build C extensions first
make

# Import TIGER/Line data
build/tiger_import /opt/tiger/geocoder.db /opt/tiger

# Generate metaphones
bin/rebuild_metaphones /opt/tiger/geocoder.db

# Build indexes
build/build_indexes /opt/tiger/geocoder.db
```

See `DATABASE_BUILD_GUIDE.md` for detailed instructions.

## Important Files

### Documentation
- `README.md` - Main project documentation (Ruby-focused)
- `README_PYTHON.md` - Python API documentation
- `IMPLEMENTATION_GUIDE.md` - Python implementation guide
- `DATABASE_BUILD_GUIDE.md` - Database building guide
- `REFACTORING_SUMMARY.md` - Ruby→Python migration rationale

### Configuration
- `requirements.txt` - Python dependencies
- `setup.py` - Python package setup
- `Gemfile` - Ruby dependencies (if exists)
- `gemspec` - Ruby gem specification

### Tools
- `tools/tiger_import_duckdb.py` - Import TIGER/Line to DuckDB
- `tools/rebuild_metaphones.py` - Generate phonetic codes
- `census/zip_dl.py` - Download TIGER/Line data

### Examples
- `examples/demo_python.py` - Python usage examples
- `demos/` - Ruby demo scripts

## Security Considerations

### Always
- ✅ Use parameterized SQL queries (NEVER string interpolation)
- ✅ Pre-compute metaphones in Python before SQL
- ✅ Validate and sanitize all user inputs
- ✅ Avoid SQL injection through proper query construction

### Never
- ❌ Don't use string formatting in SQL: `f"WHERE city = '{user_input}'"`
- ❌ Don't compute phonetic codes in SQL: `metaphone('{user_input}', 5)`
- ❌ Don't trust user input without validation
- ❌ Don't commit API keys, credentials, or secrets

## Troubleshooting

### Python Import Errors
If you get `ModuleNotFoundError: No module named 'geocoder_us'`:
```bash
# Add to PYTHONPATH
export PYTHONPATH=/path/to/rb_geocoder:$PYTHONPATH

# Or install as package
pip install -e .
```

### DuckDB Spatial Extension
If you get spatial extension errors:
```python
import duckdb
conn = duckdb.connect(':memory:')
conn.execute("INSTALL spatial;")
conn.execute("LOAD spatial;")
```

### Poor Geocoding Results
- Check input format (standard US address format)
- Try different abbreviations and variations
- Ensure database has coverage for the area
- Enable debug mode: `Database(path, debug=True)`

## Git Workflow

### Branches
- `main` or `master` - Stable release branch
- Feature branches - For new development

### Commits
- Write clear, descriptive commit messages
- Reference issues when applicable
- Keep commits focused and atomic

### Pull Requests
- Include description of changes
- Reference related issues
- Ensure tests pass
- Update documentation if needed

## Resources

- **TIGER/Line Data**: https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html
- **DuckDB Docs**: https://duckdb.org/docs/
- **DuckDB Spatial**: https://duckdb.org/docs/extensions/spatial.html
- **Jellyfish (Metaphone)**: https://github.com/jamesturk/jellyfish
- **Original Geocoder::US**: https://github.com/geocommons/geocoder

## Quick Reference

### Parse an Address
```python
from geocoder_us import Address
addr = Address("123 Main St, Springfield IL 62701")
print(f"{addr.number} {addr.street} {addr.city} {addr.state} {addr.zip}")
```

### Geocode an Address
```python
from geocoder_us import Database
with Database("geocoder.db") as db:
    results = db.geocode("123 Main St, Springfield IL")
    if results:
        print(f"Lat: {results[0]['lat']}, Lon: {results[0]['lon']}")
```

### Run Tests
```bash
pytest test_geocoder_us.py -v
```

### Build Database from TIGER/Line
```bash
python tools/tiger_import_duckdb.py geocoder.db /data/tiger/ --verbose
```

---

When writing code for this project, prioritize:
1. **Security** - Parameterized queries, input validation
2. **Simplicity** - Clear, maintainable code
3. **Performance** - Efficient algorithms, proper indexing
4. **Documentation** - Clear docstrings and comments where needed
5. **Testing** - Comprehensive test coverage
