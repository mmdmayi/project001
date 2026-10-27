"""Load the local Maya UI without importing external scientific libraries."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from faceinverse.ui import show
show()
