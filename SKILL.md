---
name: plane-so-skills
description: Create Plane work items through the official Plane API. Use when a user asks to create a Plane task, bug, issue, or work item, especially when the request should be executed directly with minimal back-and-forth. Prefer explicit user-provided workspace, project, and state; otherwise resolve them from environment variables or unambiguous API results.
---

# Plane.so Skills

## Default Behavior

- Do not hardcode user-specific workspace, project, or state values in the skill.
- Prefer values explicitly provided by the user.
- Fall back to environment variables such as `PLANE_WORKSPACE_SLUG`, `PLANE_DEFAULT_PROJECT_NAME`, and `PLANE_DEFAULT_STATE` when available.
- If the workspace contains exactly one project and no project was specified, use that project.
- If the project exposes a default state and no state was specified, use that default state.
- Act directly when the user gives enough information to create the item.
- Ask follow-up questions only when the title is missing, the workspace or project cannot be resolved uniquely, or the API returns a permission or validation error.

## Workflow

1. Read `PLANE_API_KEY` and `PLANE_BASE_URL`. Read `PLANE_WORKSPACE_SLUG`, `PLANE_DEFAULT_PROJECT_NAME`, and `PLANE_DEFAULT_STATE` as optional fallbacks.
2. Prefer running [scripts/create_plane_work_item.py](./scripts/create_plane_work_item.py) instead of rewriting the Plane API call.
3. If the user does not specify a workspace, use `PLANE_WORKSPACE_SLUG`.
4. If the user does not specify a project, use `PLANE_DEFAULT_PROJECT_NAME` or the only project in the workspace.
5. If the user does not specify a state, use `PLANE_DEFAULT_STATE` or the project's default state.
6. Convert the user's description into simple HTML when only plain text is provided.
7. Return the created work item's title, workspace, project, state, `id`, and `sequence_id`.

## Environment Contract

- Require standard process environment variables. Do not depend on OS-specific registries or shell history.
- Required: `PLANE_API_KEY`
- Required: `PLANE_BASE_URL`
- Required unless the user explicitly provides a workspace: `PLANE_WORKSPACE_SLUG`
- Optional: `PLANE_DEFAULT_PROJECT_NAME`
- Optional: `PLANE_DEFAULT_STATE`
- Keep the skill portable across Windows, macOS, and Linux by relying only on standard environment variable access.

## Field Mapping

- 标题 / title -> `name`
- 描述 / description -> `description_html`
- 优先级 / priority -> `priority`
- 状态 / state -> resolve state name to Plane state id before create
- 开始日期 / start date -> `start_date`
- 截止日期 / target date -> `target_date`

## Execution Notes

- Use the official Plane `work-items` endpoint, not the deprecated `issues` endpoint.
- Resolve the state name from `/projects/{project_id}/states/` before creating the work item.
- Keep the interaction short. If the target is already resolvable, create the item instead of asking for confirmation.
- If the target workspace has exactly one project and no project default is configured, use the only available project and report that assumption.
- If the target cannot be resolved from the request, environment, or a single API result, ask one concise follow-up question.

## Examples

If the user says:

- `在 Plane 里创建一个 new work item，标题“修复登录白屏”`
- `建一个 bug，标题“Facebook 回传丢失”，描述“昨天开始部分转化没同步”，优先级 high`

Resolve them using:

- workspace: user input, otherwise `PLANE_WORKSPACE_SLUG`
- project: user input, otherwise `PLANE_DEFAULT_PROJECT_NAME` or the only project in the workspace
- state: user input, otherwise `PLANE_DEFAULT_STATE` or the project's default state

If the user says:

- `在 workspace slug 是 abc-team 的 Plane 里建一个任务，项目是 Growth，标题“补齐埋点”`

Override any environment defaults with the user-provided workspace and project.
