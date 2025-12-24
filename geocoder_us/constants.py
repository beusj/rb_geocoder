"""
Constants module for Geocoder-US Python port.
Contains mappings for US address components, abbreviations, and state names.
"""

import re
from typing import Dict

class MapDict(dict):
    """
    A bidirectional dictionary that maps both keys to values and values to keys.
    Also maintains a regex pattern for matching all keys and values.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._build()
    
    def _build(self):
        """Build lowercase mappings and regex pattern."""
        # Add lowercase versions
        items = list(self.items())
        for key, value in items:
            self[key.lower()] = value
            self[value.lower()] = value
        
        # Build regex pattern
        all_terms = list(set(list(self.keys()) + list(self.values())))
        # Sort by length (longest first) to match longer strings first
        all_terms.sort(key=len, reverse=True)
        pattern = r'\b(' + '|'.join(re.escape(term) for term in all_terms) + r')\b'
        self.regexp = re.compile(pattern, re.IGNORECASE)
    
    def __getitem__(self, key):
        """Case-insensitive lookup."""
        return super().__getitem__(key.lower() if isinstance(key, str) else key)
    
    def __contains__(self, key):
        """Case-insensitive membership test."""
        return super().__contains__(key.lower() if isinstance(key, str) else key)


# Directional mappings
DIRECTIONAL = MapDict({
    "North": "N", "South": "S", "East": "E", "West": "W",
    "Northeast": "NE", "Northwest": "NW", "Southeast": "SE", "Southwest": "SW",
    "Norte": "N", "Sur": "S", "Este": "E", "Oeste": "O",
    "Noreste": "NE", "Noroeste": "NO", "Sudeste": "SE", "Sudoeste": "SO"
})

# Street type prefixes (canonical + alternates)
PREFIX_TYPE = MapDict({
    "Avenue": "Ave", "Boulevard": "Blvd", "Expressway": "Expy",
    "Highway": "Hwy", "Lane": "Ln", "Road": "Rd", "Route": "Rte",
    "Av": "Ave", "Aven": "Ave", "Avenu": "Ave", "Avn": "Ave", "Avnue": "Ave",
    "Boul": "Blvd", "Boulv": "Blvd",
    "Exp": "Expy", "Expr": "Expy", "Express": "Expy", "Expw": "Expy",
    "Highwy": "Hwy", "Hiway": "Hwy", "Hiwy": "Hwy", "Hway": "Hwy",
    "Lanes": "Ln",
})

# Street type suffixes (canonical + alternates)
SUFFIX_TYPE = MapDict({
    "Alley": "Aly", "Avenue": "Ave", "Boulevard": "Blvd", "Bridge": "Brg",
    "Bypass": "Byp", "Causeway": "Cswy", "Circle": "Cir", "Court": "Ct",
    "Drive": "Dr", "Expressway": "Expy", "Freeway": "Fwy", "Highway": "Hwy",
    "Lane": "Ln", "Loop": "Loop", "Parkway": "Pkwy", "Pike": "Pike",
    "Place": "Pl", "Plaza": "Plz", "Point": "Pt", "Road": "Rd",
    "Route": "Rte", "Square": "Sq", "Street": "St", "Terrace": "Ter",
    "Trail": "Trl", "Turnpike": "Tpke", "Way": "Way",
    # Alternates
    "Allee": "Aly", "Ally": "Aly",
    "Av": "Ave", "Aven": "Ave", "Avenu": "Ave", "Avn": "Ave", "Avnue": "Ave",
    "Boul": "Blvd", "Boulv": "Blvd", "Brdge": "Brg",
    "Bypa": "Byp", "Bypas": "Byp", "Byps": "Byp",
    "Causway": "Cswy",
    "Circ": "Cir", "Circl": "Cir", "Crcl": "Cir", "Crcle": "Cir",
    "Crt": "Ct",
    "Driv": "Dr", "Drv": "Dr",
    "Exp": "Expy", "Expr": "Expy", "Express": "Expy", "Expw": "Expy",
    "Freewy": "Fwy", "Frway": "Fwy", "Frwy": "Fwy",
    "Highwy": "Hwy", "Hiway": "Hwy", "Hiwy": "Hwy", "Hway": "Hwy",
    "La": "Ln", "Lanes": "Ln",
    "Loops": "Loop",
    "Parkways": "Pkwy", "Parkwy": "Pkwy", "Pkway": "Pkwy", "Pkwys": "Pkwy", "Pky": "Pkwy",
    "Pikes": "Pike",
    "Plza": "Plz",
    "Sqr": "Sq", "Sqre": "Sq", "Squ": "Sq",
    "Str": "St", "Strt": "St",
    "Terr": "Ter",
    "Tr": "Trl", "Trails": "Trl", "Trls": "Trl",
    "Tpk": "Tpke", "Trnpk": "Tpke", "Trpk": "Tpke", "Turnpk": "Tpke",
    "Wy": "Way",
})

# Combined standard abbreviations
STD_ABBR = MapDict({**DIRECTIONAL, **PREFIX_TYPE, **SUFFIX_TYPE})

# Name abbreviations (for city/place names)
NAME_ABBR = MapDict({
    "Ave": "Avenue", "Blvd": "Boulevard", "Br": "Branch", "Brg": "Bridge",
    "Cen": "Center", "Cent": "Center", "Cir": "Circle", "Ck": "Creek",
    "Cnter": "Center", "Cntr": "Center", "Cor": "Corner", "Cp": "Camp",
    "Cr": "Creek", "Crcl": "Circle", "Crcle": "Circle", "Cres": "Crescent",
    "Ct": "Court", "Ctr": "Center", "Cts": "Courts", "Dr": "Drive",
    "Est": "Estate", "Ests": "Estates", "Ext": "Extension",
    "Ft": "Fort", "Gdn": "Garden", "Gdns": "Gardens",
    "Harb": "Harbor", "Hbr": "Harbor", "Hgts": "Heights", "Ht": "Heights",
    "Hwy": "Highway", "Is": "Island", "Jct": "Junction",
    "Ldg": "Lodge", "Lndg": "Landing", "Mt": "Mount", "Mtn": "Mountain",
    "Pk": "Park", "Pkwy": "Parkway", "Pl": "Place",
    "Pt": "Point", "Rdg": "Ridge", "Riv": "River",
    "Spg": "Spring", "Spgs": "Springs", "Sq": "Square",
    "St": "Saint", "Sta": "Station", "Ste": "Sainte", "Stn": "Station",
    "Ter": "Terrace", "Tpke": "Turnpike", "Tr": "Trail",
    "Vill": "Village", "Vlg": "Village", "Vis": "Vista",
})

# US State abbreviations
STATE = MapDict({
    "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR",
    "California": "CA", "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE",
    "District of Columbia": "DC", "Florida": "FL", "Georgia": "GA",
    "Hawaii": "HI", "Idaho": "ID", "Illinois": "IL", "Indiana": "IN",
    "Iowa": "IA", "Kansas": "KS", "Kentucky": "KY", "Louisiana": "LA",
    "Maine": "ME", "Maryland": "MD", "Massachusetts": "MA", "Michigan": "MI",
    "Minnesota": "MN", "Mississippi": "MS", "Missouri": "MO", "Montana": "MT",
    "Nebraska": "NE", "Nevada": "NV", "New Hampshire": "NH", "New Jersey": "NJ",
    "New Mexico": "NM", "New York": "NY", "North Carolina": "NC", "North Dakota": "ND",
    "Ohio": "OH", "Oklahoma": "OK", "Oregon": "OR", "Pennsylvania": "PA",
    "Puerto Rico": "PR", "Rhode Island": "RI", "South Carolina": "SC",
    "South Dakota": "SD", "Tennessee": "TN", "Texas": "TX", "Utah": "UT",
    "Vermont": "VT", "Virginia": "VA", "Washington": "WA", "West Virginia": "WV",
    "Wisconsin": "WI", "Wyoming": "WY"
})

# Cardinal number words
CARDINALS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
    "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20
}

# Ordinal number words
ORDINALS = {
    "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5,
    "sixth": 6, "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10,
    "eleventh": 11, "twelfth": 12, "thirteenth": 13, "fourteenth": 14,
    "fifteenth": 15, "sixteenth": 16, "seventeenth": 17, "eighteenth": 18,
    "nineteenth": 19, "twentieth": 20
}

def ordinal_to_number(word: str) -> int:
    """Convert ordinal word to number."""
    return ORDINALS.get(word.lower(), 0)

def cardinal_to_number(word: str) -> int:
    """Convert cardinal word to number."""
    return CARDINALS.get(word.lower(), 0)

def number_to_ordinal(num: int) -> str:
    """Convert number to ordinal string (1st, 2nd, 3rd, etc.)."""
    if 10 <= num % 100 <= 20:
        suffix = 'th'
    else:
        suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(num % 10, 'th')
    return f"{num}{suffix}"
