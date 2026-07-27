"""Structural tests for the generated Appsmith application export."""

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
EXPORT = ROOT / "household-financial-planner.json"
sys.path.insert(0, str(ROOT))


class AppsmithExportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.application = json.loads(EXPORT.read_text(encoding="utf-8"))

    def test_export_has_supported_schema_and_only_foundation_pages(self) -> None:
        self.assertEqual(self.application["clientSchemaVersion"], 1)
        self.assertEqual(self.application["serverSchemaVersion"], 6)
        self.assertEqual(self.application["pageOrder"], ["Home", "Settings"])
        self.assertEqual(self.application["publishedDefaultPageName"], "Home")

    def test_export_contains_no_credentials_or_personal_defaults(self) -> None:
        source = EXPORT.read_text(encoding="utf-8")
        self.assertNotIn("jordan", source.lower())
        self.assertNotIn("@", source)
        self.assertNotIn('"apiToken":', source)
        self.assertNotIn('"developmentSubject":', source)

    def test_every_page_has_navigation_and_user_facing_content(self) -> None:
        for page in self.application["pageList"]:
            children = page["unpublishedPage"]["layouts"][0]["dsl"]["children"]
            names = {widget["widgetName"] for widget in children}
            self.assertIn("PageTitle", names)
            self.assertTrue(any(name.startswith("Nav") for name in names))
            self.assertGreaterEqual(len(children), 5)

    def test_api_actions_use_runtime_auth_and_docker_service_url(self) -> None:
        actions = self.application["actionList"]
        self.assertEqual(len(actions), 1)
        for wrapper in actions:
            action = wrapper["unpublishedAction"]
            self.assertEqual(
                action["datasource"]["datasourceConfiguration"]["url"],
                "http://api:8000",
            )
            headers = {
                item["key"]: item["value"]
                for item in action["actionConfiguration"]["headers"]
            }
            self.assertIn("appsmith.store.apiToken", headers["Authorization"])
            self.assertIn(
                "appsmith.store.developmentSubject",
                headers["X-Development-Subject"],
            )

    def test_generated_export_is_current(self) -> None:
        from generate_app import build

        self.assertEqual(self.application, build())

    def test_sensitive_settings_are_session_only(self) -> None:
        settings = next(
            page
            for page in self.application["pageList"]
            if page["unpublishedPage"]["name"] == "Settings"
        )
        widgets = settings["unpublishedPage"]["layouts"][0]["dsl"]["children"]
        save = next(widget for widget in widgets if widget["widgetName"] == "SaveSettings")
        self.assertIn("storeValue('apiToken', BearerToken.text || '', false)", save["onClick"])
        self.assertIn(
            "storeValue('developmentSubject', DevelopmentSubject.text || '', false)",
            save["onClick"],
        )

    def test_foundation_health_check_uses_ready_endpoint(self) -> None:
        action = self.application["actionList"][0]["unpublishedAction"]
        self.assertEqual(action["name"], "HealthCheck")
        self.assertEqual(action["actionConfiguration"]["path"], "/health/ready")
        self.assertEqual(action["runBehaviour"], "ON_PAGE_LOAD")

    def test_foundation_does_not_include_later_workflows(self) -> None:
        source = EXPORT.read_text(encoding="utf-8")
        for deferred_name in (
            "CreateHousehold",
            "CreatePerson",
            "CreateProperty",
            "CreateScenario",
            "ListTimeline",
        ):
            self.assertNotIn(deferred_name, source)


if __name__ == "__main__":
    unittest.main()
