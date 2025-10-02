# CHANGELOG

<!-- version list -->

## v5.17.3 (2025-10-02)

### Chores

- Sync version to config.py [skip ci]
  ([`722f6f8`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/722f6f86ae228206ce0094d109a3b20499d4e11a))


## v5.17.2 (2025-10-02)

### Chores

- Sync version to config.py [skip ci]
  ([`e47a7e8`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/e47a7e89d5bfad0bb0150cb3207f1a37dc91b170))


## v5.17.1 (2025-10-02)

### Bug Fixes

- Baseclass should return MODEL_CAPABILITIES
  ([`82a03ce`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/82a03ce63f28fece17bfc1d70bdb75aadec4c6bb))

### Chores

- Sync version to config.py [skip ci]
  ([`7ce66bd`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/7ce66bd9508865cef64dc30936e86e37c1a306d0))

### Documentation

- Document custom timeout values
  ([`218fbdf`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/218fbdf49cb90f2353f58bbaef567519dd876634))

### Refactoring

- Clean temperature inference
  ([`9c11ecc`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/9c11ecc4bf37562aa08dc3ecfa70f380e0ead357))

- Cleanup
  ([`6ec2033`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/6ec2033f34c74ad139036de83a34cf6d374db77b))

- Cleanup provider base class; cleanup shared responsibilities; cleanup public contract
  ([`693b84d`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/693b84db2b87271ac809abcf02100eee7405720b))

- Cleanup token counting
  ([`7fe9fc4`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/7fe9fc49f8e3cd92be4c45a6645d5d4ab3014091))

- Code cleanup
  ([`bb138e2`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/bb138e2fb552f837b0f9f466027580e1feb26f7c))

- Code cleanup
  ([`182aa62`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/182aa627dfba6c578089f83444882cdd2635a7e3))

- Moved image related code out of base provider into a separate utility
  ([`14a35af`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/14a35afa1d25408e62b968d9846be7bffaede327))

- Moved temperature method from base provider to model capabilities
  ([`6d237d0`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/6d237d09709f757a042baf655f47eb4ddfc078ad))

- Moved temperature method from base provider to model capabilities
  ([`f461cb4`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/f461cb451953f882bbde096a9ecf0584deb1dde8))

- Removed hard coded checks, use model capabilities instead
  ([`250545e`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/250545e34f8d4f8026bfebb3171f3c2bc40f4692))

- Removed hook from base class, turned into helper static method instead
  ([`2b10adc`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/2b10adcaf2b8741f0da5de84cc3483eae742a014))

- Removed method from provider, should use model capabilities instead
  ([`a254ff2`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/a254ff2220ba00ec30f5110c69a4841419917382))

- Renaming to reflect underlying type
  ([`1dc25f6`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/1dc25f6c3d4cdbf01f041cc424e3b5235c23175b))


## v5.17.0 (2025-10-02)

### Bug Fixes

- Use types.HttpOptions from module imports instead of local import
  ([`956e8a6`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/956e8a6927837f5c7f031a0db1dd0b0b5483c626))

### Chores

- Sync version to config.py [skip ci]
  ([`0836213`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/0836213071d0037d8a6d2e64d34ab5df79b8e684))

### Code Style

- Apply Black formatting to use double quotes
  ([`33ea896`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/33ea896c511764904bf2b6b22df823928f88a148))

### Features

- Add custom Gemini endpoint support
  ([`462bce0`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/462bce002e2141b342260969588e69f55f8bb46a))

### Refactoring

- Simplify Gemini provider initialization using kwargs dict
  ([`023940b`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/023940be3e38a7eedbc8bf8404a4a5afc50f8398))


## v5.16.0 (2025-10-01)

### Bug Fixes

- Resolve logging timing and import organization issues
  ([`d34c299`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/d34c299f02a233af4f17bdcc848219bf07799723))

### Chores

- Sync version to config.py [skip ci]
  ([`b6c4bca`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/b6c4bca158e4cee1ae4abd08b7e55216ebffba2d))

### Code Style

- Fix ruff import sorting issue
  ([`4493a69`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/4493a693332e0532d04ad3634de2a2f5b1249b64))

### Features

- Add configurable environment variable override system
  ([`93ce698`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/93ce6987b6e7d8678ffa5ac51f5106a7a21ce67b))


## v5.15.0 (2025-10-01)

### Chores

- Sync version to config.py [skip ci]
  ([`b0fe956`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/b0fe956f8a50240507e0fc911f0800634c15e9f7))

### Features

- Depending on the number of tools in use, this change should save ~50% of overall tokens used.
  fixes https://github.com/BeehiveInnovations/zen-mcp-server/issues/255 but also refactored
  individual tools to instead encourage the agent to use the listmodels tool if needed.
  ([`d9449c7`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/d9449c7bb607caff3f0454f210ddfc36256c738a))

### Performance Improvements

- Tweaks to schema descriptions, aiming to reduce token usage without performance degradation
  ([`cc8a4df`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/cc8a4dfd21b6f3dae4972a833b619e53c964693b))

### Refactoring

- Trimmed some prompts
  ([`f69ff03`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/f69ff03c4d10e606a1dfed2a167f3ba2e2236ba8))


## v5.14.1 (2025-10-01)

### Bug Fixes

- Https://github.com/BeehiveInnovations/zen-mcp-server/issues/258
  ([`696b45f`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/696b45f25e80faccb67034254cf9a8fc4c643dbd))

### Chores

- Sync version to config.py [skip ci]
  ([`692016c`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/692016c6205ed0a0c3d9e830482d88231aca2e31))


## v5.14.0 (2025-10-01)

### Chores

- Sync version to config.py [skip ci]
  ([`c0f822f`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/c0f822ffa23292d668f7b5dd3cb62e3f23fb29af))

### Features

- Add Claude Sonnet 4.5 and update alias configuration
  ([`95c4822`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/95c4822af2dc55f59c0e4ed9454673d6ca964731))

### Testing

- Update tests to match new Claude Sonnet 4.5 alias configuration
  ([`7efb409`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/7efb4094d4eb7db006340d3d9240b9113ac25cd3))


## v5.13.0 (2025-10-01)

### Bug Fixes

- Add sonnet alias for Claude Sonnet 4.1 to match opus/haiku pattern
  ([`dc96344`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/dc96344db043e087ee4f8bf264a79c51dc2e0b7a))

- Missing "optenai/" in name
  ([`7371ed6`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/7371ed6487b7d90a1b225a67dca2a38c1a52f2ad))

### Chores

- Sync version to config.py [skip ci]
  ([`b8479fc`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/b8479fc638083d6caa4bad6205e3d3fcab830aca))

### Features

- Add comprehensive GPT-5 series model support
  ([`4930824`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/493082405237e66a2f033481a5f8bf8293b0d553))


## v5.12.1 (2025-10-01)

### Bug Fixes

- Resolve consensus tool model_context parameter missing issue
  ([`9044b63`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/9044b63809113047fe678d659e4fcd175f58e87a))

### Chores

- Sync version to config.py [skip ci]
  ([`e3ebf4e`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/e3ebf4e94eba63acdc4df5a0b0493e44e3343dd1))

### Code Style

- Fix trailing whitespace in consensus.py
  ([`0760b31`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/0760b31f8a6d03c4bea3fd2a94dfbbfab0ad5079))

### Refactoring

- Optimize ModelContext creation in consensus tool
  ([`30a8952`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/30a8952fbccd22bebebd14eb2c8005404b79bcd6))


## v5.12.0 (2025-10-01)

### Bug Fixes

- Removed use_websearch; this parameter was confusing Codex. It started using this to prompt the
  external model to perform searches! web-search is enabled by Claude / Codex etc by default and the
  external agent can ask claude to search on its behalf.
  ([`cff6d89`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/cff6d8998f64b73265c4e31b2352462d6afe377f))

### Chores

- Sync version to config.py [skip ci]
  ([`28cabe0`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/28cabe0833661b0bab56d4227781ee2da332b00c))

### Features

- Implement semantic cassette matching for o3 models
  ([`70fa088`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/70fa088c32ac4e6153d5e7b30a3e32022be2f908))


## v5.11.2 (2025-10-01)

### Chores

- Sync version to config.py [skip ci]
  ([`4d6f1b4`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/4d6f1b41005dee428c955e33f04f8f9f6259e662))


## v5.11.1 (2025-10-01)

### Bug Fixes

- Remove duplicate OpenAI models from listmodels output
  ([`c29e762`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/c29e7623ace257eb45396cdf8c19e1659e29edb9))

### Chores

- Sync version to config.py [skip ci]
  ([`1209064`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/12090646ee83f2368311d595d87ae947e46ddacd))

### Testing

- Update OpenAI provider alias tests to match new format
  ([`d13700c`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/d13700c14c7ee3d092302837cb1726d17bab1ab8))


## v5.11.0 (2025-08-26)

### Chores

- Sync version to config.py [skip ci]
  ([`9735469`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/973546990f2c45afa93f1aa6de33ff461ecf1a83))

### Features

- Codex CLI support
  ([`ce56d16`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/ce56d16240ddcc476145a512561efe5c66438f0d))


## v5.10.3 (2025-08-24)

### Bug Fixes

- Address test failures and PR feedback
  ([`6bd9d67`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/6bd9d6709acfb584ab30a0a4d6891cabdb6d3ccf))

- Resolve temperature handling issues for O3/custom models
  ([#245](https://github.com/BeehiveInnovations/zen-mcp-server/pull/245),
  [`3b4fd88`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/3b4fd88d7e9a3f09fea616a10cb3e9d6c1a0d63b))

### Chores

- Sync version to config.py [skip ci]
  ([`d6e6808`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/d6e6808be525192ab8388c0f01bc1bbd016fc23a))


## v5.10.2 (2025-08-24)

### Bug Fixes

- Another fix for https://github.com/BeehiveInnovations/zen-mcp-server/issues/251
  ([`a07036e`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/a07036e6805042895109c00f921c58a09caaa319))

### Chores

- Sync version to config.py [skip ci]
  ([`9da5c37`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/9da5c37809cbde19d0c7ffed273ae93ca883a016))


## v5.10.0 (2025-08-22)

### Chores

- Sync version to config.py [skip ci]
  ([`1254205`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/12542054a214022d3f515e53367f5bf3a77fb289))

### Features

- Refactored and tweaked model descriptions / schema to use fewer tokens at launch (average
  reduction per field description: 60-80%) without sacrificing tool effectiveness
  ([`4b202f5`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/4b202f5d1d24cea1394adab26a976188f847bd09))


## v5.9.0 (2025-08-21)

### Documentation

- Update instructions for precommit
  ([`90821b5`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/90821b51ff653475d9fb1bc70b57951d963e8841))

### Features

- Refactored and improved codereview in line with precommit. Reviews are now either external
  (default) or internal. Takes away anxiety and loss of tokens when Claude incorrectly decides to be
  'confident' about its own changes and bungle things up.
  ([`80d21e5`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/80d21e57c0246762c0a306ede5b93d6aeb2315d8))

### Refactoring

- Minor prompt tweaks
  ([`d30c212`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/d30c212029c05b767d99b5391c1dd4cee78ef336))


## v5.8.6 (2025-08-20)

### Bug Fixes

- Escape backslashes in TOML regex pattern
  ([`1c973af`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/1c973afb002650b9bbee8a831b756bef848915a1))

- Establish version 5.8.6 and add version sync automation
  ([`90a4195`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/90a419538128b54fbd30da4b8a8088ac59f8c691))

- Restore proper version 5.8.6
  ([`340b58f`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/340b58f2e790b84c3736aa96df7f6f5f2d6a13c9))

### Chores

- Sync version to config.py [skip ci]
  ([`4f82f65`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/4f82f6500502b7b6ba41875a560c41f6a63b683b))


## v1.1.0 (2025-08-20)

### Features

- Improvements to precommit
  ([`2966dcf`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/2966dcf2682feb7eef4073738d0c225a44ce0533))


## v1.0.0 (2025-08-20)

- Initial Release
