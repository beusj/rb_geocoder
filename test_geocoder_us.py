"""
Tests for the Python Geocoder-US implementation.
"""

import pytest
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


class TestDatabase:
    """Tests for Database class (requires actual database)."""
    
    def test_database_init(self):
        """Test that database can be initialized (skip if no DB)."""
        # This test requires an actual database file
        # In real usage, you would have: db = Database("/path/to/geocoder.db")
        pytest.skip("Requires actual geocoder database")
    
    def test_metaphone_function(self):
        """Test metaphone implementation."""
        # Could test the metaphone function directly if needed
        pytest.skip("Requires database connection")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
