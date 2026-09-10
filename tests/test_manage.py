from pathlib import Path
from datetime import date
import json
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import manage

class FixedDate(date):
    @classmethod
    def today(cls):return cls(2026,9,9)

class ManageTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.home=Path(self.temp.name)/'codex'
        self.home.mkdir();self.config=b'model="keep-user-model"\n'
        (self.home/'config.toml').write_bytes(self.config)
        self.original='用户自己的指令\n'.encode('utf8');(self.home/'AGENTS.md').write_bytes(self.original)
        state=self.home/'cognitive-runtime/state';state.mkdir(parents=True)
        (state/'sentinel').write_bytes(b'memory and ledger survive')
        self.clock=patch.object(manage.router,'date',FixedDate);self.clock.start();self.addCleanup(self.clock.stop)
    def tearDown(self):self.temp.cleanup()
    def test_dry_run_and_default_scope(self):
        plan=manage.install(self.home)
        self.assertTrue(plan['dry_run']);self.assertFalse((self.home/'skills').exists())
        manage.install(self.home,True)
        self.assertEqual((self.home/'AGENTS.md').read_bytes(),self.original)
        self.assertFalse((self.home/'agents').exists())
        self.assertEqual((self.home/'config.toml').read_bytes(),self.config)
    def test_full_install_doctor_and_roundtrip(self):
        manage.install(self.home,True,with_roles=True,activate=True)
        self.assertEqual(len(list((self.home/'agents').glob('*.toml'))),8)
        self.assertTrue(all(manage.doctor(self.home)['checks'].values()))
        self.assertTrue((self.home/'AGENTS.md').read_bytes().startswith(self.original))
        manage.rollback(self.home,True)
        self.assertFalse((self.home/'skills/agent-cognitive-runtime/SKILL.md').exists())
        self.assertEqual((self.home/'AGENTS.md').read_bytes(),self.original)
        self.assertEqual((self.home/'config.toml').read_bytes(),self.config)
        self.assertEqual((self.home/'cognitive-runtime/state/sentinel').read_bytes(),b'memory and ledger survive')
    def test_reinstall_is_idempotent(self):
        manage.install(self.home,True,activate=True)
        r=manage.install(self.home,True,activate=True);self.assertEqual(r['changed_files'],[])
        self.assertEqual((self.home/'AGENTS.md').read_text(encoding='utf8').count('<!-- ACR:BEGIN -->'),1)
    def test_foreign_files_require_explicit_adoption(self):
        p=self.home/'skills/agent-cognitive-runtime/SKILL.md';p.parent.mkdir(parents=True);p.write_bytes(b'custom')
        with self.assertRaises(ValueError):manage.install(self.home,True)
        manage.install(self.home,True,adopt_existing=True);manage.rollback(self.home,True)
        self.assertEqual(p.read_bytes(),b'custom')
    def test_later_edits_preserved(self):
        manage.install(self.home,True,activate=True);p=self.home/'AGENTS.md';p.write_bytes(b'later edit')
        r=manage.rollback(self.home,True)
        self.assertIn('AGENTS.md',r['preserved_modified_or_missing']);self.assertEqual(p.read_bytes(),b'later edit')
    def test_cooperative_lock_is_not_stolen(self):
        lock=self.home/'cognitive-runtime/packages/.lock';lock.mkdir(parents=True)
        with self.assertRaises(FileExistsError):manage.install(self.home,True)
        self.assertTrue(lock.exists());self.assertFalse((self.home/'skills').exists())
    def test_corrupted_backup_refuses_restore(self):
        r=manage.install(self.home,True,activate=True)
        folder=self.home/'cognitive-runtime/packages'/r['receipt_id']
        for p in folder.glob('*.before'):p.write_bytes(b'corruption')
        with self.assertRaises(ValueError):manage.rollback(self.home,True)
        self.assertTrue((self.home/'skills/agent-cognitive-runtime/SKILL.md').exists())
    def test_ambiguous_activation_refused(self):
        (self.home/'AGENTS.md').write_bytes(b'<!-- ACR:BEGIN --> broken')
        with self.assertRaises(ValueError):manage.install(self.home,True,activate=True)
    def test_path_escape_refused(self):
        for rel in ('../outside','cognitive-runtime/state/sentinel'):
            with self.assertRaises(ValueError):manage.target(self.home,rel)

if __name__=='__main__':unittest.main(verbosity=2)
