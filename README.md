<div align="center">

  [Zen in action](https://github.com/user-attachments/assets/0d26061e-5f21-4ab1-b7d0-f883ddc2c3da)

👉 **[Watch more examples](#-watch-tools-in-action)**

### Your CLI + Multiple Models = Your AI Dev Team

**Use the 🤖 CLI you love:**  
[Claude Code](https://www.anthropic.com/claude-code) · [Gemini CLI](https://github.com/google-gemini/gemini-cli) · [Codex CLI](https://github.com/openai/codex) · [Qwen Code CLI](https://qwenlm.github.io/qwen-code-docs/) · [Cursor](https://cursor.com) · _and more_

**With multiple models within a single prompt:**  
Gemini · OpenAI · Anthropic · Grok · Azure · Ollama · OpenRouter · DIAL · On-Device Model

</div>

---

## 🧘 Zen MCP: Many Workflows. One Context.

**Zen MCP** is a **Model Context Protocol server** that transforms your CLI or IDE into a multi-model AI workspace.  
Instead of depending on one model, Zen lets your favorite tool — like Claude Code, Codex CLI, or Gemini CLI — **collaborate with multiple AI models** in a single session.

> Build, review, debug, and plan — with multiple AI models working together under your CLI’s control.

---

## 🚀 Why Zen MCP?

**Why rely on one AI model when you can orchestrate them all?**

Zen MCP supercharges AI tools and IDEs by connecting them to **multiple models simultaneously**, enabling true multi-agent collaboration.

### Highlights

- 🧩 **Multi-Model Orchestration** – Combine Gemini, GPT-5, O3, Grok, Ollama, and more in one workflow  
- 🔁 **Conversation Continuity** – Context flows seamlessly between tools and models  
- 🧠 **Guided Workflows** – Code review, debugging, and planning with consistent reasoning  
- 🪄 **Context Revival** – Recover discussions even after context resets  
- 🔒 **Local & Private** – Run local Llama or Mistral via Ollama for privacy and zero API cost  
- ⚙️ **Extensible** – Add or disable tools easily via `.env` or `mcp.json`

> Think of it as **Claude Code _for_ Claude Code** — the super-glue between your favorite AI dev tools.

---

## 🆕 CLI-to-CLI Bridge (`clink`)

The **[`clink`](docs/tools/clink.md)** (CLI + Link) tool connects external AI CLIs directly into your workflow:

- Connect [Gemini CLI](https://github.com/google-gemini/gemini-cli), [Codex CLI](https://github.com/openai/codex), [Claude Code](https://www.anthropic.com/claude-code)
- Launch isolated **sub-agents** inside your current CLI session
- Run separate tasks with **context isolation**
- Create **specialized roles** (planner, codereviewer, debugger)
- Enjoy **seamless continuity** — sub-CLIs share context between tools

```bash
# Example: Spawn Codex subagent for code review
clink with codex codereviewer to audit auth module for security issues

# Consensus across models → Implementation handoff
Use consensus with gpt-5 and gemini-pro to decide: dark mode or offline support next
Continue with clink gemini - implement the recommended feature
