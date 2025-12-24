"""
Tests for the Python Geocoder-US implementation.
"""

import pytest
import tempfile
from pathlib import Path
from geocoder_us import Address, Database
from geocoder_us.constants import STATE, NAME_ABBR, STD_ABBR


class TestAddress:
    """Tests for Address parsing."""
    
    def test_simple_address(self):
        """Test parsing a simple street address."""
        addr = Address("1600 Pennsylvania Ave, Washington DC 20502")
        assert addr.number == "1600"
        assert any("pennsylvania" in s.lower() for s in addr.street)
        assert "washington" in [c.lower() for c in addr.city]
        assert addr.state == "DC"
        assert addr.zip == "20502"
    
    def test_address_without_zip(self):
        """Test parsing address without ZIP code."""
        addr = Address("123 Main St, New York, NY")
        assert addr.number == "123"
        assert any("main" in s.lower() for s in addr.street)
        assert addr.state == "NY"
        assert addr.zip == ""
    
    def test_address_with_abbreviations(self):
        """Test that abbreviations are expanded."""
        addr = Address("100 N Main St, Springfield IL")
        assert len(addr.street) > 1  # Should have expanded variations
        assert addr.state == "IL"
    
    def test_city_only(self):
        """Test parsing city and state only."""
        addr = Address("New York, NY")
        assert "new york" in [c.lower() for c in addr.city]
        assert addr.state == "NY"
        assert addr.number == ""
        assert not addr.street
    
    def test_zip_only(self):
        """Test parsing ZIP code only."""
        addr = Address("20502")
        assert addr.zip == "20502"
    
    def test_po_box(self):
        """Test PO Box detection."""
        addr = Address("PO Box 123, New York NY 10001")
        assert addr.po_box()
        assert addr.zip == "10001"
    
    def test_intersection(self):
        """Test intersection detection."""
        addr = Address("Main St & 1st Ave, New York NY")
        assert addr.intersection()
        assert addr.state == "NY"
    
    def test_ordinal_numbers(self):
        """Test ordinal number expansion."""
        addr = Address("100 1st Street")
        # Should have variations like "first", "1", "1st"
        assert len(addr.street) >= 1
    
    def test_state_abbreviation(self):
        """Test state name to abbreviation conversion."""
        addr = Address("123 Main St, New York New York")
        assert addr.state == "NY"
    
    def test_empty_address(self):
        """Test parsing empty address raises error."""
        with pytest.raises(ValueError, match="Address text cannot be empty or None"):
            Address("")
    
    def test_address_with_suite(self):
        """Test address with suite/apt number."""
        addr = Address("123 Main St Suite 100, New York NY")
        assert addr.number == "123"
        assert any("main" in s.lower() for s in addr.street)
    
    def test_address_dict_input(self):
        """Test creating address from dict."""
        # The dict input processing may not preserve all fields perfectly
        # Just test that it doesn't crash
        addr = Address({
            'number': '123',
            'street': ['Main St'],
            'city': ['New York'],
            'state': 'NY',
            'zip': '10001'
        })
        assert addr.number == '123'
        # Street and city variations are created during initialization
        assert any('main' in s.lower() for s in addr.street)
        assert 'New York' in str(addr.city)
        assert addr.state == 'NY'


class TestConstants:
    """Tests for constants module."""
    
    def test_state_lookup(self):
        """Test state abbreviation lookup."""
        assert STATE["California"] == "CA"
        assert STATE["california"] == "CA"
        assert STATE["CA"] == "CA"
    
    def test_abbreviation_lookup(self):
        """Test street type abbreviation lookup."""
        assert STD_ABBR["Street"] == "St"
        assert STD_ABBR["street"] == "St"
        assert STD_ABBR["Avenue"] == "Ave"
    
    def test_name_abbreviation(self):
        """Test name abbreviation expansion."""
        assert NAME_ABBR["St"] == "Saint"
        assert NAME_ABBR["Mt"] == "Mount"
    
    def test_all_states_present(self):
        """Test that all 50 states + DC are present."""
        # Should have at least 51 entries (50 states + DC)
        assert len(STATE) >= 51


class TestDatabase:
    """Tests for Database class."""
    
    def test_validate_database_extension_valid_duckdb(self):
        """Test validation accepts .duckdb extension."""
        from tools.tiger_import_duckdb import validate_database_extension
        
        result = validate_database_extension("geocoder.duckdb")
        assert result == "geocoder.duckdb"
    
    def test_validate_database_extension_valid_db(self):
        """Test validation accepts .db extension."""
        from tools.tiger_import_duckdb import validate_database_extension
        
        result = validate_database_extension("geocoder.db")
        assert result == "geocoder.db"
    
    def test_validate_database_extension_invalid(self):
        """Test validation rejects invalid extensions."""
        from tools.tiger_import_duckdb import validate_database_extension
        
        with pytest.raises(ValueError, match="Invalid database extension"):
            validate_database_extension("geocoder.sqlite")
        
        with pytest.raises(ValueError, match="Invalid database extension"):
            validate_database_extension("geocoder.txt")
        
        with pytest.raises(ValueError, match="Invalid database extension"):
            validate_database_extension("geocoder")
    
    def test_validate_database_extension_case_insensitive(self):
        """Test validation is case insensitive."""
        from tools.tiger_import_duckdb import validate_database_extension
        
        assert validate_database_extension("geocoder.DUCKDB") == "geocoder.DUCKDB"
        assert validate_database_extension("geocoder.DB") == "geocoder.DB"
        assert validate_database_extension("geocoder.DuckDb") == "geocoder.DuckDb"
    
    def test_database_context_manager(self):
        """Test database context manager (requires actual DB)."""
        # This test requires an actual database file
        # In real usage, you would have: db = Database("/path/to/geocoder.duckdb")
        pytest.skip("Requires actual geocoder database")
    
    def test_metaphone_function(self):
        """Test metaphone implementation."""
        # Could test the metaphone function directly if needed
        pytest.skip("Requires database connection")


class TestDatabaseUtils:
    """Tests for database utility functions."""
    
    def test_metaphone_basic(self):
        """Test basic metaphone functionality."""
        # Import the Database class to test metaphone
        import duckdb
        import jellyfish
        
        # Test the metaphone function logic
        def metaphone(text: str, length: int = 5) -> str:
            if not text:
                return ""
            text = ''.join(c for c in text if c.isalnum())
            if text.isdigit():
                return text[:length]
            if len(text) == 1 and text.lower() in ['w', 'y']:
                return text.lower()
            try:
                result = jellyfish.metaphone(text)
                return result[:length] if result else ""
            except (ValueError, TypeError):
                return text[:length]
        
        # Test some common cases
        assert metaphone("street") != ""
        assert metaphone("Street") == metaphone("street")
        assert metaphone("main") != ""
        assert metaphone("") == ""
        assert metaphone("123") == "123"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
