"""Setup script for Congressional Trading Bot"""

from setuptools import setup, find_packages
from pathlib import Path

# Read README
readme_file = Path(__file__).parent / "README.md"
long_description = readme_file.read_text() if readme_file.exists() else ""

# Read requirements
requirements_file = Path(__file__).parent / "requirements.txt"
requirements = []
if requirements_file.exists():
    requirements = requirements_file.read_text().splitlines()
    requirements = [r.strip() for r in requirements if r.strip() and not r.startswith('#')]

setup(
    name="congressional-trading-bot",
    version="0.1.0",
    author="Congressional Trading Bot Contributors",
    description="Track and replicate congressional stock trades with automated risk management",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/congressional-trading-bot",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Financial and Insurance Industry",
        "Topic :: Office/Business :: Financial :: Investment",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.11",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "congress-trade=src.cli.cli:cli",
        ],
    },
    include_package_data=True,
    package_data={
        "": ["*.yaml", "*.csv"],
    },
)
