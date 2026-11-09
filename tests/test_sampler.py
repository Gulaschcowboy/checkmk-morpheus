# SPDX-License-Identifier: GPL-2.0-only
# Copyright (c) 2026 Pawel Wladzinski <pawel.wladzinski@vayana.pl>
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import sample_vm_stats as sampler


class SamplerTests(unittest.TestCase):
    def test_samples_keep_partial_and_complete_api_timestamps(self):
        class API(sampler.Audit):
            def get(self, endpoint, **query):
                if endpoint.endswith('/3'):
                    self.calls += 1
                    stats = {'ts': '2026-11-05T00:00:00Z'} if self.calls==1 else {'ts':'2026-11-05T00:00:10Z','cpuUsage':10}
                    return {'server':{'id':3,'name':'ExampleVM','stats':stats,'apiKey':'SECRET'}}, {'status':'ok'}
                return {'servers':[{'id':3,'stats':{}},{'id':99,'name':'OTHER_VM'}], 'meta':{'total':2}}, {'status':'ok'}
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'report.txt'
            argv=['sampler','--url','https://example.invalid','--vm-id','3','--samples','2','--interval','1','--output',str(path)]
            with patch.object(sampler,'Audit',API),patch.object(sys,'argv',argv),patch.object(sampler.getpass,'getpass',return_value='TOKEN'),patch.object(sampler.time,'sleep'),contextlib.redirect_stderr(io.StringIO()),contextlib.redirect_stdout(io.StringIO()):
                sampler.main()
            raw=path.read_text();report=json.loads(raw)
            details=[e for e in report['entries'] if e['endpoint'].endswith('/3')]
            self.assertNotIn('cpuUsage',details[0]['data']['stats']['values'])
            self.assertEqual(details[1]['data']['stats']['values']['cpuUsage'],10)
            self.assertNotIn('OTHER_VM',raw)
            self.assertNotIn('SECRET',raw)
            self.assertNotIn('TOKEN',raw)

    def test_url_with_credentials_is_rejected_before_token_prompt(self):
        argv=['sampler','--url','https://user:password@example.invalid','--vm-id','3']
        with patch.object(sys,'argv',argv),patch.object(sampler.getpass,'getpass',side_effect=AssertionError('unexpected prompt')),contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):sampler.main()


if __name__=='__main__':unittest.main()
