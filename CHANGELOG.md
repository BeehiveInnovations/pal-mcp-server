# CHANGELOG

<!-- version list -->

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
