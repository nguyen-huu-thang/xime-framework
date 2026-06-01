import os
import sys

# Project root (chứa core/) và DI/ (chứa sample/) đều cần trong sys.path
# __file__ nằm ở tests_temp/DI/ nên cần đi lên 3 cấp để ra project root
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_tests_dir = os.path.dirname(os.path.abspath(__file__))

sys.path.insert(0, _project_root)
sys.path.insert(0, _tests_dir)

print(f"Added to sys.path: {_project_root}, {_tests_dir}")