"""
Geocoder-US: Python port of the US address geocoding library.

This library geocodes US street addresses using TIGER/Line data from
the US Census Bureau. It uses DuckDB with the spatial extension for
efficient geographic queries.

Usage:
    from geocoder_us import Database
    
    db = Database("/path/to/geocoder.db")
    results = db.geocode("1600 Pennsylvania Ave, Washington DC")
"""

__version__ = "3.0.0"
__author__ = "Python port of Geocoder::US by Schuyler Erle"

from .database import Database
from .address import Address

__all__ = ['Database', 'Address']
