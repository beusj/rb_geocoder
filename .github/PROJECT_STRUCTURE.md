# Project Structure Guide

This document provides a comprehensive overview of the rb_geocoder repository structure.

## Directory Tree

```
rb_geocoder/
├── .github/                    # GitHub configuration and Copilot hints
│   ├── copilot-instructions.md # Copilot context and guidelines
│   └── PROJECT_STRUCTURE.md    # This file
│
├── .vscode/                    # VS Code configuration
│   └── settings.json          # Python environment settings
│
├── geocoder_us/               # Python package (MAIN - Modern Implementation)
│   ├── __init__.py           # Package exports: Address, Database
│   ├── address.py            # Address parsing and normalization
│   ├── constants.py          # MapDict class, abbreviations, mappings
│   └── database.py           # DuckDB geocoding interface
│
├── lib/geocoder/us/          # Ruby library (Legacy Implementation)
│   ├── address.rb            # Ruby address parsing
│   ├── constants.rb          # Ruby constants and abbreviations
│   ├── database.rb           # SQLite3 database interface
│   └── ...                   # Other Ruby support files
│
├── tools/                    # Database building utilities (Python)
│   ├── README.md            # Tools documentation
│   ├── tiger_import_duckdb.py  # Import TIGER/Line to DuckDB
│   └── rebuild_metaphones.py   # Generate phonetic codes
│
├── census/                   # TIGER/Line data download tools
│   ├── README.md            # Census data download guide
│   └── zip_dl.py            # TIGER/Line downloader script
│
├── examples/                 # Usage examples
│   └── demo_python.py       # Python geocoding demonstration
│
├── demos/                    # Ruby demo scripts
│   └── ...                  # Various Ruby demonstrations
│
├── test/                     # Ruby test suite
│   ├── run.rb               # Ruby test runner
│   ├── address.rb           # Address parsing tests
│   ├── constants.rb         # Constants tests
│   ├── database.rb          # Database tests
│   └── data/                # Test fixtures
│
├── test_geocoder_us.py      # Python test suite (pytest)
│
├── src/                      # C source code for Ruby extensions
│   ├── shp2sqlite/          # Shapefile to SQLite converter
│   ├── metaphone/           # Metaphone C implementation
│   └── ...                  # Other C utilities
│
├── build/                    # Build scripts and compiled binaries
│   ├── tiger_import         # Ruby TIGER/Line importer
│   ├── build_indexes        # Index builder
│   └── rebuild_cluster      # Database optimizer
│
├── bin/                      # Executable scripts
│   └── rebuild_metaphones   # Ruby metaphone generator
│
├── conf/                     # Configuration files
│   └── ...                  # Various config files
│
├── doc/                      # Additional documentation
│   └── ...                  # Generated docs
│
├── debian/                   # Debian packaging files
│   └── ...                  # Package metadata
│
├── navteq/                   # NAVTEQ data support (optional)
│   └── ...                  # NAVTEQ-specific tools
│
├── Documentation Files
├── README.md                # Main project documentation
├── README.rdoc             # Ruby documentation (rdoc format)
├── README_PYTHON.md        # Python API documentation
├── IMPLEMENTATION_GUIDE.md # Python implementation guide
├── DATABASE_BUILD_GUIDE.md # Database building tutorial
├── REFACTORING_SUMMARY.md  # Ruby→Python migration rationale
├── REST.rdoc               # REST API documentation
├── History.txt             # Changelog
├── TODO.txt                # Future enhancements
├── LICENSE.txt             # GPLv3 License
│
├── Configuration Files
├── requirements.txt        # Python dependencies
├── setup.py               # Python package setup
├── gemspec                # Ruby gem specification
├── Makefile              # Build automation
├── Manifest.txt          # Gem manifest
├── setup.rb              # Ruby setup script
├── .gitignore            # Git ignore patterns
│
└── Generated/Temporary
    └── ...                # Build artifacts, downloaded data, etc.
```

## Key Directories Explained

### `/geocoder_us/` - Python Package (Active Development)

The primary Python implementation using DuckDB. This is the **recommended** version for new projects.

**Files:**
- `__init__.py` - Package initialization, exports `Address` and `Database` classes
- `constants.py` - Abbreviation mappings and the `MapDict` bidirectional dictionary class
- `address.py` - Parses US addresses into structured components
- `database.py` - DuckDB interface for geocoding with fuzzy matching

**Key Features:**
- No C extensions required
- Multi-core query execution
- Built-in spatial support via DuckDB
- Type hints for better IDE support
- Metaphone and Levenshtein string matching

**Usage:**
```python
from geocoder_us import Address, Database

# Parse address
addr = Address("1600 Pennsylvania Ave NW, Washington DC 20502")

# Geocode (requires database)
with Database("geocoder.db") as db:
    results = db.geocode("1600 Pennsylvania Ave, Washington DC")
```

### `/lib/geocoder/us/` - Ruby Library (Legacy)

Original Ruby implementation using SQLite3. Still maintained but Python version is preferred.

**Files:**
- `database.rb` - SQLite3 interface with custom C extensions
- `address.rb` - Ruby address parser
- `constants.rb` - Ruby constants and mappings

**Key Features:**
- Mature, well-tested codebase
- Requires custom-patched sqlite3-ruby gem
- Global mutex for thread safety
- C extensions for performance

**Usage:**
```ruby
require 'geocoder/us'
db = Geocoder::US::Database.new("/path/to/geocoder.db")
results = db.geocode("1600 Pennsylvania Ave, Washington DC")
```

### `/tools/` - Database Building Tools (Python)

Python scripts for building geocoding databases from TIGER/Line shapefiles.

**tiger_import_duckdb.py**
- Imports TIGER/Line shapefiles into DuckDB
- Creates schema, imports edges, addresses, feature names
- Generates metaphones automatically
- Builds indexes

```bash
python tools/tiger_import_duckdb.py geocoder.db /data/tiger/ --verbose
```

**rebuild_metaphones.py**
- Generates phonetic codes (metaphones) for fuzzy matching
- Updates `city_phone` and `street_phone` columns
- Used when adding new data or fixing phonetic codes

```bash
python tools/rebuild_metaphones.py geocoder.db --verbose
```

### `/census/` - TIGER/Line Data Downloader

Tools for downloading US Census TIGER/Line shapefiles.

**zip_dl.py**
- Downloads TIGER/Line data from Census FTP
- Supports parallel downloads
- Can download specific states or all US

```bash
# Download California (FIPS code 06)
python census/zip_dl.py --states 06 --output /data/tiger/ --parallel 8

# Download all US states
python census/zip_dl.py --output /data/tiger/
```

### `/examples/` - Usage Examples

Demonstration scripts showing how to use the library.

**demo_python.py**
- Shows address parsing
- Demonstrates geocoding (if database provided)
- Displays results in readable format

```bash
# Parse addresses only
python examples/demo_python.py

# Geocode with database
python examples/demo_python.py /path/to/geocoder.db
```

### `/test/` - Ruby Test Suite

Ruby unit and integration tests.

**Structure:**
- `run.rb` - Test runner
- `address.rb` - Address parsing tests
- `constants.rb` - Constants and mapping tests
- `database.rb` - Database and geocoding tests
- `data/` - Test fixtures and sample data

**Running:**
```bash
# Without database
ruby test/run.rb

# With database
ruby test/run.rb /path/to/geocoder.db
```

### `/test_geocoder_us.py` - Python Test Suite

Pytest-based test suite for Python implementation.

**Test Classes:**
- `TestAddress` - Address parsing tests
- `TestConstants` - MapDict and constants tests
- `TestStringMatching` - Metaphone and Levenshtein tests

**Running:**
```bash
pytest test_geocoder_us.py -v
pytest test_geocoder_us.py::TestAddress -v
pytest test_geocoder_us.py --cov=geocoder_us
```

### `/src/` - C Source Code

C implementations for Ruby extensions and utilities.

**Key Components:**
- `shp2sqlite/` - Shapefile to SQLite converter (derived from PostGIS)
- `metaphone/` - C metaphone implementation
- `libsqlite3_geocoder/` - Custom SQLite extensions for geocoding

**Note:** Python version doesn't need these (uses DuckDB's built-in features).

### `/build/` - Build Scripts

Compiled binaries and build scripts for Ruby version.

**Scripts:**
- `tiger_import` - Ruby-based TIGER/Line importer
- `build_indexes` - Creates database indexes
- `rebuild_cluster` - Optimizes database by clustering

**Usage:**
```bash
# Import TIGER/Line (Ruby)
build/tiger_import geocoder.db /data/tiger/

# Build indexes
build/build_indexes geocoder.db

# Optimize database
build/rebuild_cluster geocoder.db
```

## Documentation Files

### Main Documentation

- **README.md** - Project overview, Ruby-focused documentation
- **README_PYTHON.md** - Python API documentation and examples
- **README.rdoc** - Ruby documentation in RDoc format

### Guides

- **IMPLEMENTATION_GUIDE.md** - Detailed Python implementation guide
  - Quick start instructions
  - Architecture overview
  - Performance tuning
  - Troubleshooting
  
- **DATABASE_BUILD_GUIDE.md** - Complete database building tutorial
  - TIGER/Line data download
  - Import process (Python and Ruby)
  - Metaphone generation
  - Performance expectations

- **REFACTORING_SUMMARY.md** - Ruby→Python migration rationale
  - Performance comparison
  - Benefits of Python and DuckDB
  - Migration path
  - Technical decisions

### Other

- **REST.rdoc** - REST API documentation (for web service)
- **History.txt** - Version history and changelog
- **TODO.txt** - Planned features and improvements
- **LICENSE.txt** - GNU General Public License v3.0

## Configuration Files

### Python

- **requirements.txt** - Python dependencies
  ```
  duckdb>=0.9.0
  jellyfish>=0.11.0
  rapidfuzz>=3.0.0
  pytest>=7.0.0
  ```

- **setup.py** - Python package configuration for pip install

### Ruby

- **gemspec** - Ruby gem specification
- **Manifest.txt** - Files to include in gem
- **setup.rb** - Ruby setup script

### Build

- **Makefile** - Build automation (compiles C extensions, builds gem)

## Data Flow

### Database Building Flow

```
TIGER/Line Shapefiles (Census)
    ↓
[census/zip_dl.py] - Download
    ↓
Unzipped Shapefiles
    ↓
[tools/tiger_import_duckdb.py] - Import
    ↓
DuckDB Database (geocoder.db)
    ├── place table (cities, ZIP codes)
    ├── feature table (street names)
    ├── edge table (geometries)
    └── range table (address ranges)
    ↓
[tools/rebuild_metaphones.py] - Phonetic codes
    ↓
Ready for Geocoding
```

### Geocoding Flow

```
User Input Address String
    ↓
[Address.__init__] - Parse
    ├── Extract: number, street, city, state, ZIP
    ├── Normalize abbreviations
    └── Generate variations
    ↓
[Database.geocode] - Fuzzy Match
    ├── Look up by ZIP code
    ├── Match city (metaphone + Levenshtein)
    ├── Match street (metaphone + fuzzy)
    ├── Find address range
    └── Interpolate lat/lon
    ↓
List of Results
    ├── lat, lon (coordinates)
    ├── score (confidence)
    ├── Normalized address components
    └── FIPS codes
```

## Dependencies

### Python Dependencies

**Required:**
- `duckdb` - In-process SQL database with spatial support
- `jellyfish` - Phonetic string matching (metaphone, Levenshtein)

**Optional:**
- `rapidfuzz` - High-performance fuzzy string matching
- `pytest` - Testing framework
- `shapely` - Advanced geometry operations

### Ruby Dependencies

**Required:**
- `text` gem - String metrics (metaphone, Levenshtein)
- `sqlite3-ruby` - SQLite interface (custom-patched version needed)
- `fastercsv` - CSV parsing

**Build Dependencies:**
- gcc/g++ - C compiler
- make - Build automation
- SQLite3 dev files - Headers for compilation
- bash - Shell scripting

## Build Artifacts (Not in Git)

These are generated during build/use and ignored by git:

- `*.o`, `*.so` - Compiled C objects and shared libraries
- `*.pyc`, `__pycache__/` - Python bytecode
- `*.gem` - Built Ruby gems
- `*.db` - Geocoding databases
- Downloaded TIGER/Line files
- Test coverage reports
- Virtual environments (`venv/`, `.venv/`)

## Getting Started Paths

### I want to use the geocoder (Python)

1. Install: `pip install -r requirements.txt`
2. Get/build database (see DATABASE_BUILD_GUIDE.md)
3. Try example: `python examples/demo_python.py geocoder.db`
4. Read: README_PYTHON.md

### I want to use the geocoder (Ruby)

1. Build: `make`
2. Install: `make install` (as root)
3. Get/build database (see DATABASE_BUILD_GUIDE.md)
4. Read: README.md, README.rdoc

### I want to build a database

1. Download data: `python census/zip_dl.py --states 06 --output /data/tiger/`
2. Import: `python tools/tiger_import_duckdb.py geocoder.db /data/tiger/ --verbose`
3. (Optional) Rebuild metaphones: `python tools/rebuild_metaphones.py geocoder.db`
4. Read: DATABASE_BUILD_GUIDE.md

### I want to contribute code

1. Read: .github/copilot-instructions.md (this gives context)
2. Read: IMPLEMENTATION_GUIDE.md (architecture)
3. Set up dev environment: `pip install -r requirements.txt`
4. Run tests: `pytest test_geocoder_us.py -v`
5. Make changes, write tests, submit PR

## Migration Notes

### From Ruby to Python

The Python implementation is a **complete rewrite** with API compatibility:

**What's the same:**
- Core geocoding algorithm
- Address parsing logic
- Database schema (can convert)
- Result format (similar structure)

**What's different:**
- Language: Ruby → Python
- Database: SQLite3 → DuckDB
- No C extensions needed (Python)
- Better performance (2-6x faster)
- Easier deployment

**Migration checklist:**
1. Install Python dependencies
2. Convert database (or rebuild with Python tools)
3. Update code imports and syntax
4. Test thoroughly
5. Deploy

See REFACTORING_SUMMARY.md for detailed comparison.

## Questions?

- **General usage**: See README.md or README_PYTHON.md
- **Python implementation**: See IMPLEMENTATION_GUIDE.md
- **Database building**: See DATABASE_BUILD_GUIDE.md
- **Why Python/DuckDB**: See REFACTORING_SUMMARY.md
- **Code context**: See .github/copilot-instructions.md
- **REST API**: See REST.rdoc

## License

GNU General Public License v3.0 or later

Copyright (c) 2009 FortiusOne, Inc.
Based on original work by Schuyler Erle
