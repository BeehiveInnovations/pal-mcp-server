# CHANGELOG

<!-- version list -->

## v9.4.0 (2025-11-18)

### Bug Fixes

- Failing test for gemini 3.0 pro open router
  ([`19a2a89`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/19a2a89b12c5dec53aea21a4244aff7796a5e049))

### Chores

- Sync version to config.py [skip ci]
  ([`d3de61f`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/d3de61f8787ab60261d09f2c7f362c50d2093799))

### Features

- Gemini 3.0 Pro Preview for Open Router
  ([`bbfdfac`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/bbfdfac511668e8ae60f9b9b5d41eb9ab55d74cf))

### Refactoring

- Enable search on codex CLI
  ([`1579d9f`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/1579d9f806a653bb04c9c73ab304cdd0e78fbdfa))


## v9.3.1 (2025-11-18)

### Chores

- Sync version to config.py [skip ci]
  ([`d256098`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/d2560983402abf084608f7750f05407a8d3e20a0))


## v9.3.0 (2025-11-18)

### Chores

- Sync version to config.py [skip ci]
  ([`3748d47`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/3748d47faba7d871f2dd379f2c8646aa8cd3c6e9))


## v9.2.2 (2025-11-18)

### Bug Fixes

- **build**: Include clink resources in package
  ([`e9ac1ce`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/e9ac1ce3354fbb124a72190702618f94266b8459))

### Chores

- Sync version to config.py [skip ci]
  ([`749bc73`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/749bc7307949fa0b0e026bfcfbd546d7619eba8b))


## v9.2.1 (2025-11-18)

### Bug Fixes

- **server**: Iterate provider instances during shutdown
  ([`d40fc83`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/d40fc83d7549293372f3d20cc599a79ec355acef))

### Chores

- Sync version to config.py [skip ci]
  ([`84f6c4f`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/84f6c4fb241257b611f4b954c22a6b9340007a73))


## v9.2.0 (2025-11-18)

### Chores

- Sync version to config.py [skip ci]
  ([`7a1de64`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/7a1de6477aae88bfe7a2f677faf0794169651354))

### Documentation

- Streamline advanced usage guide by reorganizing table of contents for improved navigation
  ([`698d391`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/698d391b26a0dd565eada8bfa6e67e549ce1dd20))

- Update .env.example to include new GPT-5.1 model options and clarify existing model descriptions
  ([`dbbfef2`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/dbbfef292c67ed54f90f7612c9c14d4095bd6c45))

- Update advanced usage and configuration to include new GPT-5.1 models and enhance tool parameters
  ([`807c9df`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/807c9df70e3b54031ec6beea10f3975455b36dfb))

### Features

- Add new GPT-5.1 models to configuration files and update model selection logic in OpenAI provider
  ([`8e9aa23`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/8e9aa2304d5e9ea9a9f8dc2a13a27a1ced6b1608))

- Enhance model support by adding GPT-5.1 to .gitignore and updating cassette maintenance
  documentation for dual-model testing
  ([`f713d8a`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/f713d8a354a37c32a806c98994e6f949ecd64237))


## v9.1.4 (2025-11-18)

### Bug Fixes

- Replaced deprecated Codex web search configuration
  ([`2ec64ba`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/2ec64ba7489acc586846b25eedf94a4f05d5bd2d))

### Chores

- Sync version to config.py [skip ci]
  ([`4d3d177`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/4d3d177d91370097ca7ac4f922fa3a8b69ce3250))


## v9.1.3 (2025-10-22)

### Bug Fixes

- Reduced token usage, removed parameters from schema that CLIs never seem to use
  ([`3e27319`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/3e27319e60b0287df918856b58b2bbf042c948a8))

- Telemetry option no longer available in gemini 0.11
  ([`2a8dff0`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/2a8dff0cc8a3f33111533cdb971d654637ed0578))

### Chores

- Sync version to config.py [skip ci]
  ([`9e163f9`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/9e163f9dc0654fc28961c9897b7c787a2b96e57d))

- Sync version to config.py [skip ci]
  ([`557e443`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/557e443a63ffd733fb41faaa8696f6f4bb2c2fd1))

### Refactoring

- Improved precommit system prompt
  ([`3efff60`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/3efff6056e322ee1531d7bed5601038c129a8b29))


## v9.1.2 (2025-10-21)

### Bug Fixes

- Configure codex with a longer timeout
  ([`d2773f4`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/d2773f488af28986632846652874de9ff633049c))

- Handle claude's array style JSON https://github.com/BeehiveInnovations/zen-mcp-server/issues/295
  ([`d5790a9`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/d5790a9bfef719f03d17f2d719f1882e55d13b3b))

### Chores

- Sync version to config.py [skip ci]
  ([`04132f1`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/04132f1459f1e086afd8e3d456f671b63338f846))


## v9.1.1 (2025-10-17)

### Bug Fixes

- Failing test
  ([`aed3e3e`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/aed3e3ee80c440ac8ab0d4abbf235b84df723d18))

- Handler for parsing multiple generated code blocks
  ([`f4c20d2`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/f4c20d2a20e1c57d8b10e8f508e07e2a8d72f94a))

- Improved error reporting; codex cli would at times fail to figure out how to handle plain-text /
  JSON errors
  ([`95e69a7`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/95e69a7cb234305dcd37dcdd2f22be715922e9a8))

### Chores

- Sync version to config.py [skip ci]
  ([`942757a`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/942757a360a74c021b2a1aa63e394f18f5abcecd))


## v9.1.0 (2025-10-17)

### Chores

- Sync version to config.py [skip ci]
  ([`3ee0c8f`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/3ee0c8f555cb51b975700290919c2a8e2ada8cc4))

### Features

- Enhance review prompts to emphasize static analysis
  ([`36e66e2`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/36e66e2e9a44a73a466545d4d3477ecb2cb3e669))


## v9.0.4 (2025-10-17)

### Chores

- Sync version to config.py [skip ci]
  ([`8c6f653`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/8c6f6532d843f7f1b283ce9b6472e5ba991efe16))


## v9.0.3 (2025-10-16)

### Bug Fixes

- Remove duplicate -o json flag in gemini CLI config
  ([`3b2eff5`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/3b2eff58ac0e2388045a7442c63f56ce259b54ba))

### Chores

- Sync version to config.py [skip ci]
  ([`b205d71`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/b205d7159b674ce47ebc11af7255d1e3556fff93))


## v9.0.2 (2025-10-15)

### Bug Fixes

- Update Claude CLI commands to new mcp syntax
  ([`a2189cb`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/a2189cb88a295ebad6268b9b08c893cd65bc1d89))

### Chores

- Sync version to config.py [skip ci]
  ([`d08cdc6`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/d08cdc6691e0f68917f2824945905b7256e0e568))


## v9.0.1 (2025-10-14)

### Bug Fixes

- Add JSON output flag to gemini CLI configuration
  ([`eb3dff8`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/eb3dff845828f60ff2659586883af622b8b035eb))

### Chores

- Sync version to config.py [skip ci]
  ([`b9408aa`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/b9408aae8860d43b1da0ba67f9db98db7e4de2cf))


## v9.0.0 (2025-10-08)

### Chores

- Sync version to config.py [skip ci]
  ([`23c9b35`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/23c9b35d5226b07b59a4c4b3d7833ba81b019ea8))

### Features

- Claude Code as a CLI agent now supported. Mix and match: spawn claude code from within claude
  code, or claude code from within codex.
  ([`4cfaa0b`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/4cfaa0b6060769adfbd785a072526a5368421a73))


## v8.0.2 (2025-10-08)

### Bug Fixes

- Restore run-server quote trimming regex
  ([`1de4542`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/1de454224c105891137134e2a25c2ee4f00dba45))

### Chores

- Sync version to config.py [skip ci]
  ([`728fb43`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/728fb439b929c9dc37646b24537ae043208fda7d))


## v8.0.1 (2025-10-08)

### Bug Fixes

- Resolve executable path for cross-platform compatibility in CLI agent
  ([`f98046c`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/f98046c2fccaa7f9a24665a0d705a98006461da5))

### Chores

- Sync version to config.py [skip ci]
  ([`52245b9`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/52245b91eaa5d720f8c3b21ead55248dd8e8bd57))

### Testing

- Fix clink agent tests to mock shutil.which() for executable resolution
  ([`4370be3`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/4370be33b4b69a40456527213bcd62321a925a57))


## v8.0.0 (2025-10-07)

### Chores

- Sync version to config.py [skip ci]
  ([`4c34541`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/4c3454121c3c678cdfe8ea03fa77f4dd414df9bc))


## v7.8.1 (2025-10-07)

### Bug Fixes

- Updated model description to fix test
  ([`04f7ce5`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/04f7ce5b03804564263f53a765931edba9c320cd))

### Chores

- Sync version to config.py [skip ci]
  ([`c27e81d`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/c27e81d6d2f22978816f798a161a869d1ab5f025))

### Refactoring

- Moved registries into a separate module and code cleanup
  ([`7c36b92`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/7c36b9255a13007a10af4fadefc21aadfce482b0))


## v7.8.0 (2025-10-07)

### Chores

- Sync version to config.py [skip ci]
  ([`3e5fa96`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/3e5fa96c981bbd7b844a9887a518ffe266b78e9b))

### Documentation

- Consensus video
  ([`2352684`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/23526841922a73c68094e5205e19af04a1f6c8cc))

- Formatting
  ([`7d7c74b`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/7d7c74b5a38b7d1adf132b8e28034017df7aa852))

- Link to videos from main page
  ([`e8ef193`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/e8ef193daba393b55a3beaaba49721bb9182378a))

- Update README.md
  ([`7b13543`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/7b13543824fc0af729daf753ecdddba9ee7d9f1e))

### Features

- All native providers now read from catalog files like OpenRouter / Custom configs. Allows for
  greater control over the capabilities
  ([`2a706d5`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/2a706d5720c0bf97b71c3e0fc95c15f78015bedf))

- Provider cleanup
  ([`9268dda`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/9268ddad2a07306351765b47098134512739f49f))

### Refactoring

- New base class for model registry / loading
  ([`02d13da`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/02d13da897016d7491b4a10a1195983385d66654))


## v7.7.0 (2025-10-07)

### Chores

- Sync version to config.py [skip ci]
  ([`70ae62a`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/70ae62a2cd663c3abcabddd1be1bc6ed9512d7df))

### Documentation

- Video
  ([`ed5dda7`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/ed5dda7c5a9439c2835cc69d76e6377169ad048a))

### Features

- More aliases
  ([`5f0aaf5`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/5f0aaf5f69c9d188d817b5ffbf6738c61da40ec7))


## v7.6.0 (2025-10-07)

### Chores

- Sync version to config.py [skip ci]
  ([`c1c75ba`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/c1c75ba304c2840329650c46273e87eab9b05906))

- Sync version to config.py [skip ci]
  ([`0fa9b66`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/0fa9b6658099c8e0d79fda0c7d2347f62d0e6137))

### Documentation

- Info about AI client timeouts
  ([`3ddfed5`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/3ddfed5ef09000791e1c94b041c43dc273ed53a8))

### Features

- Add support for openai/gpt-5-pro model
  ([`abed075`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/abed075b2eaa99e9618202f47ff921094baae952))


## v7.5.2 (2025-10-06)

### Bug Fixes

- Handle 429 response https://github.com/BeehiveInnovations/zen-mcp-server/issues/273
  ([`cbe1d79`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/cbe1d7993276bd014b495cbd2d0ece1f5d7583d9))

### Chores

- Sync version to config.py [skip ci]
  ([`74fdd36`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/74fdd36de92d34681fcc5a2f772c3d05634f0a55))


## v7.5.1 (2025-10-06)

### Chores

- Sync version to config.py [skip ci]
  ([`004e379`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/004e379cf2f1853829dccb15fa72ec18d282f1a4))


## v7.5.0 (2025-10-06)

### Chores

- Sync version to config.py [skip ci]
  ([`71e7cd5`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/71e7cd55b1f4955a6d718fddc0de419414d133b6))

### Documentation

- Video
  ([`775e4d5`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/775e4d50b826858095c5f2a61a07fc01c4a00816))

- Videos
  ([`bb2066c`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/bb2066c909f6581ba40fc5ddef3870954ae553ab))

### Features

- Support for GPT-5-Pro highest reasoning model
  https://github.com/BeehiveInnovations/zen-mcp-server/issues/275
  ([`a65485a`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/a65485a1e52fc79739000426295a27d096f4c9d8))


## v7.4.0 (2025-10-06)

### Chores

- Sync version to config.py [skip ci]
  ([`76bf98e`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/76bf98e5cd972dabd3c79b25fcb9b9a717b23f6d))

### Features

- Improved prompt
  ([`b1e9963`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/b1e9963991a41dff082ec1dce5691c318f105e6d))


## v7.3.0 (2025-10-06)

### Chores

- Sync version to config.py [skip ci]
  ([`e7920d0`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/e7920d0ed16c0e6de9d1ccaa0b58d3fb5cbd7f2f))

### Documentation

- Fixed typo
  ([`3ab0aa8`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/3ab0aa8314ad5992bcb00de549a0fab2e522751d))

- Fixed typo
  ([`c17ce3c`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/c17ce3cf958d488b97fa7127942542ab514b58bd))

- Update apilookup.md
  ([`1918679`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/19186794edac4fce5523e671310aecff4cbfdc81))

- Update README.md
  ([`23c6c78`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/23c6c78bf152ede6e7b5f7b7770b12a8442845a3))

### Features

- Codex supports web-search natively but needs to be turned on, run-server script asks if the user
  would like this done
  ([`97ba7e4`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/97ba7e44ce7e3fd874759514ed2f0738033fc801))


## v7.2.0 (2025-10-06)

### Chores

- Sync version to config.py [skip ci]
  ([`1854b1e`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/1854b1e26b705cda0dc3f4d733647f1454aa0352))

### Documentation

- Updated
  ([`bb57f71`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/bb57f719666ab6a586d835688ff8086282a5a0dc))

### Features

- New tool to perform apilookup (latest APIs / SDKs / language features etc)
  https://github.com/BeehiveInnovations/zen-mcp-server/issues/204
  ([`5bea595`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/5bea59540f58b3c45044828c10f131aed104dd1c))

### Refactoring

- De-duplicate roles to avoid explosion when more CLIs get added
  ([`c42e9e9`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/c42e9e9c34d7ae4732e2e4fbed579b681a6d170d))


## v7.1.1 (2025-10-06)

### Bug Fixes

- Clink missing in toml
  ([`1ff77fa`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/1ff77faa800ad6c2dde49cad98dfa72035fe1c81))

### Chores

- Sync version to config.py [skip ci]
  ([`e02e78d`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/e02e78d903b35f4c01b8039f4157e97b38d3ec7b))

### Documentation

- Example for codex cli
  ([`344c42b`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/344c42bcbfb543bfd05cbc27fd5b419c76b77954))

- Example for codex cli
  ([`c3044de`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/c3044de7424e638dde5c8ec49adb6c3c7c5a60b2))

- Update README.md
  ([`2e719ae`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/2e719ae35e7979f7b83bd910867e79863a7f9ceb))


## v7.1.0 (2025-10-05)

### Chores

- Sync version to config.py [skip ci]
  ([`d54bfdd`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/d54bfdd49797d076ec9cade44c56292a8089c744))

### Features

- Support for codex as external CLI
  ([`561e4aa`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/561e4aaaa8a89eb89c03985b9e7720cc98ef666c))


## v7.0.2 (2025-10-05)

### Chores

- Sync version to config.py [skip ci]
  ([`f2142a2`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/f2142a22ec50abc54b464eedd6b8239d20c509be))


## v7.0.1 (2025-10-05)

### Bug Fixes

- --yolo needed for running shell commands, documentation added
  ([`15ae3f2`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/15ae3f24babccf42f43be5028bf8c60c05a6beaf))

### Chores

- Sync version to config.py [skip ci]
  ([`bc4a27b`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/bc4a27b18a4a3f45afb22178e61ea0be4d6a273c))

### Documentation

- Updated intro
  ([`fb668c3`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/fb668c39b5f6e3dd37f7027f953f6004f258f2bf))


## v7.0.0 (2025-10-05)

### Chores

- Sync version to config.py [skip ci]
  ([`0d46976`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/0d46976a8aa85254e4dbe06f5e71161cd3b13938))

- Sync version to config.py [skip ci]
  ([`8296bf8`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/8296bf871c39597a904c70e7d98c72fcb4dc5a84))

### Documentation

- Instructions for OpenCode
  ([`bd66622`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/bd666227c8f7557483f7e24fb8544fc0456600dc))

- Updated intro
  ([`615873c`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/615873c3db2ecf5ce6475caa3445e1da9a2517bd))

### Features

- Huge update - Link another CLI (such as `gemini` directly from with Claude Code / Codex).
  https://github.com/BeehiveInnovations/zen-mcp-server/issues/208
  ([`a2ccb48`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/a2ccb48e9a5080a75dbfd483b5f09fc719c887e5))

### Refactoring

- Fixed test
  ([`9c99b9b`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/9c99b9b35219f54db8d7be0958d4390a106631ae))

- Include file modification dates too
  ([`47973e9`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/47973e945efa2cdbdb8f3404d467d7f1abc62b0a))


## v6.1.0 (2025-10-04)

### Chores

- Sync version to config.py [skip ci]
  ([`18095d7`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/18095d7d398e4bf3d24c57a52c81ac619acb1b89))

### Documentation

- Updated intro
  ([`aa65394`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/aa6539472c4ddf1c3c1bac446fdee03e75e1cb50))

### Features

- Support for Qwen Code
  ([`fe9968b`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/fe9968b633d0312b82426e9ebddfe1d6515be3c5))


## v6.0.0 (2025-10-04)

### Chores

- Sync version to config.py [skip ci]
  ([`ae8749a`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/ae8749ab37bdaa7e225b5219820adeb74ca9a552))

### Documentation

- Updated
  ([`e91ed2a`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/e91ed2a924b1702edf9e1417479ac0dee0ca1553))

### Features

- Azure OpenAI / Azure AI Foundry support. Models should be defined in conf/azure_models.json (or a
  custom path). See .env.example for environment variables or see readme.
  https://github.com/BeehiveInnovations/zen-mcp-server/issues/265
  ([`ff9a07a`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/ff9a07a37adf7a24aa87c63b3ba9db88bdff467b))

- Breaking change - OpenRouter models are now read from conf/openrouter_models.json while Custom /
  Self-hosted models are read from conf/custom_models.json
  ([`ff9a07a`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/ff9a07a37adf7a24aa87c63b3ba9db88bdff467b))

- OpenAI/compatible models (such as Azure OpenAI) can declare if they use the response API instead
  via `use_openai_responses_api`
  ([`3824d13`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/3824d131618683572e9e8fffa6b25ccfabf4cf50))

- OpenRouter / Custom Models / Azure can separately also use custom config paths now (see
  .env.example )
  ([`ff9a07a`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/ff9a07a37adf7a24aa87c63b3ba9db88bdff467b))

### Refactoring

- Breaking change: `is_custom` property has been removed from model_capabilities.py (and thus
  custom_models.json) given each models are now read from separate configuration files
  ([`ff9a07a`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/ff9a07a37adf7a24aa87c63b3ba9db88bdff467b))

- Model registry class made abstract, OpenRouter / Custom Provider / Azure OpenAI now subclass these
  ([`ff9a07a`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/ff9a07a37adf7a24aa87c63b3ba9db88bdff467b))


## v5.22.0 (2025-10-04)

### Bug Fixes

- CI test
  ([`bc93b53`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/bc93b5343bbd8657b95ab47c00a2cb99a68a009f))

- Listmodels to always honor restricted models
  ([`4015e91`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/4015e917ed32ae374ec6493b74993fcb34f4a971))

### Chores

- Sync version to config.py [skip ci]
  ([`054e34e`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/054e34e31ca5bee5a11c0e3e6537f58e8897c79c))

- Sync version to config.py [skip ci]
  ([`c0334d7`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/c0334d77922f1b05e3fd755851da112567fb9ae6))

### Features

- Centralized environment handling, ensures ZEN_MCP_FORCE_ENV_OVERRIDE is honored correctly
  ([`2c534ac`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/2c534ac06e4c6078b96781dfb55c5759b982afe8))

### Refactoring

- Don't retry on 429
  ([`d184024`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/d18402482087f52b7bd07755c9304ed00ed20592))

- Improved retry logic and moved core logic to base class
  ([`f955100`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/f955100f3a82973ccd987607e1d8a1bbe07828c8))

- Removed subclass override when the base class should be resolving the model name
  ([`06d7701`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/06d7701cc3ee09732ab713fa9c7c004199154483))


## v5.21.0 (2025-10-03)

### Chores

- Sync version to config.py [skip ci]
  ([`ddb20a6`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/ddb20a6cdb8cdeee27c0aacb0b9c794283b5774c))


## v5.20.1 (2025-10-03)

### Chores

- Sync version to config.py [skip ci]
  ([`03addcf`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/03addcfa2d3aed5086fe4c94e8b9ae56229a93ae))


## v5.20.0 (2025-10-03)

### Chores

- Sync version to config.py [skip ci]
  ([`539bc72`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/539bc72f1ca2a2cadcccad02de1fd5fc22cd0415))


## v5.19.0 (2025-10-03)

### Bug Fixes

- Add GPT-5-Codex to Responses API routing and simplify comments
  ([`82b021d`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/82b021d75acc791e68c7afb35f6492f68cf02bec))

### Chores

- Sync version to config.py [skip ci]
  ([`8e32ef3`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/8e32ef33e3ce7ab2a9d7eb5c90fe5b93b12d5c26))

### Documentation

- Bumped defaults
  ([`95d98a9`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/95d98a9bc0a5bafadccb9f6d1e4eda97a0dd2ce7))

### Features

- Add GPT-5-Codex support with Responses API integration
  ([`f265342`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/f2653427ca829368e7145325d20a98df3ee6d6b4))

### Testing

- Cross tool memory recall, testing continuation via cassette recording
  ([`88493bd`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/88493bd357c6a12477c3160813100dae1bc46493))


## v5.18.3 (2025-10-03)

### Bug Fixes

- External model name now recorded properly in responses
  ([`d55130a`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/d55130a430401e106cd86f3e830b3d756472b7ff))

### Chores

- Sync version to config.py [skip ci]
  ([`5714e20`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/5714e2016405f7607b44d78f85081c7ccee706e5))

### Documentation

- Updated docs
  ([`b4e5090`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/b4e50901ba60c88137a29d00ecf99718582856d3))

### Refactoring

- Generic name for the CLI agent
  ([`e9b6947`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/e9b69476cd922c12931d62ccc3be9082bbbf6014))

- Generic name for the CLI agent
  ([`7a6fa0e`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/7a6fa0e77a8c4a682dc11c9bbb16bdaf86d9edf4))

- Generic name for the CLI agent
  ([`b692da2`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/b692da2a82facce7455b8f2ec0108e1db84c07c3))

- Generic name for the CLI agent
  ([`f76ebbf`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/f76ebbf280cc78ffcfe17cb4590aeaa231db8aa1))

- Generic name for the CLI agent
  ([`c05913a`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/c05913a09e53e195b9a108647c09c061ced19d17))

- Generic name for the CLI agent
  ([`0dfaa63`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/0dfaa6312ed95ac3d1ae0032334ae1286871b15e))

### Testing

- Fixed integration tests, removed magicmock
  ([`87ccb6b`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/87ccb6b25ba32a3cb9c4cc64fc0e96294f492c04))


## v5.18.2 (2025-10-02)

### Bug Fixes

- Https://github.com/BeehiveInnovations/zen-mcp-server/issues/194
  ([`8b3a286`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/8b3a2867fb83eccb3a8e8467e7e3fc5b8ebe1d0c))

### Chores

- Sync version to config.py [skip ci]
  ([`bf2196c`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/bf2196cdd58ae8d8d93597f2be69c798265d678f))


## v5.18.1 (2025-10-02)

### Chores

- Sync version to config.py [skip ci]
  ([`e434a26`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/e434a2614af82efd15de4dd94b2c30559c91414e))


## v5.18.0 (2025-10-02)

### Chores

- Sync version to config.py [skip ci]
  ([`e78fe35`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/e78fe35a1b64cc0ed89664440ef7c7b94495d7dc))

### Features

- Added `intelligence_score` to the model capabilities schema; a 1-20 number that can be specified
  to influence the sort order of models presented to the CLI in `auto selection` mode
  ([`6cab9e5`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/6cab9e56fc5373da5c11d4545bcb85371d4803a4))


## v5.17.4 (2025-10-02)

### Chores

- Sync version to config.py [skip ci]
  ([`a6c9b92`](https://github.com/BeehiveInnovations/zen-mcp-server/commit/a6c9b9212c77852d9e9a8780f4bc3e53b3bfed2f))


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
