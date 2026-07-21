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

    def test_export_has_supported_schema_and_all_phase_10_pages(self) -> None:
        self.assertEqual(self.application["clientSchemaVersion"], 1)
        self.assertEqual(self.application["serverSchemaVersion"], 6)
        self.assertEqual(
            self.application["pageOrder"],
            [
                "Onboarding",
                "Dashboard",
                "People",
                "Properties",
                "Property Wizard",
                "Timeline",
                "Scenarios",
                "Settings",
            ],
        )

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
            self.assertGreaterEqual(len(children), 10)

    def test_api_actions_use_runtime_auth_and_docker_service_url(self) -> None:
        actions = self.application["actionList"]
        self.assertGreaterEqual(len(actions), 14)
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
        self.assertIn("storeValue('apiToken', BearerToken.text, false)", save["onClick"])
        self.assertIn(
            "storeValue('developmentSubject', DevelopmentSubject.text, false)",
            save["onClick"],
        )

    def test_inputs_have_string_defaults(self) -> None:
        for page in self.application["pageList"]:
            widgets = page["unpublishedPage"]["layouts"][0]["dsl"]["children"]
            for widget in widgets:
                if widget["type"] == "INPUT_WIDGET_V2":
                    self.assertEqual(widget["defaultText"], "")

    def test_onboarding_handles_an_empty_household_selection(self) -> None:
        onboarding = next(
            page
            for page in self.application["pageList"]
            if page["unpublishedPage"]["name"] == "Onboarding"
        )
        widgets = onboarding["unpublishedPage"]["layouts"][0]["dsl"]["children"]
        use_household = next(
            widget for widget in widgets if widget["widgetName"] == "UseHouseholdButton"
        )
        self.assertIn("selectedRow?.id", use_household["isDisabled"])
        self.assertIn("selectedRow?.id", use_household["onClick"])

        create_household = next(
            wrapper["unpublishedAction"]
            for wrapper in self.application["actionList"]
            if wrapper["unpublishedAction"]["name"] == "CreateHousehold"
        )
        body = create_household["actionConfiguration"]["body"]
        self.assertIn("String(HouseholdName.text || '')", body)

    def test_current_snapshot_debt_cannot_silently_default_to_zero(self) -> None:
        wizard = next(
            page
            for page in self.application["pageList"]
            if page["unpublishedPage"]["name"] == "Property Wizard"
        )
        widgets = wizard["unpublishedPage"]["layouts"][0]["dsl"]["children"]
        debt = next(widget for widget in widgets if widget["widgetName"] == "PropertyDebt")
        self.assertIn("CURRENT_SNAPSHOT", debt["isRequired"])
        self.assertIn("CURRENT_SNAPSHOT", debt["isVisible"])


if __name__ == "__main__":
    unittest.main()
