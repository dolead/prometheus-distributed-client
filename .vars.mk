# Project-specific configuration for Makefile
# This is the only file that changes per project.

# Source code path: a directory (mypackage/) or a single file (mymodule.py)
CODE = prometheus-distributed-client

# Test command — override if you need custom flags or paths
TEST_CMD = poetry run pytest tests/

# Linter flags — set to empty to disable a given linter
PYCODESTYLE_IGNORE = E126,E127,E128,W503
PYLINT_DISABLE     = I0011,R0901,R0902,R0801,C0111,C0103,C0411,C0415,R0903,R0913,R0914,R0915,R1710,W0613,W0703
