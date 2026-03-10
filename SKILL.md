---
name: plane-so-skills
description: Operate Plane projects through the official Plane API. Use when a user asks to create, list, inspect, update, comment on, label, assign, or delete Plane work items, especially when the request should be executed directly with minimal back-and-forth.
---

# Plane.so Skills

## Default Behavior

- Prefer explicit user-provided workspace, project, state, item, assignee, and label references.
- Fall back to `PLANE_WORKSPACE_SLUG`, `PLANE_DEFAULT_PROJECT_NAME`, and `PLANE_DEFAULT_STATE` when available.
- If the workspace contains exactly one project and no project was specified, use that project.
- If the project has a default state and no state was specified, use that default state.
- Act directly when the target can be resolved unambiguously.
- Ask follow-up questions only when the target project or item cannot be resolved, or the API returns a validation or permission error.

## Workflow

1. Read `PLANE_API_KEY` and `PLANE_BASE_URL`. Read workspace and default project or state from environment only as fallbacks.
2. Prefer running [scripts/plane_so_skills.py](./scripts/plane_so_skills.py) instead of rewriting Plane API calls.
3. Resolve project, state, work item, member, and label references before mutating data.
4. Convert plain-text descriptions and comments into simple HTML when HTML is not provided.
5. Return concrete API results: created item, updated item, deleted item, labels, members, or comments.

## Supported Operations

- Create a work item
- List work items
- Get one work item by UUID, identifier, sequence id, or exact title
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

## Command Mapping

- Create item -> `create`
- List items -> `list`
- Inspect item -> `get`
- Update item -> `update`
- Delete item -> `delete`
- List members -> `list-members`
- List labels -> `list-labels`
- Create label -> `create-label`
- Delete label -> `delete-label`
- List comments -> `list-comments`
- Add comment -> `add-comment`
- Update comment -> `update-comment`
- Delete comment -> `delete-comment`

## Field Mapping

- 标题 / title -> `name`
- 描述 / description -> `description_html`
- 优先级 / priority -> `priority`
- 状态 / state -> resolve state name to Plane state id before create or update
- 负责人 / assignee -> resolve member id before create or update
- 标签 / label -> resolve label id before create or update
- 开始日期 / start date -> `start_date`
- 截止日期 / target date -> `target_date`
- 评论 / comment -> `comment_html`

## Execution Notes

- Use the official Plane `work-items` endpoint, not the deprecated `issues` endpoint.
- Resolve state names from `/projects/{project_id}/states/`.
- Resolve assignees from `/projects/{project_id}/members/`.
- Resolve labels from `/projects/{project_id}/labels/`.
- Treat `--assignee` and `--label` as replacement lists on update.
- Treat `--add-assignee`, `--remove-assignee`, `--add-label`, and `--remove-label` as merge operations on update.
- Keep the interaction short. If the target is already resolvable, execute the change instead of asking for confirmation.

## Display Format

- When the user asks to view a Plane task's content, present the body as original plain text, not HTML.
- Do not rewrite, summarize, or normalize the task content unless the user explicitly asks for that.
- If the task body contains embedded images, preserve their original positions with placeholders like `[图片1]`, `[图片2]`, and `[图片3]`.
- After presenting the task body, open the corresponding downloaded image folder for the user when images were extracted locally.

## Environment Contract

- Required: `PLANE_API_KEY`
- Required: `PLANE_BASE_URL`
- Required unless the user explicitly provides a workspace: `PLANE_WORKSPACE_SLUG`
- Optional: `PLANE_DEFAULT_PROJECT_NAME`
- Optional: `PLANE_DEFAULT_STATE`

## Examples

If the user says:

- `在 Plane 里创建一个 new work item，标题“修复登录白屏”`
- `把 CW-591 改成 In Progress，并加上标签 前端`
- `给 CW-591 加评论：“已在 staging 复现”`
- `查一下这个项目最近 10 条 backlog 任务`

Map them to the matching subcommands and execute directly when the target can be resolved.
