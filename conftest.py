"""让 pytest 能导入 simplememkitty 包（无需 pip install -e）。"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
