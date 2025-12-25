"""
Setup script for Geocoder-US Python package.
"""

from setuptools import setup, find_packages

with open("README_PYTHON.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="geocoder-us-python",
    version="3.0.0",
    author="Python port of Geocoder::US by Schuyler Erle",
    author_email="",
    description="US address geocoding using TIGER/Line data with DuckDB",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/beusj/rb_geocoder",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Scientific/Engineering :: GIS",
        "License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.8",
    install_requires=[
        "duckdb>=0.9.0",
        "jellyfish>=1.0.0",
        "rapidfuzz>=3.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-cov>=4.1.0",
        ],
    },
)
