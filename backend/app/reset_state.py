import sys
import os

# Adjust path to enable absolute imports from parent directory
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from backend.app.memory import reset_state

if __name__ == "__main__":
    print("Initiating global state wipe for NeuroWeave OS...")
    reset_state()
    print("Success: All persistent knowledge graphs, memory databases, and execution run logs have been deleted.")
