import os
import sys

# Add tests_temp/testing/ to sys.path so the 'sample' package is importable
_test_dir = os.path.dirname(os.path.abspath(__file__))
if _test_dir not in sys.path:
    sys.path.insert(0, _test_dir)
