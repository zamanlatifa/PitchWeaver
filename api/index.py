import os
import sys

# Make the Backend package importable, then expose the Flask app to Vercel.
BACKEND = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Backend")
sys.path.insert(0, os.path.abspath(BACKEND))

from app import app  # noqa: E402,F401
