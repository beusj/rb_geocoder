"""
Shared utilities for geocoder tools.
"""

from pathlib import Path


def validate_database_extension(database_path: str) -> str:
    """
    Validate database file extension is .duckdb or .db.
    
    Args:
        database_path: Path to database file
        
    Returns:
        Validated database path
        
    Raises:
        ValueError: If extension is not .duckdb or .db
    """
    path = Path(database_path)
    extension = path.suffix.lower()
    
    if extension not in ['.duckdb', '.db']:
        raise ValueError(
            f"Invalid database extension '{extension}'. "
            f"Database file must have extension .duckdb or .db"
        )
    
    return database_path
