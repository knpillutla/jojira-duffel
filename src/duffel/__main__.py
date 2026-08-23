"""
Executable entry point for python -m duffel
"""

from .cli.menu import DuffelCLI

if __name__ == "__main__":
    cli = DuffelCLI()
    cli.run()
