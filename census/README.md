# Automate download of TIGER/LINE Files

Example use

```sh
cd census
# 13 is Georgia
# Downloads to census/tiger by default, uses DuckDB state tracking by default
python zip_dl.py --states 13 --types EDGES,ADDR,FEATNAMES

# To use JSON state tracking instead of DuckDB
python zip_dl.py --states 13 --types EDGES,ADDR,FEATNAMES --no-use-db

# To specify a custom output directory
python zip_dl.py --states 13 --output /data/tiger --types EDGES,ADDR,FEATNAMES

# Discover-only mode: populate state database with URLs without downloading
# This is useful for planning downloads and checking what's available
python zip_dl.py --discover-only --states 13 --types EDGES,ADDR,FEATNAMES

# After discovering, check the status
python zip_dl.py --show-status --output census/tiger

# Then download the discovered files
python zip_dl.py --states 13 --discover --resume
```

Load into database

```sh
cd src
../build/tiger_import .
./census/georgia.db ../census/tiger/13/
```