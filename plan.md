# Zen MCP「Skills 模式」落地计划（修订版）

## 目标与范围
- 在保留现有 MCP 能力的基础上，新增可选"Skills 模式"，以技能包形式向 Claude Code 分发。
- 通过 `run-server.sh --skills` 安装技能到 `~/.claude/skills/`。
- 复用现有工具实现（chat、codereview、debug、planner、consensus、thinkdeep 等），避免重复业务逻辑。

## 关键修正（基于官方文档）

### ❌ 原计划问题
- 嵌套结构 `skills/zen/planner/SKILL.md` **不支持**
- zip 打包分发**非官方推荐**

### ✅ 修正方案
- 每个技能必须是**独立目录**：`skills/zen-chat/`、`skills/zen-codereview/` 等
- 安装方式：**直接复制目录**到 `~/.claude/skills/`
- 分发方式：Git 仓库或目录复制（zip 作为备选）

## Skills 技术规范

### SKILL.md 格式
```yaml
---
name: zen-codereview                    # 必需，小写+连字符，最多64字符
description: 使用多模型进行代码审查...   # 必需，最多1024字符
allowed-tools: Bash, Read               # 可选，限制工具
---

# 标题

## Instructions
步骤说明...

## Examples
使用示例...
```

### 渐进式加载（Token 优化）
| 层级 | 内容 | Token 消耗 | 加载时机 |
|------|------|----------|---------|
| 元数据 | name + description | ~100 tokens | Claude 启动时 |
| 指令 | SKILL.md 正文 | <5k tokens | 技能激活时 |
| 资源 | scripts/references | 按需 | Claude 需要时 |

### 目录结构
```
pal-mcp-server/
├── skills/                          # 技能源目录（项目内）
│   ├── zen-chat/
│   │   ├── SKILL.md
│   │   └── scripts/
│   │       └── zen_skill_runner.py  # 复制自共享脚本
│   ├── zen-codereview/
│   │   ├── SKILL.md
│   │   └── scripts/
│   │       └── zen_skill_runner.py
│   ├── zen-debug/
│   │   └── SKILL.md
│   ├── zen-planner/
│   │   └── SKILL.md
│   ├── zen-consensus/
│   │   └── SKILL.md
│   └── zen-thinkdeep/
│       └── SKILL.md
├── scripts/
│   └── zen_skill_runner.py          # 共享执行入口（源文件）
└── run-server.sh                    # 增加 --skills 参数
```

### 安装后结构
```
~/.claude/skills/
├── zen-chat/
│   ├── SKILL.md
│   └── scripts/
│       └── zen_skill_runner.py
├── zen-codereview/
│   ├── SKILL.md
│   └── scripts/
│       └── zen_skill_runner.py
└── ...
```

## 工作分解与步骤

### Phase 1: 核心实现

#### 1) zen_skill_runner.py（共享执行入口）
```python
#!/usr/bin/env python3
"""
Zen Skill Runner - 统一调用 Zen MCP 工具的 CLI 入口
用法: python zen_skill_runner.py <tool> --input '<json>'
"""
import sys
import json
import asyncio
from pathlib import Path

# 添加项目根目录到路径
ZEN_ROOT = Path(__file__).resolve().parents[2]  # skills/zen-*/scripts/ -> 根目录
sys.path.insert(0, str(ZEN_ROOT))

from tools import TOOLS  # 复用现有工具

async def run_tool(tool_name: str, args: dict) -> dict:
    if tool_name not in TOOLS:
        return {"status": "error", "message": f"Unknown tool: {tool_name}"}
    tool = TOOLS[tool_name]
    try:
        result = await tool.execute(args)
        return {"status": "ok", "result": result[0].text if result else ""}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def main():
    if len(sys.argv) < 2:
        print("Usage: python zen_skill_runner.py <tool> --input '<json>'")
        sys.exit(1)

    tool_name = sys.argv[1]
    args = {}

    if "--input" in sys.argv:
        idx = sys.argv.index("--input")
        if idx + 1 < len(sys.argv):
            args = json.loads(sys.argv[idx + 1])

    result = asyncio.run(run_tool(tool_name, args))
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
```

#### 2) SKILL.md 示例（zen-codereview）
```yaml
---
name: zen-codereview
description: 使用 Zen 多模型进行代码审查，覆盖质量、安全、性能、架构分析。当需要深度代码审查或多模型验证时使用。
allowed-tools: Bash, Read
---

# Zen Code Review

## Overview
使用 Zen MCP Server 的 codereview 工具进行系统化代码审查。

## Instructions

1. 运行代码审查：
```bash
python scripts/zen_skill_runner.py codereview --input '{"prompt": "审查这段代码", "relevant_files": ["file.py"], "review_type": "full"}'
```

2. 快速审查模式：
```bash
python scripts/zen_skill_runner.py codereview --input '{"prompt": "快速检查", "relevant_files": ["src/"], "review_type": "quick"}'
```

3. 安全审查：
```bash
python scripts/zen_skill_runner.py codereview --input '{"prompt": "安全审计", "relevant_files": ["auth.py"], "review_type": "security"}'
```

## Parameters
- `prompt`: 审查要求描述
- `relevant_files`: 要审查的文件列表
- `review_type`: full / security / performance / quick
- `model`: 可选，指定模型

## Output
返回 JSON 格式的审查结果，包含：
- findings: 发现的问题列表（含严重级别）
- summary: 审查总结
- recommendations: 改进建议
```

#### 3) run-server.sh 新增函数
```bash
# 安装 Skills 到 ~/.claude/skills/
setup_skills_mode() {
    local script_dir=$(get_script_dir)
    local skills_source="$script_dir/skills"
    local skills_target="${CLAUDE_SKILLS_HOME:-$HOME/.claude/skills}"
    local runner_source="$script_dir/scripts/zen_skill_runner.py"

    # 检查源目录
    if [[ ! -d "$skills_source" ]]; then
        print_error "Skills source directory not found: $skills_source"
        return 1
    fi

    # 创建目标目录
    mkdir -p "$skills_target"

    # 安装每个技能
    local installed=0
    for skill_dir in "$skills_source"/zen-*/; do
        if [[ -d "$skill_dir" ]]; then
            local skill_name=$(basename "$skill_dir")
            local target_dir="$skills_target/$skill_name"

            # 复制技能目录
            rm -rf "$target_dir"
            cp -r "$skill_dir" "$target_dir"

            # 复制共享 runner 脚本
            mkdir -p "$target_dir/scripts"
            cp "$runner_source" "$target_dir/scripts/"

            print_success "Installed skill: $skill_name"
            ((installed++))
        fi
    done

    if [[ $installed -gt 0 ]]; then
        echo ""
        print_success "Installed $installed skills to $skills_target"
        echo "Skills are now available in Claude Code."
    else
        print_warning "No skills found to install"
    fi
}
```

### Phase 2: 技能内容

#### 需要创建的技能
| 技能名 | 对应工具 | 优先级 |
|--------|---------|--------|
| zen-chat | chat | 高 |
| zen-codereview | codereview | 高 |
| zen-debug | debug | 高 |
| zen-planner | planner | 高 |
| zen-consensus | consensus | 中 |
| zen-thinkdeep | thinkdeep | 中 |

### Phase 3: 集成与测试

#### run-server.sh 参数扩展
```bash
# 在 main() 中添加
case "$arg" in
    --skills)
        setup_skills_mode
        exit 0
        ;;
    --skills-only)
        setup_skills_mode
        exit 0
        ;;
esac
```

#### 用户使用流程
```bash
# 1. 运行安装脚本（同时配置 MCP 和 Skills）
./run-server.sh

# 2. 或仅安装 Skills
./run-server.sh --skills

# 3. Skills 自动可用于 Claude Code
# Claude 会根据 description 自动发现并使用
```

## 验收标准
- [x] `./run-server.sh` 保持现有 MCP 行为不变
- [ ] `./run-server.sh --skills` 安装技能到 `~/.claude/skills/`
- [ ] 每个技能目录结构正确（SKILL.md + scripts/）
- [ ] SKILL.md 格式符合规范（YAML frontmatter + Markdown）
- [ ] zen_skill_runner.py 可正确调用工具
- [ ] Claude Code 可发现并使用已安装的技能

## 安全考虑
- Skills 中不包含敏感信息（API keys 等）
- 使用 `allowed-tools` 限制权限
- runner 脚本仅调用已有工具，不执行任意代码
