import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from contextlib import redirect_stdout
import io

ROOT=Path(__file__).resolve().parents[1]

class EntryTests(unittest.TestCase):
    def test_prepare_reports_hash_of_saved_manifest(self):
        import inference_ab
        with tempfile.TemporaryDirectory() as tmp:
            output=Path(tmp)/'prepared.json'
            payload={'config_SHA256':'config-digest','binding_SHA256':'binding-digest','rows':[1],'schedule':[2]}
            def prepare(binding, inputs, destination):
                Path(destination).write_text(json.dumps(payload),encoding='utf-8')
                return payload
            stream=io.StringIO()
            with patch('ki_ocr.pipeline.prepare',side_effect=prepare), patch.dict('os.environ'), redirect_stdout(stream):
                inference_ab.main(['prepare','--binding','unused','--input','unused','--output',str(output)])
            result=json.loads(stream.getvalue())
            self.assertEqual(result['prepared_manifest_SHA256'],hashlib.sha256(output.read_bytes()).hexdigest())
            self.assertNotEqual(result['prepared_manifest_SHA256'],result['config_SHA256'])
            self.assertNotIn('rows',result)
            self.assertNotIn('prepared_manifest_SHA256',json.loads(output.read_bytes()))
    def test_real_schemas(self):
        for argv in [[],['prepare'],['run-standalone']]:
            p=subprocess.run([sys.executable,str(ROOT/'inference_ab.py'),*argv,'--help'],capture_output=True,text=True)
            self.assertEqual(p.returncode,0,p.stderr)
    def test_managed_policy_rejects_standalone_before_model_or_GPU(self):
        with tempfile.TemporaryDirectory(dir=ROOT.parent) as tmp:
            t=Path(tmp);binding=t/'binding.json';binding.write_text(json.dumps({'execution_policy':'managed'}))
            prepared=t/'prepared.json';prepared.write_text(json.dumps({'binding_path':str(binding)}))
            digest=hashlib.sha256(prepared.read_bytes()).hexdigest()
            p=subprocess.run([sys.executable,str(ROOT/'inference_ab.py'),'run-standalone','--prepared',str(prepared),
                '--prepared-sha',digest,'--output',str(t/'out'),'--device','1','--uuid','unused','--work-seconds','10'],capture_output=True,text=True)
            self.assertNotEqual(p.returncode,0)
            self.assertIn('Managed inference must call',p.stderr)
            self.assertFalse((t/'out').exists())

if __name__=='__main__':unittest.main()
