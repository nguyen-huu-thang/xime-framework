from __future__ import annotations

import os
import sys

_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_tests_dir = os.path.dirname(os.path.abspath(__file__))

sys.path.insert(0, _project_root)
sys.path.insert(0, _tests_dir)
