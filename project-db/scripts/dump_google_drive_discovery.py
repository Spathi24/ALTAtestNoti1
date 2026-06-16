import json
from pathlib import Path

import requests

DISCOVERY_URL = "https://www.googleapis.com/discovery/v1/apis/drive/v3/rest"

OUT_JSON = Path("docs/google-drive-v3-discovery.json")
OUT_MD = Path("docs/google-drive-v3-discovery-summary.md")


def method_title(resource_name: str, method_name: str) -> str:
    if resource_name:
        return f"{resource_name}.{method_name}"
    return method_name


def format_parameters(parameters: dict | None) -> list[str]:
    if not parameters:
        return []

    lines = []
    lines.append("| Parameter | Location | Type | Required | Description |")
    lines.append("|---|---|---|---|---|")

    for name, p in sorted(parameters.items()):
        location = p.get("location", "")
        typ = p.get("type", "")
        required = "yes" if p.get("required") else ""
        desc = (p.get("description") or "").replace("\n", " ").strip()
        lines.append(f"| `{name}` | `{location}` | `{typ}` | {required} | {desc} |")

    return lines


def walk_resources(resources: dict, prefix: str = ""):
    for resource_name, resource in sorted(resources.items()):
        full_name = f"{prefix}.{resource_name}" if prefix else resource_name

        for method_name, method in sorted((resource.get("methods") or {}).items()):
            yield full_name, method_name, method

        nested = resource.get("resources") or {}
        yield from walk_resources(nested, full_name)


def main() -> None:
    r = requests.get(
        DISCOVERY_URL,
        headers={
            "User-Agent": "project-db-local-doc-builder/0.1",
            "Accept": "application/json",
        },
        timeout=60,
    )
    r.raise_for_status()
    payload = r.json()

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    lines = []
    lines.append("# Google Drive API v3 Discovery Summary")
    lines.append("")
    lines.append(f"Discovery document: {DISCOVERY_URL}")
    lines.append("")
    lines.append(f"Title: {payload.get('title', '')}")
    lines.append(f"Version: {payload.get('version', '')}")
    lines.append(f"Root URL: {payload.get('rootUrl', '')}")
    lines.append(f"Service Path: {payload.get('servicePath', '')}")
    lines.append(f"Base URL: {payload.get('baseUrl', '')}")
    lines.append("")

    auth = payload.get("auth", {}).get("oauth2", {}).get("scopes", {})
    if auth:
        lines.append("## OAuth Scopes")
        lines.append("")
        lines.append("| Scope | Description |")
        lines.append("|---|---|")
        for scope, info in sorted(auth.items()):
            desc = (info.get("description") or "").replace("\n", " ").strip()
            lines.append(f"| `{scope}` | {desc} |")
        lines.append("")

    schemas = payload.get("schemas") or {}
    if schemas:
        lines.append("## Schemas")
        lines.append("")
        for schema_name, schema in sorted(schemas.items()):
            lines.append(f"### `{schema_name}`")
            lines.append("")
            if schema.get("description"):
                lines.append(schema["description"].strip())
                lines.append("")

            props = schema.get("properties") or {}
            if props:
                lines.append("| Property | Type | Description |")
                lines.append("|---|---|---|")
                for prop_name, prop in sorted(props.items()):
                    typ = prop.get("type") or prop.get("$ref") or ""
                    if prop.get("type") == "array":
                        item = prop.get("items", {})
                        typ = f"array[{item.get('type') or item.get('$ref') or ''}]"
                    desc = (prop.get("description") or "").replace("\n", " ").strip()
                    lines.append(f"| `{prop_name}` | `{typ}` | {desc} |")
                lines.append("")

    resources = payload.get("resources") or {}
    if resources:
        lines.append("## Methods")
        lines.append("")

        for resource_name, method_name, method in walk_resources(resources):
            title = method_title(resource_name, method_name)
            http_method = method.get("httpMethod", "")
            path = method.get("path", "")
            desc = (method.get("description") or "").strip()

            lines.append(f"### `{title}`")
            lines.append("")
            lines.append(f"`{http_method} /{path}`")
            lines.append("")

            if desc:
                lines.append(desc)
                lines.append("")

            params = format_parameters(method.get("parameters"))
            if params:
                lines.extend(params)
                lines.append("")

            request = method.get("request", {})
            response = method.get("response", {})

            if request.get("$ref"):
                lines.append(f"Request body: `{request['$ref']}`")
                lines.append("")

            if response.get("$ref"):
                lines.append(f"Response body: `{response['$ref']}`")
                lines.append("")

            scopes = method.get("scopes") or []
            if scopes:
                lines.append("Scopes:")
                for scope in scopes:
                    lines.append(f"- `{scope}`")
                lines.append("")

    OUT_MD.write_text("\n".join(lines), encoding="utf-8")

    print(f"Wrote {OUT_JSON}")
    print(f"Wrote {OUT_MD}")


if __name__ == "__main__":
    main()
