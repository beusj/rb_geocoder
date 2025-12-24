"""
Address parsing module for Geocoder-US Python port.
Parses US street addresses into structured components.
"""

import re
from typing import List, Dict, Optional
from .constants import (
    STATE, NAME_ABBR, STD_ABBR, DIRECTIONAL, SUFFIX_TYPE, PREFIX_TYPE,
    CARDINALS, ORDINALS, ordinal_to_number, cardinal_to_number, number_to_ordinal
)


class Address:
    """
    Parses a US street address or place name into structured components.
    
    Attributes:
        text: Original input text
        number: House/building number
        prenum: Prefix to number (e.g., 'A' in 'A123')
        sufnum: Suffix to number (e.g., 'B' in '123B')
        street: List of possible street name variations
        city: List of possible city name variations
        state: Two-letter state abbreviation
        zip: 5-digit ZIP code
        plus4: 4-digit ZIP+4 extension
    """
    
    # Regex patterns for address components
    PATTERNS = {
        'number': re.compile(r'^(\d+\w*|[a-z]+)?(\d+)([a-z]?)\b', re.IGNORECASE),
        'street': re.compile(r'(?:\b(?:\d+\w*|[a-z\'-]+)\s*)+', re.IGNORECASE),
        'city': re.compile(r'(?:\b[a-z\'-]+\s*)+', re.IGNORECASE),
        'state': None,  # Built from STATE constant
        'zip': re.compile(r'(\d{5})(?:-\d{4})?\s*$'),
        'intersection': re.compile(r'\s+(at|@|and|&)\s+', re.IGNORECASE),
        'po_box': re.compile(r'\b[Pp]*(ost|OST)*\.?\s*[Oo0]*(ffice|FFICE)*\.?\s*[Bb][Oo0][Xx]\b'),
    }
    
    def __init__(self, text: str):
        """
        Initialize and parse an address string.
        
        Args:
            text: Address string to parse or dict with address components
        """
        if not text:
            raise ValueError("No text provided")
        
        if isinstance(text, dict):
            self.text = ""
            self._assign_from_dict(text)
        else:
            self.text = self._clean(text)
            self._parse()
    
    def _clean(self, value: str) -> str:
        """Remove characters that aren't part of an address."""
        value = value.strip()
        value = re.sub(r'[^a-z0-9 ,\'&@\/\-]+', '', value, flags=re.IGNORECASE)
        value = re.sub(r'\s+', ' ', value)
        return value
    
    def _assign_from_dict(self, data: Dict):
        """Assign address components from a dictionary."""
        if 'address' in data:
            self.text = self._clean(data['address'])
            self._parse()
        else:
            self.street = []
            self.prenum = data.get('prenum', '')
            self.sufnum = data.get('sufnum', '')
            self.number = data.get('number', '')
            
            if 'street' in data and data['street']:
                street_match = self.PATTERNS['street'].findall(str(data['street']))
                self.street = self._expand_streets(street_match)
            
            self.city = [data.get('city', '')] if data.get('city') else ['']
            
            # Handle state/region
            state_val = data.get('region') or data.get('state') or data.get('country', '')
            if state_val and len(state_val) > 2:
                self.state = STATE.get(state_val, state_val)
            else:
                self.state = state_val
            
            self.zip = data.get('postal_code', '')
            self.plus4 = data.get('plus4', '')
            if not self.zip:
                self.zip = self.plus4 = ''
    
    def _parse(self):
        """Parse the address text into components."""
        text = self.text.lower()
        
        # Extract ZIP code
        zip_match = self.PATTERNS['zip'].search(text)
        if zip_match:
            self.zip = zip_match.group(1)
            self.plus4 = zip_match.group(0).replace(self.zip, '').replace('-', '').strip()
            text = text[:zip_match.start()] + text[zip_match.end():]
            text = re.sub(r'\s*,?\s*$', '', text)
        else:
            self.zip = self.plus4 = ''
        
        # Extract state
        state_pattern = re.compile(r'\b(' + '|'.join(re.escape(s) for s in STATE.keys()) + r')\s*$', re.IGNORECASE)
        state_match = state_pattern.search(text)
        if state_match:
            self.full_state = state_match.group(1).strip()
            self.state = STATE.get(self.full_state, '')
            text = text[:state_match.start()] + text[state_match.end():]
            text = re.sub(r'\s*,?\s*$', '', text)
        else:
            self.full_state = ''
            self.state = ''
        
        # Extract house number
        number_match = self.PATTERNS['number'].search(text)
        if number_match:
            self.prenum, self.number, self.sufnum = number_match.groups()
            self.prenum = (self.prenum or '').strip()
            self.number = (self.number or '').strip()
            self.sufnum = (self.sufnum or '').strip()
            text = text[:number_match.start()] + text[number_match.end():]
            text = re.sub(r'^\s*,?\s*', '', text)
        else:
            self.prenum = self.number = self.sufnum = ''
        
        # Extract street
        street_matches = self.PATTERNS['street'].findall(text)
        self.street = self._expand_streets(street_matches)
        
        # Special case: use state name as street if no street found
        if not self.street and self.state and self.full_state.lower() != self.state.lower():
            self.street = [self.full_state]
        
        # Extract city (last remaining word group)
        city_matches = self.PATTERNS['city'].findall(text)
        if city_matches:
            self.city = [city_matches[-1].strip()]
            # Expand abbreviations in city name
            expanded = [NAME_ABBR.regexp.sub(lambda m: NAME_ABBR[m.group(0)], city) for city in self.city]
            self.city.extend(expanded)
            self.city = list(set(c.lower() for c in self.city if c))
        else:
            self.city = []
        
        # Special case: use state as city if no city found
        if self.state and self.full_state.lower() != self.state.lower():
            if self.full_state not in self.city:
                self.city.append(self.full_state.lower())
    
    def _expand_streets(self, streets: List[str]) -> List[str]:
        """Expand street names with abbreviations and variations."""
        if not streets or not streets[0]:
            return []
        
        streets = [s.strip() for s in streets if s]
        expanded = set(streets)
        
        # Expand name abbreviations
        for street in streets:
            expanded.add(NAME_ABBR.regexp.sub(lambda m: NAME_ABBR[m.group(0)], street))
        
        # Expand standard abbreviations
        for street in list(expanded):
            expanded.add(STD_ABBR.regexp.sub(lambda m: STD_ABBR[m.group(0)], street))
        
        # Expand numbers
        result = []
        for street in expanded:
            result.extend(self._expand_numbers(street))
        
        return list(set(s.lower() for s in result if s))
    
    def _expand_numbers(self, string: str) -> List[str]:
        """Expand ordinal/cardinal numbers in street names."""
        # Check for numeric ordinal (1st, 2nd, etc.)
        match = re.search(r'\b\d+(?:st|nd|rd|th)?\b', string, re.IGNORECASE)
        if match:
            num = int(re.search(r'\d+', match.group(0)).group(0))
            match_str = match.group(0)
        else:
            # Check for ordinal word
            for word, num in ORDINALS.items():
                if word in string.lower():
                    match_str = word
                    break
            else:
                # Check for cardinal word
                for word, num in CARDINALS.items():
                    if word in string.lower():
                        match_str = word
                        num = CARDINALS[word]
                        break
                else:
                    return [string]
        
        # Generate variations
        if num and num < 100:
            variations = [
                string.replace(match_str, str(num), 1),
                string.replace(match_str, number_to_ordinal(num), 1),
            ]
            # Add cardinal word if exists
            for word, val in CARDINALS.items():
                if val == num:
                    variations.append(string.replace(match_str, word, 1))
                    break
            return variations
        else:
            return [string]
    
    @property
    def street_parts(self) -> List[str]:
        """Get all substring variations of street names for fuzzy matching."""
        strings = []
        for street in self.street:
            tokens = street.split()
            # Generate all contiguous substrings
            for i in range(len(tokens)):
                for j in range(i, len(tokens)):
                    strings.append(' '.join(tokens[i:j+1]))
        
        strings = list(set(strings))
        
        # Remove noise words (pure abbreviations)
        prefix_pattern = re.compile(r'^(' + '|'.join(re.escape(k) for k in PREFIX_TYPE.keys()) + r')\s*', re.IGNORECASE)
        suffix_pattern = re.compile(r'\s*(' + '|'.join(re.escape(k) for k in SUFFIX_TYPE.keys()) + r')$', re.IGNORECASE)
        dir_pattern = re.compile(r'(?:^|\s)(' + '|'.join(re.escape(k) for k in DIRECTIONAL.keys()) + r')(?:\s|$)', re.IGNORECASE)
        
        good_strings = []
        for s in strings:
            cleaned = s
            cleaned = prefix_pattern.sub('', cleaned)
            cleaned = suffix_pattern.sub('', cleaned)
            cleaned = dir_pattern.sub('', cleaned)
            if cleaned.strip():
                good_strings.append(s)
        
        # If we filtered everything, add the number
        if self.number and (not good_strings or all(s in STD_ABBR or s in NAME_ABBR for s in good_strings)):
            good_strings.append(self.number)
        
        return list(set(good_strings))
    
    @property
    def city_parts(self) -> List[str]:
        """Get city name parts for fuzzy matching."""
        parts = []
        for city in self.city:
            parts.extend(city.split())
        return list(set(parts))
    
    def po_box(self) -> bool:
        """Check if address is a PO Box."""
        return bool(self.PATTERNS['po_box'].search(self.text))
    
    def intersection(self) -> bool:
        """Check if address is an intersection (e.g., Main St & 1st Ave)."""
        return bool(self.PATTERNS['intersection'].search(self.text))
    
    def __repr__(self) -> str:
        """String representation of the address."""
        parts = []
        if self.number:
            parts.append(f"number={self.number}")
        if self.street:
            parts.append(f"street={self.street[0] if len(self.street) == 1 else self.street}")
        if self.city:
            parts.append(f"city={self.city[0]}")
        if self.state:
            parts.append(f"state={self.state}")
        if self.zip:
            parts.append(f"zip={self.zip}")
        return f"Address({', '.join(parts)})"


# Build state pattern after STATE is defined
Address.PATTERNS['state'] = re.compile(
    r'\b(' + '|'.join(re.escape(s) for s in STATE.keys()) + r')\s*$',
    re.IGNORECASE
)
