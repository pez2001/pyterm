"""CI check: settings from the 1.0.0 'pyvterm' config folder are copied to 'pyterm' on first start."""
import os
import sys
import tempfile

tmp = tempfile.mkdtemp()
os.environ['XDG_CONFIG_HOME'] = tmp   # Linux / macOS
os.environ['APPDATA'] = tmp           # Windows
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

old = os.path.join(tmp, 'pyvterm')
os.makedirs(os.path.join(old, 'themes'))
with open(os.path.join(old, 'config.yaml'), 'w') as f:
    f.write('theme: c64\n')
with open(os.path.join(old, 'themes', 'mine.yaml'), 'w') as f:
    f.write('name: mine\n')

from pyterm import config  # noqa: E402

assert config.load_config_file().get('theme') == 'c64', 'old config not migrated'
new = config.user_dir()
assert os.path.basename(new) == 'pyterm'
assert os.path.exists(os.path.join(new, 'themes', 'mine.yaml')), 'old themes not migrated'
assert os.path.exists(os.path.join(old, 'config.yaml')), 'old folder must stay in place'
print('migration ok')
