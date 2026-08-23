"""
Executable entry point for python -m duffel.cli
"""

from .menu import DuffelCLI

if __name__ == "__main__":
    cli = DuffelCLI()
    cli.run()
