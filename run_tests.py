"""
CLI test runner for FishSwarm.
Executes pytest in headless mode and returns proper exit code.
"""
import os
import sys

if __name__ == "__main__":
    os.environ["SDL_VIDEODRIVER"] = "dummy"
    os.environ["SDL_AUDIODRIVER"] = "dummy"
    
    import pytest
    exit_code = pytest.main(["-v", "tests"])
    sys.exit(exit_code)
