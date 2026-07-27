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

    def test_export_has_supported_schema_and_person_finance_slice_pages(self) -> None:
        self.assertEqual(self.application["clientSchemaVersion"], 1)
        self.assertEqual(self.application["serverSchemaVersion"], 6)
        self.assertEqual(
            self.application["pageOrder"],
            ["Home", "Households", "People", "Person finances", "Settings"],
        )
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
        self.assertEqual(len(actions), 13)
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
        self.assertEqual(
            actions["CreateHousehold"]["dynamicBindingPathList"],
            [{"key": "body"}],
        )
        self.assertTrue(
            any(
                "HouseholdName.text" in key
                for key in actions["CreateHousehold"]["jsonPathKeys"]
            )
        )

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

    def test_saved_household_is_verified_after_authentication(self) -> None:
        actions = {
            item["unpublishedAction"]["name"]: item["unpublishedAction"]
            for item in self.application["actionList"]
        }
        restore = actions["RestoreSelectedHousehold"]
        self.assertEqual(restore["actionConfiguration"]["path"], "/api/v1/households")
        self.assertEqual(restore["actionConfiguration"]["httpMethod"], "GET")
        self.assertEqual(restore["runBehaviour"], "MANUAL")

        settings = next(
            page
            for page in self.application["pageList"]
            if page["unpublishedPage"]["name"] == "Settings"
        )
        widgets = settings["unpublishedPage"]["layouts"][0]["dsl"]["children"]
        save = next(widget for widget in widgets if widget["widgetName"] == "SaveSettings")
        self.assertIn("await storeValue('apiToken'", save["onClick"])
        self.assertIn("RestoreSelectedHousehold.run", save["onClick"])
        self.assertIn("item.id === appsmith.store.householdId", save["onClick"])
        self.assertIn("removeValue('householdId')", save["onClick"])
        self.assertIn("removeValue('householdName')", save["onClick"])

    def test_household_table_guards_non_array_responses(self) -> None:
        households = next(
            page
            for page in self.application["pageList"]
            if page["unpublishedPage"]["name"] == "Households"
        )
        widgets = households["unpublishedPage"]["layouts"][0]["dsl"]["children"]
        table = next(widget for widget in widgets if widget["widgetName"] == "ExistingHouseholds")
        self.assertEqual(table["type"], "TABLE_WIDGET_V2")
        self.assertEqual(table["version"], 3)
        self.assertEqual(table["label"], "Households")
        self.assertIn("Array.isArray(ListHouseholds.data)", table["tableData"])
        self.assertEqual(
            table["columnOrder"],
            ["id", "display_name", "currency", "jurisdiction"],
        )
        aliases = []
        for key in table["columnOrder"]:
            column = table["primaryColumns"][key]
            self.assertEqual(column["id"], key)
            self.assertEqual(column["originalId"], key)
            self.assertEqual(column["alias"], key)
            aliases.append(column["alias"])
            self.assertIn("ExistingHouseholds.tableData || []", column["computedValue"])
            self.assertIn(f'currentRow["{key}"]', column["computedValue"])
            self.assertNotIn("processedTableData", column["computedValue"])
            self.assertNotIn("sanitizedTableData", column["computedValue"])
            self.assertNotEqual(column["computedValue"], f"{{{{{key}}}}}")
        self.assertEqual(len(aliases), len(set(aliases)))

        # Mirror Appsmith v1.93's getFilteredTableData column injection. A missing
        # alias makes every column overwrite the same row key with the final value.
        source_rows = [
            {
                "id": "household-id",
                "display_name": "Example home",
                "currency": "NZD",
                "jurisdiction": "NZ",
            }
        ]
        processed_rows = [dict(row) for row in source_rows]
        for key in table["columnOrder"]:
            column = table["primaryColumns"][key]
            computed_values = [row[column["originalId"]] for row in source_rows]
            for index, value in enumerate(computed_values):
                processed_rows[index][column["alias"]] = value
        self.assertEqual(processed_rows, source_rows)

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

    def test_people_slice_has_list_and_create_actions(self) -> None:
        actions = {
            item["unpublishedAction"]["name"]: item["unpublishedAction"]
            for item in self.application["actionList"]
        }
        for name, method in (("ListPeople", "GET"), ("CreatePerson", "POST")):
            action = actions[name]
            self.assertEqual(action["actionConfiguration"]["httpMethod"], method)
            self.assertEqual(
                action["actionConfiguration"]["path"],
                "/api/v1/households/{{appsmith.store.householdId}}/people",
            )
            self.assertIn("appsmith.store.householdId", action["jsonPathKeys"])
        self.assertEqual(actions["ListPeople"]["runBehaviour"], "ON_PAGE_LOAD")
        self.assertEqual(actions["CreatePerson"]["runBehaviour"], "MANUAL")
        self.assertEqual(
            actions["CreatePerson"]["dynamicBindingPathList"],
            [{"key": "body"}],
        )

    def test_people_create_is_country_neutral_and_identity_only(self) -> None:
        action = next(
            item["unpublishedAction"]
            for item in self.application["actionList"]
            if item["unpublishedAction"]["name"] == "CreatePerson"
        )
        body = action["actionConfiguration"]["body"]
        for widget_name in (
            "PersonDisplayName",
            "PersonLegalName",
            "PersonDateOfBirth",
            "PersonResidencyCountry",
            "PersonTaxJurisdiction",
            "PersonEffectiveFrom",
        ):
            self.assertIn(f"{widget_name}.text", body)
        self.assertNotIn("tax_residency_country: '", body)
        self.assertNotIn("tax_jurisdiction: '", body)
        for financial_field in ("income", "salary", "tax_rate", "retirement", "expense"):
            self.assertNotIn(financial_field, body.lower())

    def test_people_page_requires_household_and_disclaims_financial_completeness(self) -> None:
        people = next(
            page
            for page in self.application["pageList"]
            if page["unpublishedPage"]["name"] == "People"
        )
        widgets = people["unpublishedPage"]["layouts"][0]["dsl"]["children"]
        help_text = next(widget for widget in widgets if widget["widgetName"] == "PeopleHelp")
        self.assertIn("identity only", help_text["text"])
        self.assertIn("financial details are not complete", help_text["text"])
        create = next(widget for widget in widgets if widget["widgetName"] == "CreatePersonButton")
        self.assertIn("!appsmith.store.householdId", create["isDisabled"])
        self.assertIn("PersonDisplayName.text", create["isDisabled"])
        self.assertIn("PersonEffectiveFrom.text", create["isDisabled"])

    def test_people_table_has_distinct_v193_column_identity(self) -> None:
        people = next(
            page
            for page in self.application["pageList"]
            if page["unpublishedPage"]["name"] == "People"
        )
        widgets = people["unpublishedPage"]["layouts"][0]["dsl"]["children"]
        table = next(widget for widget in widgets if widget["widgetName"] == "ExistingPeople")
        self.assertEqual(table["version"], 3)
        self.assertEqual(table["label"], "People")
        self.assertIn("Array.isArray(ListPeople.data)", table["tableData"])
        aliases = []
        for key in table["columnOrder"]:
            column = table["primaryColumns"][key]
            self.assertEqual(column["id"], key)
            self.assertEqual(column["originalId"], key)
            self.assertEqual(column["alias"], key)
            self.assertIn("ExistingPeople.tableData || []", column["computedValue"])
            self.assertIn(f'currentRow["{key}"]', column["computedValue"])
            aliases.append(column["alias"])
        self.assertEqual(len(aliases), len(set(aliases)))

    def test_person_finance_slice_does_not_include_later_workflows(self) -> None:
        source = EXPORT.read_text(encoding="utf-8")
        for deferred_name in (
            "CreateExpense",
            "CreateProperty",
            "CreateScenario",
            "ListTimeline",
        ):
            self.assertNotIn(deferred_name, source)

    def test_person_selection_opens_finances_and_household_change_clears_it(self) -> None:
        pages = {
            page["unpublishedPage"]["name"]: page
            for page in self.application["pageList"]
        }
        people_widgets = pages["People"]["unpublishedPage"]["layouts"][0]["dsl"]["children"]
        manage = next(
            widget
            for widget in people_widgets
            if widget["widgetName"] == "ManagePersonFinancesButton"
        )
        self.assertIn("ExistingPeople.selectedRow.id", manage["onClick"])
        self.assertIn("storeValue('personId'", manage["onClick"])
        self.assertIn("navigateTo('Person finances')", manage["onClick"])

        household_widgets = pages["Households"]["unpublishedPage"]["layouts"][0]["dsl"]["children"]
        for name in ("CreateHouseholdButton", "UseHouseholdButton"):
            widget = next(item for item in household_widgets if item["widgetName"] == name)
            self.assertIn("removeValue('personId')", widget["onClick"])
            self.assertIn("removeValue('personName')", widget["onClick"])

    def test_person_finance_actions_are_scoped_and_use_lookup_discovery(self) -> None:
        actions = {
            item["unpublishedAction"]["name"]: item["unpublishedAction"]
            for item in self.application["actionList"]
        }
        self.assertEqual(
            actions["ListFinancePeople"]["actionConfiguration"]["path"],
            "/api/v1/households/{{appsmith.store.householdId}}/people",
        )
        self.assertEqual(
            actions["ListIncomeTypes"]["actionConfiguration"]["path"],
            "/api/v1/lookups/income_type",
        )
        self.assertEqual(
            actions["ListTaxProviders"]["actionConfiguration"]["path"],
            "/api/v1/tax-providers",
        )
        for name, suffix, method in (
            ("ListIncomeSources", "income-sources", "GET"),
            ("CreateIncome", "income-sources", "POST"),
            ("ListTaxProfiles", "tax-profiles", "GET"),
            ("CreateTaxProfile", "tax-profiles", "POST"),
        ):
            action = actions[name]
            self.assertEqual(
                action["actionConfiguration"]["path"],
                f"/api/v1/people/{{{{appsmith.store.personId}}}}/{suffix}",
            )
            self.assertEqual(action["actionConfiguration"]["httpMethod"], method)
            self.assertIn("appsmith.store.personId", action["jsonPathKeys"])

    def test_income_form_sends_dated_recurring_source_without_defaults(self) -> None:
        action = next(
            item["unpublishedAction"]
            for item in self.application["actionList"]
            if item["unpublishedAction"]["name"] == "CreateIncome"
        )
        body = action["actionConfiguration"]["body"]
        for widget_name in (
            "IncomeType",
            "IncomeName",
            "IncomeAmount",
            "IncomeFrequency",
            "IncomeTaxable",
            "IncomeEffectiveFrom",
            "IncomeEffectiveTo",
            "IncomeGrowthRate",
            "IncomeSalarySacrifice",
            "IncomeNotes",
        ):
            self.assertIn(widget_name, body)
        self.assertNotIn("income_type_id: '", body)
        self.assertNotIn("frequency: 'ANNUAL'", body)
        self.assertNotIn("gross_amount: 0", body)

    def test_tax_form_discovers_providers_and_keeps_manual_mode_country_neutral(self) -> None:
        page = next(
            page
            for page in self.application["pageList"]
            if page["unpublishedPage"]["name"] == "Person finances"
        )
        widgets = page["unpublishedPage"]["layouts"][0]["dsl"]["children"]
        provider = next(widget for widget in widgets if widget["widgetName"] == "TaxProviderYear")
        self.assertIn("ListTaxProviders.data", provider["sourceData"])
        self.assertIn("provider.supported_tax_years", provider["sourceData"])
        self.assertNotIn("Australia", provider["sourceData"])
        self.assertNotIn("AU", provider["sourceData"])

        action = next(
            item["unpublishedAction"]
            for item in self.application["actionList"]
            if item["unpublishedAction"]["name"] == "CreateTaxProfile"
        )
        body = action["actionConfiguration"]["body"]
        self.assertIn("TaxProviderYear.selectedOptionValue.split", body)
        self.assertIn("ManualTaxJurisdiction.text", body)
        self.assertIn("ManualTaxYear.text", body)
        self.assertIn("ManualAnnualNetIncome.text", body)
        self.assertIn("JSON.parse(TaxParameters.text", body)
        self.assertNotIn("jurisdiction: 'AU'", body)
        self.assertNotIn("tax_year: '2025-26'", body)

    def test_person_finance_tables_guard_responses_and_keep_distinct_columns(self) -> None:
        page = next(
            page
            for page in self.application["pageList"]
            if page["unpublishedPage"]["name"] == "Person finances"
        )
        widgets = page["unpublishedPage"]["layouts"][0]["dsl"]["children"]
        for table_name in ("FinancePeople", "IncomeSources", "TaxProfiles"):
            table = next(widget for widget in widgets if widget["widgetName"] == table_name)
            self.assertIn("Array.isArray(", table["tableData"])
            aliases = []
            for key in table["columnOrder"]:
                column = table["primaryColumns"][key]
                self.assertEqual(column["id"], key)
                self.assertEqual(column["originalId"], key)
                self.assertEqual(column["alias"], key)
                self.assertIn(f"{table_name}.tableData || []", column["computedValue"])
                aliases.append(column["alias"])
            self.assertEqual(len(aliases), len(set(aliases)))

    def test_person_finance_validation_requires_explicit_material_values(self) -> None:
        page = next(
            page
            for page in self.application["pageList"]
            if page["unpublishedPage"]["name"] == "Person finances"
        )
        widgets = page["unpublishedPage"]["layouts"][0]["dsl"]["children"]
        income = next(widget for widget in widgets if widget["widgetName"] == "CreateIncomeButton")
        for required in (
            "appsmith.store.personId",
            "IncomeType.selectedOptionValue",
            "IncomeAmount.text",
            "IncomeFrequency.selectedOptionValue",
            "IncomeEffectiveFrom.text",
        ):
            self.assertIn(required, income["isDisabled"])

        tax = next(
            widget for widget in widgets if widget["widgetName"] == "CreateTaxProfileButton"
        )
        self.assertIn("TaxProviderYear.selectedOptionValue", tax["isDisabled"])
        self.assertIn("JSON.parse(TaxParameters.text)", tax["isDisabled"])
        self.assertIn("ManualAnnualNetIncome.text", tax["isDisabled"])
        self.assertIn("TaxEffectiveFrom.text", tax["isDisabled"])


if __name__ == "__main__":
    unittest.main()
