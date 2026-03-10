# plane-so-skills

`plane-so-skills` is a Codex skill for operating Plane work items through the official Plane API.

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

## Required Environment Variables

Required:

- `PLANE_API_KEY`
- `PLANE_BASE_URL`
- `PLANE_WORKSPACE_SLUG`

Optional:

- `PLANE_DEFAULT_PROJECT_NAME`
- `PLANE_DEFAULT_STATE`

## Supported Operations

- Create a work item
- List work items
- Get one work item
- Update a work item
- Delete a work item
- List project members
- List labels
- Create a label
- Delete a label
- List comments
- Add a comment
- Update a comment
- Delete a comment

## Command Examples

Create a work item:

```bash
python scripts/plane_so_skills.py create \
  --title "Fix login white screen" \
  --description "Reproducible on iOS Safari." \
  --priority high \
  --state Backlog
```

List backlog items:

```bash
python scripts/plane_so_skills.py list --state Backlog --limit 10
```

Get one item by sequence id:

```bash
python scripts/plane_so_skills.py get --item 591
```

Update state and labels:

```bash
python scripts/plane_so_skills.py update \
  --item 591 \
  --state "In Progress" \
  --add-label frontend
```

Add a comment:

```bash
python scripts/plane_so_skills.py add-comment \
  --item 591 \
  --comment "Validated on staging."
```

List project members:

```bash
python scripts/plane_so_skills.py list-members
```

Create a label:

```bash
python scripts/plane_so_skills.py create-label --name bug --color "#ef4444"
```

## Reference Rules

- `--item` accepts a UUID, identifier, sequence id, or exact title.
- `--project` accepts a project name, id, or identifier.
- `--state` accepts a state name or id.
- `--assignee` accepts a member id, email, display name, or full name.
- `--label` accepts a label id or name.
- On update, `--assignee` and `--label` replace the full list.
- On update, `--add-*` and `--remove-*` merge with the current item state.

## Task Display Rules

- Show Plane task content as original plain text instead of raw HTML when the user asks to read a task.
- Preserve image positions with placeholders like `[图片1]`, `[图片2]`, and `[图片3]`.
- Do not rewrite or summarize the original task content unless the user explicitly asks.
- After extracting task images locally, open the corresponding image folder for the user.

## Repository Layout

- `SKILL.md`: skill instructions for Codex
- `agents/openai.yaml`: UI metadata
- `scripts/plane_so_skills.py`: reusable Plane CLI for work item operations
