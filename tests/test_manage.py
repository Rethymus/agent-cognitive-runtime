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

    def _changed_activation(self):
        original=manage.activation
        def changed(home):
            return original(home).replace(manage.ACTIVATION_END.encode('utf8'), ('本次已审阅。\n'+manage.ACTIVATION_END).encode('utf8'))
        return changed

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

    def test_changed_activation_block_requires_adoption_in_dry_run_and_apply(self):
        manage.install(self.home,True,activate=True)
        agents=(self.home/'AGENTS.md').read_bytes()
        (self.home/'AGENTS.md').write_bytes(agents.replace('保留当前主模型。'.encode('utf8'), '保留另一个主模型。'.encode('utf8')))
        with patch.object(manage,'activation',side_effect=self._changed_activation()):
            with self.assertRaises(ValueError):manage.install(self.home,activate=True)
            with self.assertRaises(ValueError):manage.install(self.home,True,activate=True)

    def test_changed_activation_block_adoption_roundtrip(self):
        manage.install(self.home,True,activate=True)
        agents=self.home/'AGENTS.md'
        before=agents.read_bytes().replace(manage.ACTIVATION_END.encode('utf8'), ('用户自定义块内容\n'+manage.ACTIVATION_END).encode('utf8'))
        agents.write_bytes(before)
        with patch.object(manage,'activation',side_effect=self._changed_activation()):
            result=manage.install(self.home,True,activate=True,adopt_existing=True)
        self.assertIn('AGENTS.md',result['changed_files'])
        self.assertNotEqual((self.home/'AGENTS.md').read_bytes(),before)
        manage.rollback(self.home,True)
        self.assertEqual((self.home/'AGENTS.md').read_bytes(),before)

    def test_outside_edit_is_allowed_when_updating_managed_block(self):
        manage.install(self.home,True,activate=True)
        agents=(self.home/'AGENTS.md').read_text(encoding='utf8')
        match=manage.extract_activation(agents.encode('utf8'))[1]
        edited=agents[:match.start()]+'用户后来补充的规则\n'+agents[match.start():]+'\n用户末尾补充的规则\n'
        (self.home/'AGENTS.md').write_bytes(edited.encode('utf8'))
        with patch.object(manage,'activation',side_effect=self._changed_activation()):
            manage.install(self.home,True,activate=True)
        final=(self.home/'AGENTS.md').read_text(encoding='utf8')
        self.assertIn('用户后来补充的规则',final)
        self.assertIn('用户末尾补充的规则',final)
        self.assertIn('本次已审阅',final)

    def test_deleted_managed_block_requires_adoption(self):
        manage.install(self.home,True,activate=True)
        agents=(self.home/'AGENTS.md').read_text(encoding='utf8')
        match=manage.extract_activation(agents.encode('utf8'))[1]
        (self.home/'AGENTS.md').write_text(agents[:match.start()]+agents[match.end():],encoding='utf8')
        with self.assertRaises(ValueError):manage.install(self.home,activate=True)
        manage.install(self.home,True,activate=True,adopt_existing=True)
        self.assertEqual((self.home/'AGENTS.md').read_text(encoding='utf8').count('<!-- ACR:BEGIN -->'),1)

    def test_legacy_receipt_allows_exact_full_file_change(self):
        manage.install(self.home,True,activate=True)
        latest=self.home/'cognitive-runtime/packages/latest.json'
        receipt=json.loads(latest.read_text(encoding='utf8'))
        receipt.pop('activation_block_sha256')
        latest.write_text(json.dumps(receipt,ensure_ascii=False),encoding='utf8')
        with patch.object(manage,'activation',side_effect=self._changed_activation()):
            manage.install(self.home,True,activate=True)

    def test_legacy_receipt_rejects_outside_edit_when_block_changes(self):
        manage.install(self.home,True,activate=True)
        latest=self.home/'cognitive-runtime/packages/latest.json'
        receipt=json.loads(latest.read_text(encoding='utf8'))
        receipt.pop('activation_block_sha256')
        latest.write_text(json.dumps(receipt,ensure_ascii=False),encoding='utf8')
        (self.home/'AGENTS.md').write_text('用户修改\n'+(self.home/'AGENTS.md').read_text(encoding='utf8'),encoding='utf8')
        with patch.object(manage,'activation',side_effect=self._changed_activation()):
            with self.assertRaises(ValueError):manage.install(self.home,activate=True)

    def test_initial_custom_activation_block_requires_adoption(self):
        custom='''用户前置指令\n<!-- ACR:BEGIN -->\n用户自己写的块\n<!-- ACR:END -->\n用户后置指令\n'''
        (self.home/'AGENTS.md').write_text(custom,encoding='utf8')
        with self.assertRaises(ValueError):manage.install(self.home,activate=True)
        manage.install(self.home,True,activate=True,adopt_existing=True)
        final=(self.home/'AGENTS.md').read_text(encoding='utf8')
        self.assertIn('用户前置指令',final);self.assertIn('用户后置指令',final)

    def test_skill_only_receipt_preserves_activation_block_baseline(self):
        manage.install(self.home,True,activate=True)
        first=json.loads((self.home/'cognitive-runtime/packages/latest.json').read_text(encoding='utf8'))
        skill=self.home/'skills/agent-cognitive-runtime/SKILL.md';skill.unlink()
        manage.install(self.home,True,activate=False)
        second=json.loads((self.home/'cognitive-runtime/packages/latest.json').read_text(encoding='utf8'))
        self.assertEqual(second['activation_block_sha256'],first['activation_block_sha256'])
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
