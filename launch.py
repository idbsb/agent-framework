"""PyInstaller entry point for the portable Windows application."""
import sys
from agent_framework.ui_server import main, self_test

if __name__ == "__main__":
    raise SystemExit(self_test() if "--self-test" in sys.argv else main())
