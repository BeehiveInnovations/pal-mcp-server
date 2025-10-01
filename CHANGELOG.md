# CHANGELOG

<!-- version list -->

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
