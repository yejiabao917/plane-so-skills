import argparse
import html
import json
import os
import re
import sys
from typing import Any

import requests


UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
IDENTIFIER_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*-\d+$")
PRIORITY_CHOICES = ["none", "low", "medium", "high", "urgent"]


def _normalize(value: str | None) -> str:
    return (value or "").strip().lower()


def _is_uuid(value: str) -> bool:
    return bool(UUID_RE.fullmatch(value.strip()))


def _is_identifier(value: str) -> bool:
    return bool(IDENTIFIER_RE.fullmatch(value.strip()))


def _full_name(member: dict[str, Any]) -> str:
    return " ".join(
        part for part in [member.get("first_name"), member.get("last_name")] if part
    ).strip()


def _paragraph_html(text: str) -> str:
    escaped = html.escape(text).replace("\r\n", "\n").replace("\r", "\n")
    return "<p>" + escaped.replace("\n", "<br/>") + "</p>"


def _resolve_html_input(
    plain_text: str | None, html_text: str | None, field_name: str
) -> str | None:
    if html_text:
        return html_text
    if plain_text:
        return _paragraph_html(plain_text)
    if field_name == "comment":
        return None
    return None


def _coerce_results(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        results = data.get("results")
        if isinstance(results, list):
            return [item for item in results if isinstance(item, dict)]
    return []


def _item_summary(item: dict[str, Any]) -> dict[str, Any]:
    state = item.get("state")
    if isinstance(state, dict):
        state = state.get("name") or state.get("id")

    project = item.get("project")
    if isinstance(project, dict):
        project = project.get("name") or project.get("identifier") or project.get("id")

    labels = []
    for label in item.get("labels", []):
        if isinstance(label, dict):
            labels.append(label.get("name") or label.get("id"))
        else:
            labels.append(label)

    assignees = []
    for assignee in item.get("assignees", []):
        if isinstance(assignee, dict):
            assignees.append(
                assignee.get("display_name")
                or assignee.get("email")
                or assignee.get("id")
            )
        else:
            assignees.append(assignee)

    return {
        "id": item.get("id"),
        "sequence_id": item.get("sequence_id"),
        "name": item.get("name"),
        "priority": item.get("priority"),
        "state": state,
        "project": project,
        "assignees": assignees,
        "labels": labels,
        "start_date": item.get("start_date"),
        "target_date": item.get("target_date"),
    }


class PlaneClient:
    def __init__(self, workspace_slug: str | None = None) -> None:
        self.api_key = self._require_env("PLANE_API_KEY")
        self.base_url = self._require_env("PLANE_BASE_URL").rstrip("/")
        self.workspace_slug = workspace_slug or self._require_env("PLANE_WORKSPACE_SLUG")
        self.default_project_name = os.getenv("PLANE_DEFAULT_PROJECT_NAME")
        self.default_state_name = os.getenv("PLANE_DEFAULT_STATE")
        self.session = requests.Session()
        self.session.headers.update(
            {
                "X-API-Key": self.api_key,
                "Content-Type": "application/json",
            }
        )

    @staticmethod
    def _require_env(name: str) -> str:
        value = os.getenv(name) or os.environ.get(name)
        if value:
            return value
        raise RuntimeError(f"Missing required environment variable: {name}")

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        response = self.session.request(
            method, f"{self.base_url}{path}", timeout=30, **kwargs
        )
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            detail = response.text.strip()
            raise RuntimeError(
                f"Plane API error: {response.status_code} {detail}"
            ) from exc
        if not response.content:
            return None
        return response.json()

    def list_projects(self) -> list[dict[str, Any]]:
        data = self._request(
            "GET",
            f"/api/v1/workspaces/{self.workspace_slug}/projects/",
        )
        return _coerce_results(data)

    def resolve_project(self, project_ref: str | None) -> dict[str, Any]:
        projects = self.list_projects()
        if not projects:
            raise RuntimeError("No Plane projects found in workspace.")

        target_ref = (project_ref or self.default_project_name or "").strip()
        if target_ref:
            normalized = _normalize(target_ref)
            for project in projects:
                if (
                    _normalize(project.get("id")) == normalized
                    or _normalize(project.get("name")) == normalized
                    or _normalize(project.get("identifier")) == normalized
                ):
                    return project
            available = ", ".join(
                project.get("name") or project.get("id") for project in projects
            )
            raise RuntimeError(
                f"Project '{target_ref}' not found. Available projects: {available}"
            )

        if len(projects) == 1:
            return projects[0]

        available = ", ".join(
            project.get("name") or project.get("id") for project in projects
        )
        raise RuntimeError(
            "Project is not specified and cannot be resolved automatically. "
            f"Available projects: {available}"
        )

    def list_states(self, project_id: str) -> list[dict[str, Any]]:
        data = self._request(
            "GET",
            f"/api/v1/workspaces/{self.workspace_slug}/projects/{project_id}/states/",
        )
        return _coerce_results(data)

    def resolve_state(self, project_id: str, state_ref: str | None) -> str:
        states = self.list_states(project_id)
        if not states:
            raise RuntimeError("No Plane states found for project.")

        target_ref = (state_ref or self.default_state_name or "").strip()
        if target_ref:
            normalized = _normalize(target_ref)
            for state in states:
                if (
                    _normalize(state.get("id")) == normalized
                    or _normalize(state.get("name")) == normalized
                ):
                    return state["id"]
            available = ", ".join(state.get("name") or state.get("id") for state in states)
            raise RuntimeError(
                f"State '{target_ref}' not found. Available states: {available}"
            )

        for state in states:
            if state.get("default"):
                return state["id"]

        available = ", ".join(state.get("name") or state.get("id") for state in states)
        raise RuntimeError(
            "State is not specified and no default state could be resolved. "
            f"Available states: {available}"
        )

    def list_project_members(self, project_id: str) -> list[dict[str, Any]]:
        data = self._request(
            "GET",
            f"/api/v1/workspaces/{self.workspace_slug}/projects/{project_id}/members/",
        )
        return _coerce_results(data)

    def resolve_member(self, project_id: str, member_ref: str) -> str:
        members = self.list_project_members(project_id)
        normalized = _normalize(member_ref)
        for member in members:
            if _normalize(member.get("id")) == normalized:
                return member["id"]
            if _normalize(member.get("email")) == normalized:
                return member["id"]
            if _normalize(member.get("display_name")) == normalized:
                return member["id"]
            if _normalize(_full_name(member)) == normalized:
                return member["id"]
        available = ", ".join(
            member.get("display_name") or member.get("email") or member.get("id")
            for member in members
        )
        raise RuntimeError(
            f"Member '{member_ref}' not found. Available members: {available}"
        )

    def list_labels(self, project_id: str) -> list[dict[str, Any]]:
        data = self._request(
            "GET",
            f"/api/v1/workspaces/{self.workspace_slug}/projects/{project_id}/labels/",
        )
        return _coerce_results(data)

    def resolve_label(self, project_id: str, label_ref: str) -> str:
        labels = self.list_labels(project_id)
        normalized = _normalize(label_ref)
        for label in labels:
            if _normalize(label.get("id")) == normalized:
                return label["id"]
            if _normalize(label.get("name")) == normalized:
                return label["id"]
        available = ", ".join(label.get("name") or label.get("id") for label in labels)
        raise RuntimeError(
            f"Label '{label_ref}' not found. Available labels: {available}"
        )

    def list_work_items(
        self,
        project: dict[str, Any],
        *,
        state_ref: str | None = None,
        assignee_ref: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"limit": limit, "expand": "state,labels,assignees,project"}
        if state_ref:
            params["state"] = self.resolve_state(project["id"], state_ref)
        if assignee_ref:
            params["assignee"] = self.resolve_member(project["id"], assignee_ref)

        data = self._request(
            "GET",
            f"/api/v1/workspaces/{self.workspace_slug}/projects/{project['id']}/work-items/",
            params=params,
        )
        items = _coerce_results(data)
        if limit > 0:
            return items[:limit]
        return items

    def get_work_item_by_id(self, project_id: str, item_id: str) -> dict[str, Any]:
        return self._request(
            "GET",
            f"/api/v1/workspaces/{self.workspace_slug}/projects/{project_id}/work-items/{item_id}/",
            params={"expand": "state,labels,assignees,project"},
        )

    def get_work_item_by_identifier(self, identifier: str) -> dict[str, Any]:
        return self._request(
            "GET",
            f"/api/v1/workspaces/{self.workspace_slug}/work-items/{identifier}/",
            params={"expand": "state,labels,assignees,project"},
        )

    def resolve_work_item(
        self,
        project: dict[str, Any],
        item_ref: str,
    ) -> dict[str, Any]:
        item_ref = item_ref.strip()
        if _is_uuid(item_ref):
            return self.get_work_item_by_id(project["id"], item_ref)

        identifier = item_ref
        if item_ref.isdigit():
            project_identifier = project.get("identifier")
            if not project_identifier:
                raise RuntimeError(
                    "Project identifier is unavailable, cannot resolve numeric item reference."
                )
            identifier = f"{project_identifier}-{item_ref}"

        if _is_identifier(identifier):
            item = self.get_work_item_by_identifier(identifier)
            item_project = item.get("project")
            item_project_id = item_project.get("id") if isinstance(item_project, dict) else item_project
            if item_project_id and item_project_id != project["id"]:
                raise RuntimeError(
                    f"Work item '{identifier}' does not belong to project '{project['name']}'."
                )
            return item

        target_name = _normalize(item_ref)
        items = self.list_work_items(project, limit=100)
        matches = [item for item in items if _normalize(item.get("name")) == target_name]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise RuntimeError(
                f"Multiple work items named '{item_ref}' were found. Use UUID or sequence id."
            )
        raise RuntimeError(
            f"Work item '{item_ref}' not found in project '{project['name']}'."
        )

    def create_work_item(
        self,
        *,
        project_name: str | None,
        title: str,
        description_html: str | None,
        priority: str | None,
        state_name: str | None,
        assignee_refs: list[str] | None,
        label_refs: list[str] | None,
        start_date: str | None,
        target_date: str | None,
    ) -> dict[str, Any]:
        project = self.resolve_project(project_name)
        payload: dict[str, Any] = {
            "name": title,
            "state": self.resolve_state(project["id"], state_name),
        }
        if description_html:
            payload["description_html"] = description_html
        if priority:
            payload["priority"] = priority
        if assignee_refs:
            payload["assignees"] = [
                self.resolve_member(project["id"], assignee_ref)
                for assignee_ref in assignee_refs
            ]
        if label_refs:
            payload["labels"] = [
                self.resolve_label(project["id"], label_ref) for label_ref in label_refs
            ]
        if start_date:
            payload["start_date"] = start_date
        if target_date:
            payload["target_date"] = target_date

        work_item = self._request(
            "POST",
            f"/api/v1/workspaces/{self.workspace_slug}/projects/{project['id']}/work-items/",
            json=payload,
        )
        return {
            "workspace_slug": self.workspace_slug,
            "project_name": project["name"],
            "payload": payload,
            "work_item": _item_summary(work_item),
        }

    def update_work_item(
        self,
        *,
        project_name: str | None,
        item_ref: str,
        title: str | None,
        description_html: str | None,
        priority: str | None,
        state_name: str | None,
        assignee_refs: list[str] | None,
        label_refs: list[str] | None,
        add_assignee_refs: list[str] | None,
        remove_assignee_refs: list[str] | None,
        add_label_refs: list[str] | None,
        remove_label_refs: list[str] | None,
        start_date: str | None,
        target_date: str | None,
    ) -> dict[str, Any]:
        project = self.resolve_project(project_name)
        item = self.resolve_work_item(project, item_ref)
        payload: dict[str, Any] = {}

        if title:
            payload["name"] = title
        if description_html:
            payload["description_html"] = description_html
        if priority:
            payload["priority"] = priority
        if state_name:
            payload["state"] = self.resolve_state(project["id"], state_name)
        if start_date:
            payload["start_date"] = start_date
        if target_date:
            payload["target_date"] = target_date

        if assignee_refs is not None:
            payload["assignees"] = [
                self.resolve_member(project["id"], assignee_ref)
                for assignee_ref in assignee_refs
            ]
        elif add_assignee_refs or remove_assignee_refs:
            current_ids = {
                assignee.get("id") if isinstance(assignee, dict) else assignee
                for assignee in item.get("assignees", [])
            }
            for assignee_ref in add_assignee_refs or []:
                current_ids.add(self.resolve_member(project["id"], assignee_ref))
            for assignee_ref in remove_assignee_refs or []:
                current_ids.discard(self.resolve_member(project["id"], assignee_ref))
            payload["assignees"] = sorted(current_ids)

        if label_refs is not None:
            payload["labels"] = [
                self.resolve_label(project["id"], label_ref) for label_ref in label_refs
            ]
        elif add_label_refs or remove_label_refs:
            current_ids = {
                label.get("id") if isinstance(label, dict) else label
                for label in item.get("labels", [])
            }
            for label_ref in add_label_refs or []:
                current_ids.add(self.resolve_label(project["id"], label_ref))
            for label_ref in remove_label_refs or []:
                current_ids.discard(self.resolve_label(project["id"], label_ref))
            payload["labels"] = sorted(current_ids)

        if not payload:
            raise RuntimeError("No update fields were provided.")

        updated = self._request(
            "PATCH",
            f"/api/v1/workspaces/{self.workspace_slug}/projects/{project['id']}/work-items/{item['id']}/",
            json=payload,
        )
        return {
            "workspace_slug": self.workspace_slug,
            "project_name": project["name"],
            "payload": payload,
            "work_item": _item_summary(updated),
        }

    def delete_work_item(
        self,
        *,
        project_name: str | None,
        item_ref: str,
    ) -> dict[str, Any]:
        project = self.resolve_project(project_name)
        item = self.resolve_work_item(project, item_ref)
        self._request(
            "DELETE",
            f"/api/v1/workspaces/{self.workspace_slug}/projects/{project['id']}/work-items/{item['id']}/",
        )
        return {
            "workspace_slug": self.workspace_slug,
            "project_name": project["name"],
            "deleted": True,
            "work_item": _item_summary(item),
        }

    def create_label(
        self,
        project_id: str,
        name: str,
        color: str | None,
        description: str | None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"name": name}
        if color:
            payload["color"] = color
        if description:
            payload["description"] = description
        return self._request(
            "POST",
            f"/api/v1/workspaces/{self.workspace_slug}/projects/{project_id}/labels/",
            json=payload,
        )

    def delete_label(self, project_id: str, label_ref: str) -> dict[str, Any]:
        label_id = self.resolve_label(project_id, label_ref)
        self._request(
            "DELETE",
            f"/api/v1/workspaces/{self.workspace_slug}/projects/{project_id}/labels/{label_id}",
        )
        return {"deleted": True, "label_id": label_id}

    def list_comments(self, project_id: str, work_item_id: str) -> list[dict[str, Any]]:
        data = self._request(
            "GET",
            f"/api/v1/workspaces/{self.workspace_slug}/projects/{project_id}/work-items/{work_item_id}/comments/",
            params={"limit": 100},
        )
        return _coerce_results(data)

    def add_comment(
        self,
        project_id: str,
        work_item_id: str,
        comment_html: str,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/api/v1/workspaces/{self.workspace_slug}/projects/{project_id}/work-items/{work_item_id}/comments/",
            json={"comment_html": comment_html},
        )

    def update_comment(
        self,
        project_id: str,
        work_item_id: str,
        comment_id: str,
        comment_html: str,
    ) -> dict[str, Any]:
        return self._request(
            "PATCH",
            f"/api/v1/workspaces/{self.workspace_slug}/projects/{project_id}/work-items/{work_item_id}/comments/{comment_id}/",
            json={"comment_html": comment_html},
        )

    def delete_comment(
        self,
        project_id: str,
        work_item_id: str,
        comment_id: str,
    ) -> dict[str, Any]:
        self._request(
            "DELETE",
            f"/api/v1/workspaces/{self.workspace_slug}/projects/{project_id}/work-items/{work_item_id}/comments/{comment_id}/",
        )
        return {"deleted": True, "comment_id": comment_id}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Operate Plane work items.")
    parser.add_argument("--workspace", help="Plane workspace slug")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_parser = subparsers.add_parser("create", help="Create a work item")
    create_parser.add_argument("--project", help="Plane project name or id")
    create_parser.add_argument("--title", required=True, help="Work item title")
    create_parser.add_argument("--description", help="Plain-text description")
    create_parser.add_argument("--description-html", help="HTML description")
    create_parser.add_argument("--priority", choices=PRIORITY_CHOICES)
    create_parser.add_argument("--state", help="State name or id")
    create_parser.add_argument("--assignee", action="append", default=[])
    create_parser.add_argument("--label", action="append", default=[])
    create_parser.add_argument("--start-date", help="Start date in YYYY-MM-DD")
    create_parser.add_argument("--target-date", help="Target date in YYYY-MM-DD")

    list_parser = subparsers.add_parser("list", help="List work items")
    list_parser.add_argument("--project", help="Plane project name or id")
    list_parser.add_argument("--state", help="Filter by state")
    list_parser.add_argument("--assignee", help="Filter by assignee")
    list_parser.add_argument("--limit", type=int, default=20)

    get_parser = subparsers.add_parser("get", help="Get one work item")
    get_parser.add_argument("--project", help="Plane project name or id")
    get_parser.add_argument(
        "--item", required=True, help="UUID, identifier, sequence id, or exact title"
    )

    update_parser = subparsers.add_parser("update", help="Update a work item")
    update_parser.add_argument("--project", help="Plane project name or id")
    update_parser.add_argument(
        "--item", required=True, help="UUID, identifier, sequence id, or exact title"
    )
    update_parser.add_argument("--title", help="Updated title")
    update_parser.add_argument("--description", help="Plain-text description")
    update_parser.add_argument("--description-html", help="HTML description")
    update_parser.add_argument("--priority", choices=PRIORITY_CHOICES)
    update_parser.add_argument("--state", help="State name or id")
    update_parser.add_argument("--assignee", action="append")
    update_parser.add_argument("--label", action="append")
    update_parser.add_argument("--add-assignee", action="append", default=[])
    update_parser.add_argument("--remove-assignee", action="append", default=[])
    update_parser.add_argument("--add-label", action="append", default=[])
    update_parser.add_argument("--remove-label", action="append", default=[])
    update_parser.add_argument("--start-date", help="Start date in YYYY-MM-DD")
    update_parser.add_argument("--target-date", help="Target date in YYYY-MM-DD")

    delete_parser = subparsers.add_parser("delete", help="Delete a work item")
    delete_parser.add_argument("--project", help="Plane project name or id")
    delete_parser.add_argument(
        "--item", required=True, help="UUID, identifier, sequence id, or exact title"
    )

    members_parser = subparsers.add_parser("list-members", help="List project members")
    members_parser.add_argument("--project", help="Plane project name or id")

    labels_parser = subparsers.add_parser("list-labels", help="List project labels")
    labels_parser.add_argument("--project", help="Plane project name or id")

    create_label_parser = subparsers.add_parser("create-label", help="Create a label")
    create_label_parser.add_argument("--project", help="Plane project name or id")
    create_label_parser.add_argument("--name", required=True, help="Label name")
    create_label_parser.add_argument("--color", help="Hex color")
    create_label_parser.add_argument("--description", help="Label description")

    delete_label_parser = subparsers.add_parser("delete-label", help="Delete a label")
    delete_label_parser.add_argument("--project", help="Plane project name or id")
    delete_label_parser.add_argument("--label", required=True, help="Label id or name")

    list_comments_parser = subparsers.add_parser(
        "list-comments", help="List work item comments"
    )
    list_comments_parser.add_argument("--project", help="Plane project name or id")
    list_comments_parser.add_argument("--item", required=True, help="Work item reference")

    add_comment_parser = subparsers.add_parser("add-comment", help="Add a comment")
    add_comment_parser.add_argument("--project", help="Plane project name or id")
    add_comment_parser.add_argument("--item", required=True, help="Work item reference")
    add_comment_parser.add_argument("--comment", help="Plain-text comment")
    add_comment_parser.add_argument("--comment-html", help="HTML comment")

    update_comment_parser = subparsers.add_parser(
        "update-comment", help="Update a comment"
    )
    update_comment_parser.add_argument("--project", help="Plane project name or id")
    update_comment_parser.add_argument("--item", required=True, help="Work item reference")
    update_comment_parser.add_argument("--comment-id", required=True, help="Comment id")
    update_comment_parser.add_argument("--comment", help="Plain-text comment")
    update_comment_parser.add_argument("--comment-html", help="HTML comment")

    delete_comment_parser = subparsers.add_parser(
        "delete-comment", help="Delete a comment"
    )
    delete_comment_parser.add_argument("--project", help="Plane project name or id")
    delete_comment_parser.add_argument("--item", required=True, help="Work item reference")
    delete_comment_parser.add_argument("--comment-id", required=True, help="Comment id")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    client = PlaneClient(workspace_slug=args.workspace)

    if args.command == "create":
        description_html = _resolve_html_input(
            args.description, args.description_html, "description"
        )
        result = client.create_work_item(
            project_name=args.project,
            title=args.title,
            description_html=description_html,
            priority=args.priority,
            state_name=args.state,
            assignee_refs=args.assignee,
            label_refs=args.label,
            start_date=args.start_date,
            target_date=args.target_date,
        )
    elif args.command == "list":
        project = client.resolve_project(args.project)
        items = client.list_work_items(
            project,
            state_ref=args.state,
            assignee_ref=args.assignee,
            limit=args.limit,
        )
        result = {
            "workspace_slug": client.workspace_slug,
            "project_name": project["name"],
            "count": len(items),
            "items": [_item_summary(item) for item in items],
        }
    elif args.command == "get":
        project = client.resolve_project(args.project)
        item = client.resolve_work_item(project, args.item)
        result = {
            "workspace_slug": client.workspace_slug,
            "project_name": project["name"],
            "work_item": item,
        }
    elif args.command == "update":
        description_html = _resolve_html_input(
            args.description, args.description_html, "description"
        )
        result = client.update_work_item(
            project_name=args.project,
            item_ref=args.item,
            title=args.title,
            description_html=description_html,
            priority=args.priority,
            state_name=args.state,
            assignee_refs=args.assignee,
            label_refs=args.label,
            add_assignee_refs=args.add_assignee,
            remove_assignee_refs=args.remove_assignee,
            add_label_refs=args.add_label,
            remove_label_refs=args.remove_label,
            start_date=args.start_date,
            target_date=args.target_date,
        )
    elif args.command == "delete":
        result = client.delete_work_item(
            project_name=args.project,
            item_ref=args.item,
        )
    elif args.command == "list-members":
        project = client.resolve_project(args.project)
        members = client.list_project_members(project["id"])
        result = {
            "workspace_slug": client.workspace_slug,
            "project_name": project["name"],
            "count": len(members),
            "members": members,
        }
    elif args.command == "list-labels":
        project = client.resolve_project(args.project)
        labels = client.list_labels(project["id"])
        result = {
            "workspace_slug": client.workspace_slug,
            "project_name": project["name"],
            "count": len(labels),
            "labels": labels,
        }
    elif args.command == "create-label":
        project = client.resolve_project(args.project)
        label = client.create_label(project["id"], args.name, args.color, args.description)
        result = {
            "workspace_slug": client.workspace_slug,
            "project_name": project["name"],
            "label": label,
        }
    elif args.command == "delete-label":
        project = client.resolve_project(args.project)
        deleted = client.delete_label(project["id"], args.label)
        result = {
            "workspace_slug": client.workspace_slug,
            "project_name": project["name"],
            **deleted,
        }
    elif args.command == "list-comments":
        project = client.resolve_project(args.project)
        item = client.resolve_work_item(project, args.item)
        comments = client.list_comments(project["id"], item["id"])
        result = {
            "workspace_slug": client.workspace_slug,
            "project_name": project["name"],
            "work_item": _item_summary(item),
            "count": len(comments),
            "comments": comments,
        }
    elif args.command == "add-comment":
        comment_html = _resolve_html_input(args.comment, args.comment_html, "comment")
        if comment_html is None:
            raise RuntimeError("Comment content is required.")
        project = client.resolve_project(args.project)
        item = client.resolve_work_item(project, args.item)
        comment = client.add_comment(project["id"], item["id"], comment_html)
        result = {
            "workspace_slug": client.workspace_slug,
            "project_name": project["name"],
            "work_item": _item_summary(item),
            "comment": comment,
        }
    elif args.command == "update-comment":
        comment_html = _resolve_html_input(args.comment, args.comment_html, "comment")
        if comment_html is None:
            raise RuntimeError("Comment content is required.")
        project = client.resolve_project(args.project)
        item = client.resolve_work_item(project, args.item)
        comment = client.update_comment(
            project["id"], item["id"], args.comment_id, comment_html
        )
        result = {
            "workspace_slug": client.workspace_slug,
            "project_name": project["name"],
            "work_item": _item_summary(item),
            "comment": comment,
        }
    elif args.command == "delete-comment":
        project = client.resolve_project(args.project)
        item = client.resolve_work_item(project, args.item)
        deleted = client.delete_comment(project["id"], item["id"], args.comment_id)
        result = {
            "workspace_slug": client.workspace_slug,
            "project_name": project["name"],
            "work_item": _item_summary(item),
            **deleted,
        }
    else:
        raise RuntimeError(f"Unsupported command: {args.command}")

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
