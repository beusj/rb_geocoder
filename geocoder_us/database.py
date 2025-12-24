"""
Database interface module for Geocoder-US Python port using DuckDB.
Provides geocoding functionality using TIGER/Line data in DuckDB format.
"""

import duckdb
import struct
import math
import jellyfish
from typing import List, Dict, Any, Optional, Tuple
from .address import Address


class Database:
    """
    Interface to a Geocoder-US database using DuckDB.
    
    DuckDB provides built-in spatial support through its spatial extension,
    eliminating the need for custom C extensions required by SQLite.
    """
    
    # Scoring weights for address matching
    STREET_WEIGHT = 3.0
    NUMBER_WEIGHT = 2.0
    PARITY_WEIGHT = 1.25
    CITY_WEIGHT = 1.0
    
    def __init__(self, filename: str, debug: bool = False, cache_size_mb: int = 512):
        """
        Initialize database connection.
        
        Args:
            filename: Path to DuckDB database file
            debug: Enable debug output
            cache_size_mb: Cache size in megabytes (DuckDB default is 512MB)
        """
        self.filename = filename
        self.debug = debug
        self.connection = duckdb.connect(filename, read_only=True)
        
        # Load spatial extension for geometry operations
        try:
            self.connection.execute("INSTALL spatial;")
            self.connection.execute("LOAD spatial;")
        except Exception as e:
            if self.debug:
                print(f"Note: Spatial extension may already be loaded: {e}")
        
        # Configure DuckDB performance settings
        self.connection.execute(f"SET memory_limit='{cache_size_mb}MB';")
        self.connection.execute("SET threads TO 4;")  # Use multiple cores
        
        # Create custom metaphone function using jellyfish
        self.connection.create_function("metaphone", self._metaphone, parameters=[str, int], return_type=str)
        self.connection.create_function("levenshtein", jellyfish.levenshtein_distance, parameters=[str, str], return_type=int)
    
    def _metaphone(self, text: str, length: int = 5) -> str:
        """
        Metaphone phonetic algorithm implementation.
        
        Args:
            text: String to encode
            length: Maximum length of metaphone code
            
        Returns:
            Metaphone code
        """
        if not text:
            return ""
        
        # Clean the text
        text = ''.join(c for c in text if c.isalnum())
        
        # Handle numbers
        if text.isdigit():
            return text[:length]
        
        # Handle single letters
        if len(text) == 1 and text.lower() in ['w', 'y']:
            return text.lower()
        
        # Use jellyfish metaphone
        try:
            result = jellyfish.metaphone(text)
            return result[:length] if result else ""
        except:
            return text[:length]
    
    def _execute(self, sql: str, params: Optional[List] = None) -> List[Dict[str, Any]]:
        """
        Execute SQL query and return results as list of dictionaries.
        
        Args:
            sql: SQL query string
            params: Query parameters
            
        Returns:
            List of result rows as dictionaries
        """
        if self.debug:
            print(f"SQL: {sql}")
            if params:
                print(f"PARAMS: {params}")
        
        cursor = self.connection.execute(sql, params or [])
        columns = [desc[0] for desc in cursor.description]
        rows = []
        for row in cursor.fetchall():
            rows.append(dict(zip(columns, row)))
        
        if self.debug:
            print(f"ROWS: {len(rows)}")
        
        return rows
    
    def _levenshtein_score(self, str1: str, str2: str) -> float:
        """
        Calculate normalized Levenshtein distance (0.0 = identical, 1.0 = completely different).
        
        Args:
            str1: First string
            str2: Second string
            
        Returns:
            Normalized distance score between 0.0 and 1.0
        """
        if not str1 or not str2:
            return 1.0
        
        dist = jellyfish.levenshtein_distance(str1.lower(), str2.lower())
        max_len = max(len(str1), len(str2))
        return dist / max_len if max_len > 0 else 0.0
    
    def places_by_zip(self, city: str, zip_code: str) -> List[Dict]:
        """Query places by ZIP code."""
        sql = """
            SELECT *, levenshtein(?, city) AS city_score
            FROM place WHERE zip = ?
            ORDER BY priority DESC
        """
        return self._execute(sql, [city, zip_code])
    
    def places_by_city(self, city: str, city_parts: List[str], state: Optional[str]) -> List[Dict]:
        """Query places by city name using metaphone matching."""
        if not city:
            city = ""
        
        # Build metaphone placeholders
        metaphones = ', '.join([f"metaphone('{part}', 5)" for part in city_parts])
        
        if state:
            sql = f"""
                SELECT *, levenshtein(?, city) AS city_score
                FROM place
                WHERE city_phone IN ({metaphones})
                AND state = ?
                ORDER BY priority DESC
            """
            params = [city, state]
        else:
            sql = f"""
                SELECT *, levenshtein(?, city) AS city_score
                FROM place
                WHERE city_phone IN ({metaphones})
                ORDER BY priority DESC
            """
            params = [city]
        
        return self._execute(sql, params)
    
    def features_by_street_and_zip(self, street: str, street_parts: List[str], zips: List[str]) -> List[Dict]:
        """Query features by street name and ZIP codes."""
        if not street_parts or not zips:
            return []
        
        metaphones = ', '.join([f"metaphone('{part}', 5)" for part in street_parts])
        zip_placeholders = ', '.join(['?' for _ in zips])
        
        sql = f"""
            SELECT feature.*, levenshtein(?, street) AS street_score
            FROM feature
            WHERE street_phone IN ({metaphones})
            AND feature.zip IN ({zip_placeholders})
        """
        params = [street] + zips
        return self._execute(sql, params)
    
    def more_features_by_street_and_zip(self, street: str, street_parts: List[str], zips: List[str]) -> List[Dict]:
        """Query features with relaxed ZIP matching (3-digit prefix)."""
        if not street_parts or not zips:
            return []
        
        metaphones = ', '.join([f"metaphone('{part}', 5)" for part in street_parts])
        
        # Use 3-digit ZIP prefixes for broader search
        zip3s = list(set(z[:3] + '%' for z in zips if z))
        like_conditions = ' OR '.join(['feature.zip LIKE ?' for _ in zip3s])
        
        sql = f"""
            SELECT feature.*, levenshtein(?, street) AS street_score
            FROM feature
            WHERE street_phone IN ({metaphones})
            AND ({like_conditions})
        """
        params = [street] + zip3s
        return self._execute(sql, params)
    
    def geocode(self, address_str: str, canonical_place: bool = False) -> List[Dict]:
        """
        Geocode an address string.
        
        Args:
            address_str: Address or place name string
            canonical_place: Return canonical place names if True
            
        Returns:
            List of geocoded results with lat/lon coordinates
        """
        # Parse the address
        address = Address(address_str)
        
        if self.debug:
            print(f"Parsed address: {address}")
        
        # Check if we have enough information
        if not address.city and not address.zip:
            return []
        
        results = []
        
        # Handle PO Box - geocode to ZIP
        if address.po_box() and address.zip:
            results = self._geocode_place(address, canonical_place)
        
        # Handle intersection
        elif address.intersection() and address.street and not address.number:
            results = self._geocode_intersection(address, canonical_place)
        
        # Handle street address
        elif address.street:
            results = self._geocode_address(address, canonical_place)
        
        # Fallback to place geocoding
        if not results:
            results = self._geocode_place(address, canonical_place)
        
        return results
    
    def _geocode_place(self, address: Address, canonical_place: bool) -> List[Dict]:
        """Geocode to a place (city/ZIP)."""
        places = []
        
        if address.zip:
            places = self.places_by_zip(address.text, address.zip)
        
        if not places:
            places = self.places_by_city(address.text, address.city_parts, address.state)
        
        return self._best_places(address, places, canonical_place)
    
    def _geocode_address(self, address: Address, canonical_place: bool) -> List[Dict]:
        """Geocode a street address with interpolation."""
        candidates = self._find_candidates(address)
        
        if not candidates:
            return []
        
        # If no street found, treat as place
        if 'street' not in candidates[0] or not candidates[0]['street']:
            return self._best_places(address, candidates, canonical_place)
        
        # Score and filter candidates
        self._score_candidates(address, candidates)
        self._best_candidates(candidates)
        
        # For now, return basic results without full interpolation
        # Full interpolation would require edge/range table joins
        for candidate in candidates:
            candidate['precision'] = 'street'  # or 'zip' or 'range'
            self._clean_record(candidate)
        
        return candidates
    
    def _geocode_intersection(self, address: Address, canonical_place: bool) -> List[Dict]:
        """Geocode an intersection."""
        # Intersection geocoding requires more complex logic
        # For now, fall back to address geocoding
        return self._geocode_address(address, canonical_place)
    
    def _find_candidates(self, address: Address) -> List[Dict]:
        """Find candidate addresses matching the input."""
        places = []
        
        # Find places
        if address.city:
            city = min(address.city, key=len) if address.city else ""
            if address.zip:
                places = self.places_by_zip(city, address.zip)
            if not places:
                places = self.places_by_city(city, address.city_parts, address.state)
        
        if not places:
            return []
        
        # Extract unique ZIP codes
        zips = list(set(p['zip'] for p in places if 'zip' in p))
        
        # If no street, return places
        if not address.street:
            return places
        
        # Find street features
        street = min(address.street, key=len) if address.street else ""
        candidates = self.features_by_street_and_zip(street, address.street_parts, zips)
        
        if not candidates:
            candidates = self.more_features_by_street_and_zip(street, address.street_parts, zips)
        
        # Merge place data into candidates
        candidates = self._merge_rows(candidates, places, ['zip'])
        
        return candidates
    
    def _merge_rows(self, dest: List[Dict], src: List[Dict], keys: List[str]) -> List[Dict]:
        """Merge source rows into destination rows by matching keys."""
        src_by_key = {}
        for row in src:
            key_vals = tuple(row.get(k) for k in keys)
            if key_vals not in src_by_key:
                src_by_key[key_vals] = []
            src_by_key[key_vals].append(row)
        
        result = []
        for row in dest:
            key_vals = tuple(row.get(k) for k in keys)
            if key_vals in src_by_key:
                for src_row in src_by_key[key_vals]:
                    merged = {**row, **src_row}
                    result.append(merged)
            else:
                result.append(row)
        
        return result
    
    def _score_candidates(self, address: Address, candidates: List[Dict]):
        """Assign scores to candidate results."""
        for candidate in candidates:
            score = 0.0
            denominator = 0.0
            
            # Street score
            if 'street_score' in candidate:
                street_score = (1.0 - candidate['street_score']) * self.STREET_WEIGHT
                score += street_score
            denominator += self.STREET_WEIGHT
            
            # City score
            if 'city_score' in candidate:
                city_score = (1.0 - candidate['city_score']) * self.CITY_WEIGHT
                score += city_score
            denominator += self.CITY_WEIGHT
            
            # Exact matches
            for key in ['state', 'zip']:
                addr_val = getattr(address, key, '').lower()
                cand_val = str(candidate.get(key, '')).lower()
                if addr_val == cand_val:
                    score += 1.0
                denominator += 1.0
            
            candidate['score'] = score / denominator if denominator > 0 else 0.0
    
    def _best_candidates(self, candidates: List[Dict]):
        """Keep only the best-scoring candidates."""
        if not candidates:
            return
        
        candidates.sort(key=lambda x: x.get('score', 0), reverse=True)
        best_score = candidates[0].get('score', 0)
        
        # Remove candidates with lower scores
        to_remove = []
        for i, candidate in enumerate(candidates):
            if candidate.get('score', 0) < best_score:
                to_remove.append(i)
        
        for i in reversed(to_remove):
            candidates.pop(i)
    
    def _best_places(self, address: Address, places: List[Dict], canonical_place: bool) -> List[Dict]:
        """Score and filter place results."""
        if not places:
            return []
        
        self._score_candidates(address, places)
        self._best_candidates(places)
        
        for place in places:
            place['precision'] = 'zip' if place.get('zip') == address.zip else 'city'
            self._clean_record(place)
        
        return places
    
    def _clean_record(self, record: Dict):
        """Clean up a result record."""
        # Format score
        if 'score' in record:
            record['score'] = round(record['score'], 3)
        
        # Remove internal fields
        for key in ['street_phone', 'city_phone', 'priority', 'street_score', 'city_score']:
            record.pop(key, None)
        
        # Replace None with empty string
        for key in list(record.keys()):
            if record[key] is None:
                record[key] = ""
    
    def close(self):
        """Close the database connection."""
        if self.connection:
            self.connection.close()
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
