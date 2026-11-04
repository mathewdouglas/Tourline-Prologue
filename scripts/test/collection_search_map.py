"""Package metadata must pin the wider search to the exact supported game."""
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
from unittest.mock import patch

root=Path(__file__).parents[2]
spec=importlib.util.spec_from_file_location('collection_package',root/'scripts/release/package_player.py')
package=importlib.util.module_from_spec(spec);spec.loader.exec_module(package)
with tempfile.TemporaryDirectory() as folder:
    fixture=Path(folder);bundle=fixture/'assets/pipeline-templates/gt5p-disc-v2'
    shutil.copytree(root/'assets/pipeline-templates/gt5p-disc-v2',bundle)
    shutil.copytree(root/'assets/shader-enumeration/gt5p-disc-v1',fixture/'assets/shader-enumeration/gt5p-disc-v1')
    search=bundle/'search-map.json';original=json.loads(search.read_text())
    baseline=json.loads((bundle/'volume-map.json').read_text())
    with patch.object(package,'ROOT',fixture):
        assert any(name.endswith('/search-map.json') for name in package.template_files())
        for field in ('elf_sha256','volume_sha256'):
            changed=dict(original);changed[field]='f'*64;search.write_text(json.dumps(changed))
            try:package.template_files()
            except ValueError:pass
            else:raise AssertionError('Different game search map packaged')
        changed=dict(original,records=[r for r in original['records'] if r['container']!=baseline['records'][0]['container']])
        search.write_text(json.dumps(changed))
        try:package.template_files()
        except ValueError:pass
        else:raise AssertionError('Missing player container accepted')
        search.write_text(json.dumps(original))
        assert len(package.template_files())>0
print('Wider search map packages only with matching ELF/archive and every unchanged starter container')
