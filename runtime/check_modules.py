import sys
import os
import json

# Add parent directory to sys.path to find api module
sys.path.append("/app")
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.context import build_container
from api.services.modules import get_modules

c = build_container()
print(json.dumps(get_modules(c), indent=2))
