import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from faceinverse import config

class ConfigTests(unittest.TestCase):
    def test_2022_release_uses_2022_binary_and_plugin_glob(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'release.json').write_text(json.dumps({'target_maya':'2022'}))
            with patch.object(config,'ROOT',root):
                cfg=config.defaults()
            self.assertEqual(cfg['maya_version'],'2022')
            self.assertIn('Maya2022',cfg['maya_python'])
            self.assertNotIn('maya-2024',cfg['plugin'])
            self.assertFalse(cfg['allow_newer_scene'])
    def test_invalid_release_target_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'release.json').write_text(json.dumps({'target_maya':'1900'}))
            with patch.object(config,'ROOT',root):
                with self.assertRaises(ValueError):config.defaults()
    def test_no_release_retains_2024_default(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(config,'ROOT',Path(folder)):
                self.assertEqual(config.defaults()['maya_version'],'2024')
