#!/usr/bin/env python3

from setuptools import setup, find_packages

setup(
    name="gameboy-emulator",
    version="0.1.0",
    description="A Game Boy emulator written in Python",
    author="Your Name",
    python_requires=">=3.7",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    entry_points={
        "console_scripts": [
            "gameboy=gameboy.emulator:main",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
)