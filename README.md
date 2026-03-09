# plane-so-skills

`plane-so-skills` is a Codex skill for creating Plane work items from natural-language task details.

## Install

The installed local skill folder should be named `plane-so-skills`.

### macOS / Linux

```bash
git clone https://github.com/yejiabao917/plane-so-skills.git ~/.codex/skills/plane-so-skills
```

### Windows PowerShell

```powershell
git clone https://github.com/yejiabao917/plane-so-skills.git "$env:USERPROFILE\.codex\skills\plane-so-skills"
```

If you download a ZIP instead of cloning, extract it and rename the extracted folder to `plane-so-skills` before placing it under `$CODEX_HOME/skills/`.

## Required Environment Variables

Required:

- `PLANE_API_KEY`
- `PLANE_BASE_URL`
- `PLANE_WORKSPACE_SLUG`

Optional:

- `PLANE_DEFAULT_PROJECT_NAME`
- `PLANE_DEFAULT_STATE`

### macOS / Linux example

```bash
export PLANE_API_KEY="your_api_key"
export PLANE_BASE_URL="https://api.plane.so"
export PLANE_WORKSPACE_SLUG="your_workspace_slug"
export PLANE_DEFAULT_PROJECT_NAME="your_project_name"
export PLANE_DEFAULT_STATE="Backlog"
```

### Windows PowerShell example

```powershell
$env:PLANE_API_KEY="your_api_key"
$env:PLANE_BASE_URL="https://api.plane.so"
$env:PLANE_WORKSPACE_SLUG="your_workspace_slug"
$env:PLANE_DEFAULT_PROJECT_NAME="your_project_name"
$env:PLANE_DEFAULT_STATE="Backlog"
```

## What The Skill Does

- Creates Plane work items from plain-language requests
- Resolves project and state names through the Plane API
- Uses explicit user input first, then environment defaults
- Keeps follow-up questions to a minimum

## Example Requests

- `在 Plane 里创建一个 new work item，标题“修复登录白屏”`
- `建一个 bug，标题“Facebook 回传丢失”，描述“昨天开始部分转化没同步”，优先级 high`
- `在 workspace slug 是 abc-team 的 Plane 里建一个任务，项目是 Growth，标题“补齐埋点”`

## Repository Layout

- `SKILL.md`: skill instructions for Codex
- `agents/openai.yaml`: UI metadata
- `scripts/create_plane_work_item.py`: reusable Plane work item creation script

## Notes

- The script uses the official Plane `work-items` API.
- The repository is cross-platform and relies only on standard environment variables.
- The repository name, skill name, and recommended installed folder name are all `plane-so-skills`.
