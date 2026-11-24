import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# task 0294: a user who has not chosen a workspace starts in Essentials; the tests (written for every function) start
# where they always did. tests/test_workspaces_essentials.py takes this away for its own checks.
os.environ.setdefault("FRESING_WORKSPACE_START", "All functions")
