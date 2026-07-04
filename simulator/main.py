"""
main.py

Entry point for the office simulator.
"""

from simulator import OfficeSimulator
from config import PUSH_INTERVAL


def main():
    sim = OfficeSimulator()
    print("\nOffice Simulator Started")
    print(f"Pushing to backend every ~{PUSH_INTERVAL}s")
    sim.run()


if __name__ == "__main__":
    main()
