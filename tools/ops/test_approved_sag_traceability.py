"""Fail closed on modified packages or missing/superseded human approval."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import approved_sag_traceability as promotion


class PromotionCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.proof = {'commit':'candidate','files':{},'versions':{}}
        for commit, modules in promotion.APPROVED_RELEASES.items():
            release = {'commit':commit,'files':{},'versions':{}}
            folder = self.root/commit
            folder.mkdir()
            for name in modules:
                file = folder/name/'__manifest__.py'
                file.parent.mkdir()
                file.write_bytes(b'approved bytes')
                release['files'][name+'/__manifest__.py'] = hashlib.sha256(file.read_bytes()).hexdigest()
                release['versions'][name]='18.0.1.0.0'
            (folder/'release.json').write_text(json.dumps(release))
            self.proof['files'].update(release['files'])
            self.proof['versions'].update(release['versions'])

    def test_exact_content_and_original_integrity(self):
        with patch.object(promotion,'DEVELOPMENT_RELEASES',self.root):
            promotion.verify_content(self.proof)
            changed=copy.deepcopy(self.proof)
            changed['files']['step_packing_sag/extra.py']='unapproved'
            with self.assertRaises(AssertionError):promotion.verify_content(changed)
            first=next(self.root.glob('*/step_packing_sag/__manifest__.py'))
            first.write_bytes(b'modified original')
            with self.assertRaises(AssertionError):promotion.verify_content(self.proof)

    def test_approval_and_development_proof(self):
        dev=self.root/'qa_passed.json'
        dev.write_text(json.dumps({'database':'MANAGEMENT_QA_DEVELOPMENT_test',
            'commit':'candidate','release_sha256':'sha'}))
        for tid, mid in ((93,9521),(94,9518)):
            (self.root/f'{tid}.json').write_text(json.dumps({'ticket':{'id':tid},'messages':[
                {'id':mid,'message_type':'comment','body':'Aprobado. Actualizar Cerro El Plomo'}]}))
        with patch.object(promotion,'verify_content') as verify:
            promotion.verify_authorization(self.root,dev,self.proof,'sha')
            verify.assert_called_once_with(self.proof)
            with self.assertRaises(AssertionError):promotion.verify_authorization(self.root,dev,self.proof,'changed')
            file=self.root/'94.json'
            data=json.loads(file.read_text());data['messages'].append({'id':9522,'message_type':'comment','body':'Esperar'})
            file.write_text(json.dumps(data))
            with self.assertRaises(AssertionError):promotion.verify_authorization(self.root,dev,self.proof,'sha')
        with self.assertRaises(AssertionError):promotion.verify_authorization(None,dev,self.proof,'sha')


if __name__=='__main__':unittest.main()
