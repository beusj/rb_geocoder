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
```

Load into database

```sh
cd src
../build/tiger_import .
./census/georgia.db ../census/tiger/13/
```