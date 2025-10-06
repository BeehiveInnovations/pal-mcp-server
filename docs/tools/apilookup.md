# API Lookup Tool

The `apilookup` tool ensures you get **current, accurate API/SDK documentation** by forcing the AI to search for the latest information rather than relying on outdated training data. This is especially critical for OS-tied APIs (iOS, macOS, Android, etc.) where the AI's knowledge cutoff may be months or years old.
Most importantly, it does this within in a sub-process / sub-agent, saving you precious tokens within your working context window. 

## Why Use This Tool?

### Without Zen (Using Standard AI)
```
User: "How do I add glass look to a button in Swift?"

AI: [Searches based on training data knowledge cutoff]
    "SwiftUI glass morphism frosted glass effect button iOS 18 2025"

Result: You get outdated APIs for iOS 18, not the iOS 26 effect you're after
```

<div align="center">
    
 [API without Zen](https://github.com/user-attachments/assets/01a79dc9-ad16-4264-9ce1-76a56c3580ee)
 
</div>

### With Zen (Using apilookup)
```
User: "use apilookup how do I add glass look to a button in swift?"

AI: Step 1 - Search: "what is the latest iOS version 2025"
    → Finds: iOS 26 is current

    Step 2 - Search: "iOS 26 SwiftUI glass effect button 2025"
    → Gets current APIs specific to iOS 26

Result: You get the correct, current APIs that work with today's iOS version
```

<div align="center">

[API with Zen](https://github.com/user-attachments/assets/5c847326-4b66-41f7-8f30-f380453dce22)

</div>

## Key Features

### 1. **OS Version Detection** (Critical!)
For any OS-tied request (iOS, macOS, Windows, Android, watchOS, tvOS), `apilookup` **MUST**:
- First search for the current OS version ("what is the latest iOS version 2025")
- **Never** rely on the AI's training data for version numbers
- Only after confirming current version, search for APIs/SDKs for that specific version

### 2. **Authoritative Sources Only**
Prioritizes official documentation:
- Project documentation sites
- GitHub repositories
- Package registries (npm, PyPI, crates.io, Maven Central, etc.)
- Official blogs and release notes

### 3. **Actionable, Concise Results**
- Current version numbers and release dates
- Breaking changes and migration notes
- Code examples and configuration options
- Deprecation warnings and security advisories

## When to Use

- You need current API/SDK documentation or version info
- You're working with OS-specific frameworks (SwiftUI, UIKit, Jetpack Compose, etc.)
- You want to verify which version supports a feature
- You need migration guides or breaking change notes
- You're checking for deprecations or security advisories

## Usage Examples

### OS-Specific APIs
```
use apilookup how do I add glass look to a button in swift?
use apilookup what's the latest way to handle permissions in Android?
use apilookup how do I use the new macOS window management APIs?
```

### Library/Framework Versions
```
use apilookup find the latest Stripe Python SDK version and note any breaking changes since v7
use apilookup what's the current AWS CDK release and list migration steps from v2
use apilookup check the latest React version and any new hooks introduced in 2025
```

### Feature Compatibility
```
use apilookup does the latest TypeScript support decorators natively?
use apilookup what's the current status of Swift async/await on Linux?
```

## How It Works

1. **Receives your query** with API/SDK/framework name
2. **Injects mandatory instructions** that force current-year searches
3. **For OS-tied requests**: Requires two-step search (OS version first, then API)
4. **Returns structured guidance** with instructions for web search
5. **AI executes searches** and provides authoritative, current documentation

## Output Format

The tool returns JSON with:
- `status`: "web_lookup_needed"
- `instructions`: Detailed search strategy and requirements
- `user_prompt`: Your original request

The AI then performs the actual web searches and synthesizes the results into actionable documentation.

## Codex CLI Configuration Reminder

If you use Zen through the Codex CLI, the assistant needs Codex's native web-search tool to fetch current documentation. After adding the Zen MCP entry to `~/.codex/config.toml`, confirm the file also contains:

```toml
[tools]
web_search = true
```

If `[tools]` is missing, append the block manually. Without this flag, `apilookup` will keep requesting web searches that Codex cannot execute, and you'll see repeated attempts at using `curl` incorrectly.
