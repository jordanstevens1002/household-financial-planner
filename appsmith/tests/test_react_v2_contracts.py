"""Regression tests for the React migration architecture contracts."""

import ast
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[2]
ARCHITECTURE = ROOT / "docs" / "react-v2-architecture.md"
PARITY = ROOT / "docs" / "react-v2-api-parity.md"
ROUTE_ROW = re.compile(
    r"^\| (GET|POST|PUT|PATCH|DELETE) \| `([^`]+)` \|",
    re.MULTILINE,
)


def application_routes() -> set[tuple[str, str]]:
    """Read literal FastAPI decorator routes without importing the application."""
    routes: set[tuple[str, str]] = set()
    sources = sorted((ROOT / "api" / "app").glob("*/router.py"))
    sources.append(ROOT / "api" / "app" / "main.py")

    for source in sources:
        tree = ast.parse(source.read_text(encoding="utf-8"))
        prefix = "" if source.name == "main.py" else "/api/v1"
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for decorator in node.decorator_list:
                if (
                    not isinstance(decorator, ast.Call)
                    or not isinstance(decorator.func, ast.Attribute)
                    or decorator.func.attr
                    not in {"get", "post", "put", "patch", "delete"}
                    or not decorator.args
                ):
                    continue
                route = ast.literal_eval(decorator.args[0])
                routes.add((decorator.func.attr.upper(), f"{prefix}{route}"))
    return routes


class ReactV2ContractTests(unittest.TestCase):
    def test_architecture_contract_records_non_negotiable_boundaries(self) -> None:
        contract = ARCHITECTURE.read_text(encoding="utf-8")
        normalised_contract = " ".join(contract.split())
        for required in (
            "Node 24",
            "strict TypeScript",
            "TanStack Router",
            "TanStack Query",
            "React Hook Form",
            "1024 px",
            "Financial calculations remain exclusively in FastAPI",
            "Australia is a bundled provider example, never a frontend default",
            "Local storage may contain only",
            "Advanced mode is progressive disclosure",
        ):
            self.assertIn(required, normalised_contract)

    def test_api_parity_matrix_exactly_matches_current_fastapi_routes(self) -> None:
        documented = set(ROUTE_ROW.findall(PARITY.read_text(encoding="utf-8")))
        self.assertEqual(documented, application_routes())

    def test_every_parity_route_has_an_issue_owner(self) -> None:
        for row in PARITY.read_text(encoding="utf-8").splitlines():
            if ROUTE_ROW.match(f"{row}\n"):
                self.assertRegex(row, r"\| #[0-9]+(?:[ ,].*)? \|$")


if __name__ == "__main__":
    unittest.main()
