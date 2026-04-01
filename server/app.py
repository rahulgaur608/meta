"""
Multi-mode deployment wrapper for OpenEnv validation.
Imports the main FastAPI app and exposes a main() entry point.
"""
import sys
import os

# Ensure project root is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app  # noqa: F401


def main():
    """Entry point for multi-mode deployment."""
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=7860)


if __name__ == "__main__":
    main()
