import json
import os
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.environ.get("MONDAY_API_TOKEN")
OUT_JSON = Path("docs/monday-graphql-schema.json")
OUT_MD = Path("docs/monday-graphql-schema-summary.md")

INTROSPECTION_QUERY = """
query IntrospectionQuery {
  __schema {
    queryType { name }
    mutationType { name }
    subscriptionType { name }
    types {
      kind
      name
      description
      fields(includeDeprecated: true) {
        name
        description
        isDeprecated
        deprecationReason
        args {
          name
          description
          defaultValue
          type {
            kind
            name
            ofType {
              kind
              name
              ofType {
                kind
                name
                ofType {
                  kind
                  name
                }
              }
            }
          }
        }
        type {
          kind
          name
          ofType {
            kind
            name
            ofType {
              kind
              name
              ofType {
                kind
                name
              }
            }
          }
        }
      }
      inputFields {
        name
        description
        defaultValue
        type {
          kind
          name
          ofType {
            kind
            name
            ofType {
              kind
              name
            }
          }
        }
      }
      enumValues(includeDeprecated: true) {
        name
        description
        isDeprecated
        deprecationReason
      }
    }
  }
}
"""


def type_to_str(t):
    if not t:
        return ""
    kind = t.get("kind")
    name = t.get("name")
    of_type = t.get("ofType")

    if kind == "NON_NULL":
        return f"{type_to_str(of_type)}!"
    if kind == "LIST":
        return f"[{type_to_str(of_type)}]"
    return name or kind or ""


def main():
    if not TOKEN:
        raise RuntimeError("MONDAY_API_TOKEN not set")

    headers = {
        "Authorization": TOKEN,
        "Content-Type": "application/json",
        "API-Version": "2025-04",
    }

    r = requests.post(
        "https://api.monday.com/v2",
        headers=headers,
        json={"query": INTROSPECTION_QUERY},
        timeout=60,
    )
    r.raise_for_status()
    payload = r.json()

    if "errors" in payload:
        raise RuntimeError(json.dumps(payload["errors"], indent=2))

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    schema = payload["data"]["__schema"]
    types = schema["types"]

    query_type = schema["queryType"]["name"]
    mutation_type = schema["mutationType"]["name"]

    by_name = {t["name"]: t for t in types if t.get("name")}

    lines = []
    lines.append("# monday.com GraphQL Schema Summary")
    lines.append("")
    lines.append("API version: 2025-04")
    lines.append("")

    for section_name, type_name in [("Queries", query_type), ("Mutations", mutation_type)]:
        lines.append(f"## {section_name}")
        lines.append("")

        t = by_name.get(type_name)
        if not t:
            continue

        for field in sorted(t.get("fields") or [], key=lambda f: f["name"]):
            args = field.get("args") or []
            arg_str = ", ".join(
                f'{a["name"]}: {type_to_str(a["type"])}'
                for a in args
            )
            return_type = type_to_str(field["type"])

            if arg_str:
                lines.append(f"### `{field['name']}({arg_str}): {return_type}`")
            else:
                lines.append(f"### `{field['name']}: {return_type}`")

            if field.get("description"):
                lines.append("")
                lines.append(field["description"].strip())

            if field.get("isDeprecated"):
                lines.append("")
                lines.append(f"Deprecated: {field.get('deprecationReason') or 'No reason given.'}")

            lines.append("")

    lines.append("## Object / Input / Enum Types")
    lines.append("")

    for t in sorted(types, key=lambda x: x.get("name") or ""):
        name = t.get("name")
        if not name or name.startswith("__"):
            continue

        kind = t.get("kind")
        lines.append(f"### `{name}` — {kind}")
        lines.append("")

        if t.get("description"):
            lines.append(t["description"].strip())
            lines.append("")

        fields = t.get("fields") or []
        input_fields = t.get("inputFields") or []
        enum_values = t.get("enumValues") or []

        if fields:
            lines.append("| Field | Type | Deprecated |")
            lines.append("|---|---|---|")
            for f in fields:
                dep = f.get("deprecationReason") if f.get("isDeprecated") else ""
                lines.append(f"| `{f['name']}` | `{type_to_str(f['type'])}` | {dep or ''} |")
            lines.append("")

        if input_fields:
            lines.append("| Input field | Type | Default |")
            lines.append("|---|---|---|")
            for f in input_fields:
                lines.append(
                    f"| `{f['name']}` | `{type_to_str(f['type'])}` | `{f.get('defaultValue') or ''}` |"
                )
            lines.append("")

        if enum_values:
            lines.append("| Enum value | Deprecated |")
            lines.append("|---|---|")
            for ev in enum_values:
                dep = ev.get("deprecationReason") if ev.get("isDeprecated") else ""
                lines.append(f"| `{ev['name']}` | {dep or ''} |")
            lines.append("")

    OUT_MD.write_text("\n".join(lines), encoding="utf-8")

    print(f"Wrote {OUT_JSON}")
    print(f"Wrote {OUT_MD}")


if __name__ == "__main__":
    main()