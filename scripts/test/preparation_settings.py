"""Automatic translation selection never writes settings or claims whole settings coverage."""
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import preparation_settings as settings

AUTO={'GT5P_PREPARE_TRANSLATION':'auto'}


class SettingsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.storage=Path(self.temp.name)
        self.path=self.storage/'gt5p_settings.toml'

    def choose(self,text,env=AUTO):
        self.path.write_text(text,encoding='utf-8')
        before=self.path.read_bytes()
        result=settings.select(self.storage,env)
        self.assertEqual(self.path.read_bytes(),before)
        return result

    def test_explicit_modes_and_rollback_do_not_read_settings(self):
        with patch.object(settings,'regular_read',side_effect=AssertionError('Unexpected settings read')):
            for mode in ('default','native-scaled','ultrawide-native'):
                selected=settings.select(self.storage,{'GT5P_PREPARE_TRANSLATION':mode})
                self.assertEqual(selected['mode'],mode)
                settings.verify(selected,self.storage,{})
            for mode in ('', '1', '../outside', 'invalid'):
                with self.assertRaises(ValueError):settings.select(self.storage,{'GT5P_PREPARE_TRANSLATION':mode})

    def test_unset_selects_saved_settings_and_checks_publication(self):
        selected=self.choose('[video]\nresolution="1440p"',{})
        self.assertEqual(selected['requested'],'auto')
        self.assertEqual(selected['mode'],'native-scaled')
        settings.verify(selected,self.storage,{})
        self.path.write_text('[video]\naspect="21:9"')
        with self.assertRaisesRegex(ValueError,'Settings changed'):
            settings.verify(selected,self.storage,{})

    def test_saved_supported_resolution_and_aspect_modes(self):
        for value in ('"720p"','"1080p"','"1440p"','"2160p"','"4k"','"4K"','720','1080','1440','2160'):
            for aspect in ('16:9','21:9'):
                result=self.choose('[video]\nresolution='+value+'\naspect="'+aspect+'"\n')
                expected='ultrawide-native' if aspect=='21:9' else 'default' if value in ('"720p"','"1080p"','720','1080') else 'native-scaled'
                self.assertEqual(result['mode'],expected,(value,aspect))
                self.assertEqual(result['aspect'],aspect)
                self.assertIsNotNone(result['settings_sha256'])
                settings.verify(result,self.storage,AUTO)

    def test_missing_settings_preserves_first_run_preset(self):
        result=settings.select(self.storage,AUTO)
        self.assertEqual(result['mode'],'default')
        self.assertEqual(result['source'],'launcher-first-run-preset')
        self.assertFalse(self.path.exists())

    def test_invalid_types_and_unsupported_settings_are_explicit_fallback(self):
        for text in ('[video]\nresolution=true\naspect="21:9"',
                     '[video]\nresolution=1440.0', '[video]\naspect="32:9"',
                     'video=4', '[video]\nresolution="4K"\n[game]\nanisotropy=4',
                     '[video]\nresolution="4K"\n[game]\nsmooth_colour=false',
                     '[video]\nresolution="1440p"\n[game]\nanisotropy=true'):
            result=self.choose(text)
            self.assertEqual(result['mode'],'default')
            self.assertIn('reason',result)
            self.assertNotIn('resolution',result)

    def test_overrides_are_conservative_and_case_insensitive(self):
        for key in settings.OVERRIDES:
            result=self.choose('[video]\naspect="21:9"',dict(AUTO,**{key.lower():'1'}))
            self.assertEqual(result['mode'],'default')
            self.assertIn(key,result['reason'])

    def test_malformed_bounded_and_utf8_settings(self):
        for payload in (b'\xff',b'[video\naspect="21:9"',b'x'*(settings.MAX_SETTINGS+1)):
            self.path.write_bytes(payload)
            self.assertEqual(settings.select(self.storage,AUTO)['mode'],'default')
            self.assertEqual(self.path.read_bytes(),payload)
        self.path.write_bytes(b'\xef\xbb\xbf[video]\naspect="21:9"')
        self.assertEqual(settings.select(self.storage,AUTO)['mode'],'ultrawide-native')

    def test_hardlinked_settings_not_followed(self):
        self.path.write_text('[video]\naspect="21:9"')
        os.link(self.path,self.storage/'alias')
        selected=settings.select(self.storage,AUTO)
        self.assertEqual(selected['mode'],'default')
        self.assertIsNone(selected['settings_sha256'])

    def test_unvalidated_non_ascii_storage_is_conservative(self):
        storage=self.storage/'测试'
        storage.mkdir()
        (storage/'gt5p_settings.toml').write_text('[video]\naspect="21:9"')
        selection=settings.select(storage,AUTO)
        self.assertEqual(selection['mode'],'default')
        self.assertIn('non-ASCII',selection['reason'])

    def test_changed_settings_reject_publication_without_writes(self):
        first=settings.select(self.storage,AUTO)
        self.choose('[video]\naspect="21:9"')
        with self.assertRaisesRegex(ValueError,'Settings changed'):
            settings.verify(first,self.storage,AUTO)
        first=settings.select(self.storage,AUTO)
        self.path.write_text('[video]\naspect="16:9"')
        with self.assertRaisesRegex(ValueError,'Settings changed'):
            settings.verify(first,self.storage,AUTO)


if __name__=='__main__':unittest.main()
