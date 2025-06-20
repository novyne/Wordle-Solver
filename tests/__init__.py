import sys
import os

# Add the project root directory to sys.path to allow absolute imports when running scripts directly
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Package initialization for wordle_solver