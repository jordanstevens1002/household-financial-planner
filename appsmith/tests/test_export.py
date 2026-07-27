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

    def test_export_has_supported_schema_and_household_slice_pages(self) -> None:
        self.assertEqual(self.application["clientSchemaVersion"], 1)
        self.assertEqual(self.application["serverSchemaVersion"], 6)
        self.assertEqual(self.application["pageOrder"], ["Home", "Households", "Settings"])
        self.assertEqual(self.application["publishedDefaultPageName"], "Home")

    def test_export_contains_no_credentials_or_identity_defaults(self) -> None:
        source = EXPORT.read_text(encoding="utf-8")
        self.assertNotIn("@", source)
        self.assertNotIn('"apiToken":', source)
        self.assertNotIn('"developmentSubject":', source)

        settings = next(
            page
            for page in self.application["pageList"]
            if page["unpublishedPage"]["name"] == "Settings"
        )
        widgets = settings["unpublishedPage"]["layouts"][0]["dsl"]["children"]
        for widget_name in ("BearerToken", "DevelopmentSubject"):
            widget = next(item for item in widgets if item["widgetName"] == widget_name)
            self.assertEqual(widget["defaultText"], "")

    def test_every_page_has_navigation_and_user_facing_content(self) -> None:
        for page in self.application["pageList"]:
            children = page["unpublishedPage"]["layouts"][0]["dsl"]["children"]
            names = {widget["widgetName"] for widget in children}
            self.assertIn("PageTitle", names)
            self.assertTrue(any(name.startswith("Nav") for name in names))
            self.assertGreaterEqual(len(children), 5)

    def test_api_actions_use_runtime_auth_and_docker_service_url(self) -> None:
        actions = self.application["actionList"]
        self.assertEqual(len(actions), 3)
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
        action = next(
            item["unpublishedAction"]
            for item in self.application["actionList"]
            if item["unpublishedAction"]["name"] == "HealthCheck"
        )
        self.assertEqual(action["name"], "HealthCheck")
        self.assertEqual(action["actionConfiguration"]["path"], "/health/ready")
        self.assertEqual(action["runBehaviour"], "ON_PAGE_LOAD")

    def test_household_slice_has_list_and_create_actions(self) -> None:
        actions = {
            item["unpublishedAction"]["name"]: item["unpublishedAction"]
            for item in self.application["actionList"]
        }
        self.assertEqual(
            actions["ListHouseholds"]["actionConfiguration"]["path"],
            "/api/v1/households",
        )
        self.assertEqual(actions["ListHouseholds"]["actionConfiguration"]["httpMethod"], "GET")
        self.assertEqual(actions["ListHouseholds"]["runBehaviour"], "ON_PAGE_LOAD")
        self.assertEqual(
            actions["CreateHousehold"]["actionConfiguration"]["path"],
            "/api/v1/households",
        )
        self.assertEqual(actions["CreateHousehold"]["actionConfiguration"]["httpMethod"], "POST")

    def test_household_selection_is_persistent_but_credentials_are_not(self) -> None:
        households = next(
            page
            for page in self.application["pageList"]
            if page["unpublishedPage"]["name"] == "Households"
        )
        widgets = households["unpublishedPage"]["layouts"][0]["dsl"]["children"]
        create = next(widget for widget in widgets if widget["widgetName"] == "CreateHouseholdButton")
        select = next(widget for widget in widgets if widget["widgetName"] == "UseHouseholdButton")
        for widget in (create, select):
            self.assertIn("storeValue('householdId'", widget["onClick"])
            self.assertIn("storeValue('householdName'", widget["onClick"])
            self.assertIn(", true)", widget["onClick"])

    def test_household_table_guards_non_array_responses(self) -> None:
        households = next(
            page
            for page in self.application["pageList"]
            if page["unpublishedPage"]["name"] == "Households"
        )
        widgets = households["unpublishedPage"]["layouts"][0]["dsl"]["children"]
        table = next(widget for widget in widgets if widget["widgetName"] == "ExistingHouseholds")
        self.assertIn("Array.isArray(ListHouseholds.data)", table["tableData"])
        self.assertEqual(
            table["columnOrder"],
            ["id", "display_name", "currency", "jurisdiction"],
        )
        for key in table["columnOrder"]:
            column = table["primaryColumns"][key]
            self.assertIn(f"currentRow.{key}", column["computedValue"])
            self.assertNotEqual(column["computedValue"], f"{{{{{key}}}}}")
        use = next(widget for widget in widgets if widget["widgetName"] == "UseHouseholdButton")
        self.assertIn("!ExistingHouseholds.selectedRow", use["isDisabled"])

    def test_household_create_keeps_defaults_country_neutral(self) -> None:
        action = next(
            item["unpublishedAction"]
            for item in self.application["actionList"]
            if item["unpublishedAction"]["name"] == "CreateHousehold"
        )
        body = action["actionConfiguration"]["body"]
        self.assertIn("HouseholdCurrency.text", body)
        self.assertIn("HouseholdJurisdiction.text", body)
        self.assertNotIn("currency: '", body)
        self.assertNotIn("jurisdiction: '", body)

    def test_household_slice_does_not_include_later_workflows(self) -> None:
        source = EXPORT.read_text(encoding="utf-8")
        for deferred_name in (
            "CreatePerson",
            "CreateProperty",
            "CreateScenario",
            "ListTimeline",
        ):
            self.assertNotIn(deferred_name, source)


if __name__ == "__main__":
    unittest.main()
