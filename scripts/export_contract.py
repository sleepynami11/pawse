"""Generate the tracked OpenAPI contract from the running application's models."""
import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
from pawse.app import app

(root / 'docs/openapi.json').write_text(json.dumps(app.openapi(), indent=2) + '\n')
print('Exported docs/openapi.json')
