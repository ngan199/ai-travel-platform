"""
Run all normalization scripts in order.
Outputs to data/normalized/ and data/normalized/splink_input/
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from normalize_destinations import run as run_destinations
from normalize_attributes import run as run_attributes
from normalize_festivals import run as run_festivals
from normalize_venues import run as run_venues
from normalize_transport import run as run_transport
from normalize_accommodation import run as run_accommodation

if __name__ == "__main__":
    print("=== Normalization pipeline ===\n")

    print("--- Canonical tables ---")
    run_destinations()
    run_attributes()
    run_festivals()

    print("\n--- Splink input tables ---")
    run_venues()
    run_transport()
    run_accommodation()

    print("\n=== Done ===")
