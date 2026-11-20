# toolbox-format, pinned at tag v0.1.1

Copied read-only from the public repository `smholte/toolbox-format`, **tag `v0.1.1`, commit
`cc0356c39c1237c1c89d0c557e9cb83b39962e7b`** (20 Nov 2026, MIT licence – `LICENSE`), for task 0245 (before: tag `v0.1`,
task 0217): the text
(`FORMAT.md`), the type list, the schemas, the reference code and checker (`tbf/`, `check.py`) and the made-up samples.
Never edit these files: a newer tag is a new task, which copies the new files and this list again.
`tests/test_toolbox_pinned.py` checks every file against the SHA-256 below.

Run the checker: `~/venv/bin/python tests/data/toolbox/tbf-v0.1.1/check.py <Toolbox folder>` (needs `jsonschema`,
`tools/requirements-dev.txt`).

## SHA-256

```
5210ea0875277d6da4ab9e8a9136711d67240aba47fbcfeeca66257c4fde0bf6  FORMAT.md
09e77793b04a7c6f758cc226c1b69be3a3cfce12dd3ddd03c0f8f78ed05dcbbe  LICENSE
2d1e2fc1d1dcc5030b7ada9ce69e5ee101a0b81caee6af77872ca924ce20be17  check.py
53955b6b143091aa5f441414c2e3a67e9e8b8b7cb6ffa8d6aa6477186fe489e4  samples/Toolbox/toolbox-folder.json
8d87e99d4f21eadada20f67d6d768b754f8ff6f2995adac82949492bc3b3c136  samples/Toolbox/tools/nl.fresing.house-planner/inbox/20261118-201500-4b7d10/job.json
ee43b88c07028e6284bdba20c43493766c9434ba0b916befb6951744f52d8ac5  samples/Toolbox/tools/nl.fresing.house-planner/inbox/20261118-201500-4b7d10/sample-house.hpbake
afce2db0539171cfc27bb727c387f91195c12bde6059068ae7b6e42ac0ff7207  samples/Toolbox/tools/nl.fresing.house-planner/toolbox.json
4eec87d6667c29f406ee74c191601ddd70b2f3f801567e3718176067e5cc10f5  samples/Toolbox/tools/nl.fresing.render/alive.json
067b36dfe43857492831661932cc49a63fba3aef99eea23f842695bc0f257ccb  samples/Toolbox/tools/nl.fresing.render/inbox/20261118-195100-9f3c2a/job.json
66244d40d0e2f4bc1cff805148e4f5b643e0e2aacbda09c5e83199d2243a44d1  samples/Toolbox/tools/nl.fresing.render/inbox/20261118-195100-9f3c2a/sample-house.hpscene
6c35b011da0d5bae841067b75c0cac8e41ff3da33caf6a8c11dbb19dfb70b870  samples/Toolbox/tools/nl.fresing.render/inbox/20261118-195100-9f3c2a/status.json
98e64e9377d6e6cc009003b4071636cc0251c14f29d1f9b46cfc09a1d70b86a0  samples/Toolbox/tools/nl.fresing.render/inbox/20261118-203000-c81e55/cancel.json
59c2289a0a54e153453f42252bdc9d9cb8676c54f355d1e2054158959061a702  samples/Toolbox/tools/nl.fresing.render/inbox/20261118-203000-c81e55/job.json
c84163086fd47f3ee19a5b34f8fc52649b4938981a2885d069a5310decfcb11d  samples/Toolbox/tools/nl.fresing.render/inbox/20261118-203000-c81e55/sample-house.hpscene
879afb7cf54366a1afcda5d5a54c605f94c4456e78ac426655bb9619cd200696  samples/Toolbox/tools/nl.fresing.render/inbox/20261118-203000-c81e55/status.json
a21657d9b96c47ba538f0ffb4455e049559338eb9816deca53ce5b5489388a57  samples/Toolbox/tools/nl.fresing.render/toolbox.json
0540032625827622bdccfd04b17c74acc9add1eea6ff8612d9eb1151b1391453  samples/files/sample-archive.zip
321c2152c240cdcb0ce9018e4d2a82239e79e1e4039b9565ccb5c4225ca98017  samples/files/sample-building.ifc
ee43b88c07028e6284bdba20c43493766c9434ba0b916befb6951744f52d8ac5  samples/files/sample-house.hpbake
66244d40d0e2f4bc1cff805148e4f5b643e0e2aacbda09c5e83199d2243a44d1  samples/files/sample-house.hpscene
d52ea15ab28b6a8dbc5a7623dd23c044eaa0f6460322c22030cc6b976e365637  samples/files/sample-model.glb
17fc8cf88bed2c140eaadc0fc5dd85accccddae86e4765bb0b58afdce7ef340a  samples/files/sample-notes.csv
96abb956d3050d7e64d11ddabdb6d76fc0aad26e9b9d2ee86ad9d2a657837876  samples/files/sample-part.step
2bbde5b3dc6ade86c077a399eca739d0f32efc04dc00fc3568a04678153e6adb  samples/files/sample.unknownkind
892560e74ac6a6375f04bc839713accfd3222da2e9507bab0d0ed0cb13cfe907  schemas/alive-0.schema.json
ea899855201ea9b7e02c63c385663afaab19afab9d855460ddf103b2165a19c2  schemas/cancel-0.schema.json
c0127bf69f44a14943c5d0387dc90ed1109e451565bb58888661d875cf0e8497  schemas/folder-0.schema.json
77f68c787390e0282964efefe58f17e2edf503e101f620c8bee10e34669270b1  schemas/job-0.schema.json
04aa89616558cd97e1c4ac4c3ec400f26b3b6c6ac735f9fef209cc2d459cba35  schemas/status-0.schema.json
2aeba5512c84084a892efcbe7364bfeffe04cafc2258c91196e1d63ca57ef17c  schemas/tool-0.schema.json
94b831b1ed5fa6e7e6295834b624f974e7e74ff6e74f0f34474c5a9e62963317  schemas/types-0.schema.json
371588c48fbdd77997a3911e0777cc1e765fc728906344ce8488c4d8cd0db0f0  tbf/__init__.py
0d27c1d13e9c5729296530e369d30598eee14ef09a1573ef1c106bfb0d4a95de  tbf/check.py
3e96a7caf04ca04c6d502044138b86f9327cf56b0c02e8d1f882c8877199e3af  tbf/detect.py
dfd7046cbf288f465be37aebf5678a3f152e1e2985e612091ed126cf65102dc4  tbf/folder.py
ca03b7992884016f7e63b03c1a9b385d06bee2bf53cc7c2a27d695e72010c283  tbf/names.py
82178d4dec9781d76c1a58805c4f6e29c2d2ec6cdaa43f96893f5b39fd1eea73  types.json
```
