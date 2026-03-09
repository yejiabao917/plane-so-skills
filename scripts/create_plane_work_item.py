import argparse
import html
import json
import os
import sys
from typing import Any

import requests

class PlaneClient:
    def __init__(self, workspace_slug: str | None = None) -> None:
        self.api_key = self._require_env("PLANE_API_KEY")
        self.base_url = self._require_env("PLANE_BASE_URL").rstrip("/")
        self.workspace_slug = workspace_slug or self._require_env("PLANE_WORKSPACE_SLUG")
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
            raise RuntimeError(f"Plane API error: {response.status_code} {detail}") from exc
        if not response.content:
            return None
        return response.json()

    def list_projects(self) -> list[dict[str, Any]]:
        data = self._request(
            "GET", f"/api/v1/workspaces/{self.workspace_slug}/projects/"
        )
        return data.get("results", [])

    def resolve_project(self, project_name: str | None) -> dict[str, Any]:
        projects = self.list_projects()
        if not projects:
            raise RuntimeError("No Plane projects found in workspace.")

        target_name = project_name or os.getenv("PLANE_DEFAULT_PROJECT_NAME")
        if target_name:
            for project in projects:
                if project["name"].lower() == target_name.lower():
                    return project

        if len(projects) == 1:
            return projects[0]

        available = ", ".join(project["name"] for project in projects)
        raise RuntimeError(
            "Project is not specified and cannot be resolved automatically. "
            f"Available projects: {available}"
        )

    def list_states(self, project_id: str) -> list[dict[str, Any]]:
        data = self._request(
            "GET",
            f"/api/v1/workspaces/{self.workspace_slug}/projects/{project_id}/states/",
        )
        return data.get("results", [])

    def resolve_state(self, project_id: str, state_name: str | None) -> str:
        states = self.list_states(project_id)
        if not states:
            raise RuntimeError("No Plane states found for project.")

        target_name = state_name or os.getenv("PLANE_DEFAULT_STATE")
        if target_name:
            for state in states:
                if state["name"].lower() == target_name.lower():
                    return state["id"]

        defaults = [state for state in states if state.get("default")]
        if defaults:
            return defaults[0]["id"]

        available = ", ".join(state["name"] for state in states)
        raise RuntimeError(
            "State is not specified and no default state could be resolved. "
            f"Available states: {available}"
        )

    def create_work_item(
        self,
        *,
        project_name: str | None,
        title: str,
        description_html: str | None,
        priority: str | None,
        state_name: str | None,
        start_date: str | None,
        target_date: str | None,
    ) -> dict[str, Any]:
        project = self.resolve_project(project_name)
        state_id = self.resolve_state(project["id"], state_name)

        payload: dict[str, Any] = {
            "name": title,
            "state": state_id,
        }
        if description_html:
            payload["description_html"] = description_html
        if priority:
            payload["priority"] = priority
        if start_date:
            payload["start_date"] = start_date
        if target_date:
            payload["target_date"] = target_date

        work_item = self._request(
            "POST",
            f"/api/v1/workspaces/{self.workspace_slug}/projects/{project['id']}/work-items/",
            data=json.dumps(payload),
        )
        return {
            "workspace_slug": self.workspace_slug,
            "project_name": project["name"],
            "state_id": state_id,
            "work_item": {
                "id": work_item["id"],
                "sequence_id": work_item.get("sequence_id"),
                "name": work_item["name"],
                "priority": work_item.get("priority"),
                "state": work_item.get("state"),
            },
        }


def _paragraph_html(text: str) -> str:
    escaped = html.escape(text).replace("\r\n", "\n").replace("\r", "\n")
    return "<p>" + escaped.replace("\n", "<br/>") + "</p>"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a Plane work item.")
    parser.add_argument("--workspace", help="Plane workspace slug")
    parser.add_argument("--project", help="Plane project name")
    parser.add_argument("--title", required=True, help="Work item title")
    parser.add_argument("--description", help="Plain-text description")
    parser.add_argument("--description-html", help="HTML description")
    parser.add_argument(
        "--priority",
        choices=["none", "low", "medium", "high", "urgent"],
        help="Work item priority",
    )
    parser.add_argument("--state", help="Plane state name")
    parser.add_argument("--start-date", help="Start date in YYYY-MM-DD")
    parser.add_argument("--target-date", help="Target date in YYYY-MM-DD")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    description_html = args.description_html
    if not description_html and args.description:
        description_html = _paragraph_html(args.description)

    client = PlaneClient(workspace_slug=args.workspace)
    result = client.create_work_item(
        project_name=args.project,
        title=args.title,
        description_html=description_html,
        priority=args.priority,
        state_name=args.state,
        start_date=args.start_date,
        target_date=args.target_date,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
