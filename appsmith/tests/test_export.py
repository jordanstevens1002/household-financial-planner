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

    def test_export_has_supported_schema_and_property_slice_pages(self) -> None:
        self.assertEqual(self.application["clientSchemaVersion"], 1)
        self.assertEqual(self.application["serverSchemaVersion"], 6)
        self.assertEqual(
            self.application["pageOrder"],
            [
                "Home",
                "Households",
                "People",
                "Person finances",
                "Cash flow",
                "Properties",
                "Retirement",
                "Timeline",
                "Scenarios",
                "Settings",
            ],
        )
        self.assertEqual(self.application["publishedDefaultPageName"], "Home")

    def test_retirement_actions_use_neutral_discovery_and_backend_projection(self) -> None:
        actions = {
            item["unpublishedAction"]["name"]: item["unpublishedAction"]
            for item in self.application["actionList"]
        }
        expected = {
            "ListRetirementAccountTypes": "/api/v1/lookups/retirement_account_type",
            "ListRetirementProviders": "/api/v1/retirement-providers",
            "ListRetirementAccounts": (
                "/api/v1/households/{{appsmith.store.householdId}}/retirement-accounts"
            ),
            "ListContributionProfiles": (
                "/api/v1/retirement-accounts/"
                "{{appsmith.store.retirementAccountId}}/contribution-profiles"
            ),
            "CalculateRetirementProjection": (
                "/api/v1/retirement-accounts/"
                "{{appsmith.store.retirementAccountId}}/projection"
            ),
        }
        for name, path in expected.items():
            self.assertEqual(actions[name]["actionConfiguration"]["path"], path)

        body = actions["CreateRetirementAccount"]["actionConfiguration"]["body"]
        self.assertIn("RetirementProvider.selectedOptionValue", body)
        self.assertIn("JSON.parse(RetirementProviderSettings.text", body)
        self.assertNotIn("AU_SUPER", body)
        self.assertNotIn("Australian", body)

    def test_retirement_page_has_progressive_contribution_and_projection_flows(self) -> None:
        page = next(
            page
            for page in self.application["pageList"]
            if page["unpublishedPage"]["name"] == "Retirement"
        )
        widgets = page["unpublishedPage"]["layouts"][0]["dsl"]["children"]
        names = {widget["widgetName"] for widget in widgets}
        for required in (
            "RetirementAccountsTable",
            "ManageRetirementAccountButton",
            "ToggleRetirementAdvancedButton",
            "ContributionProfilesTable",
            "CalculateRetirementProjectionButton",
            "ProjectedBalance",
            "ProjectionAssumptions",
            "ProjectionWarnings",
        ):
            self.assertIn(required, names)

        provider = next(
            widget for widget in widgets if widget["widgetName"] == "RetirementProvider"
        )
        self.assertIn("ListRetirementProviders.data", provider["sourceData"])
        self.assertNotIn("Australian", provider["sourceData"])
        settings = next(
            widget
            for widget in widgets
            if widget["widgetName"] == "RetirementProviderSettings"
        )
        self.assertIn("retirementAdvancedMode", settings["isVisible"])

    def test_retirement_progressive_sections_do_not_overlap_in_edit_mode(self) -> None:
        page = next(
            page
            for page in self.application["pageList"]
            if page["unpublishedPage"]["name"] == "Retirement"
        )
        widgets = page["unpublishedPage"]["layouts"][0]["dsl"]["children"]
        by_name = {widget["widgetName"]: widget for widget in widgets}
        contribution_bottom = by_name["ContributionProfilesTable"]["bottomRow"]
        projection_widgets = (
            "ProjectionHelp",
            "RetirementProjectionDate",
            "CalculateRetirementProjectionButton",
            "ProjectedBalance",
            "ProjectionTotals",
            "ProjectionAssumptions",
            "ProjectionWarnings",
        )
        self.assertTrue(
            all(by_name[name]["topRow"] > contribution_bottom for name in projection_widgets)
        )

    def test_retirement_forms_require_material_values_without_country_defaults(self) -> None:
        page = next(
            page
            for page in self.application["pageList"]
            if page["unpublishedPage"]["name"] == "Retirement"
        )
        widgets = page["unpublishedPage"]["layouts"][0]["dsl"]["children"]
        create = next(
            widget
            for widget in widgets
            if widget["widgetName"] == "CreateRetirementAccountButton"
        )
        for required in (
            "RetirementAccountType.selectedOptionValue",
            "RetirementOpeningBalance.text",
            "RetirementOpeningDate.text",
            "RetirementReturnRate.text",
            "RetirementAnnualFees.text",
        ):
            self.assertIn(required, create["isDisabled"])

        contribution = next(
            widget
            for widget in widgets
            if widget["widgetName"] == "CreateContributionProfileButton"
        )
        self.assertIn("ContributionEmployerRate.text", contribution["isDisabled"])
        self.assertIn("ContributionEmployerAmount.text", contribution["isDisabled"])
        self.assertIn("retirementAccountId", contribution["isDisabled"])

    def test_timeline_actions_use_backend_provenance_and_filters(self) -> None:
        actions = {
            item["unpublishedAction"]["name"]: item["unpublishedAction"]
            for item in self.application["actionList"]
        }
        timeline = actions["ListTimeline"]["actionConfiguration"]
        self.assertTrue(
            timeline["path"].startswith(
                "/api/v1/households/{{appsmith.store.householdId}}/timeline"
            )
        )
        self.assertIn("TimelineFrom.text", timeline["path"])
        self.assertIn("TimelineTo.text", timeline["path"])
        self.assertIn("TimelineIncludeDisabled", timeline["path"])
        self.assertIn(".filter(Boolean)", timeline["path"])
        self.assertNotIn("from_date=null", timeline["path"])
        self.assertEqual(timeline["queryParameters"], [])

        create = actions["CreateTimelineEvent"]["actionConfiguration"]["body"]
        for field in (
            "TimelineEventType.selectedOptionValue",
            "TimelineClassification.selectedOptionValue",
            "TimelineEffectiveAt.text",
            "TimelineProperty.selectedOptionValue",
            "TimelinePerson.selectedOptionValue",
            "TimelineLoan.selectedOptionValue",
        ):
            self.assertIn(field, create)
        self.assertIn("JSON.parse(TimelinePayload.text", create)

    def test_timeline_page_displays_provenance_quality_and_progressive_advanced_form(
        self,
    ) -> None:
        page = next(
            page
            for page in self.application["pageList"]
            if page["unpublishedPage"]["name"] == "Timeline"
        )
        widgets = page["unpublishedPage"]["layouts"][0]["dsl"]["children"]
        by_name = {widget["widgetName"]: widget for widget in widgets}
        table = by_name["TimelineTable"]
        self.assertIn("ListTimeline.data?.events", table["tableData"])
        self.assertIn("item.classification", table["tableData"])
        self.assertIn("data_quality_flags", table["tableData"])
        self.assertIn(
            "ListTimeline.data?.data_quality_flags",
            by_name["TimelineQualityFlags"]["text"],
        )
        self.assertIn("timelineCreateOpen", by_name["TimelineEventType"]["isVisible"])
        self.assertIn(
            "timelineAdvancedMode",
            by_name["TimelinePayload"]["isVisible"],
        )
        toggle = by_name["ToggleSelectedEventButton"]
        self.assertIn("classification === 'OBSERVED'", toggle["isDisabled"])
        self.assertIn("selectedRow?.is_enabled", toggle["text"])

        actions = {
            item["unpublishedAction"]["name"]: item["unpublishedAction"]
            for item in self.application["actionList"]
        }
        toggle_action = actions["ToggleTimelineEvent"]["actionConfiguration"]
        self.assertIn("selectedRow?.id", toggle_action["path"])
        self.assertIn("selectedRow?.is_enabled", toggle_action["body"])

    def test_timeline_event_requires_explicit_classification_and_effective_datetime(
        self,
    ) -> None:
        page = next(
            page
            for page in self.application["pageList"]
            if page["unpublishedPage"]["name"] == "Timeline"
        )
        widgets = page["unpublishedPage"]["layouts"][0]["dsl"]["children"]
        create = next(
            widget
            for widget in widgets
            if widget["widgetName"] == "CreateTimelineEventButton"
        )
        self.assertIn("TimelineEventType.selectedOptionValue", create["isDisabled"])
        self.assertIn("TimelineClassification.selectedOptionValue", create["isDisabled"])
        self.assertIn("TimelineEffectiveAt.text", create["isDisabled"])
        classification = next(
            widget
            for widget in widgets
            if widget["widgetName"] == "TimelineClassification"
        )
        self.assertEqual(classification["defaultOptionValue"], "")

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

    def test_every_widget_remains_inside_the_responsive_canvas(self) -> None:
        for page in self.application["pageList"]:
            children = page["unpublishedPage"]["layouts"][0]["dsl"]["children"]
            for widget in children:
                with self.subTest(
                    page=page["unpublishedPage"]["name"],
                    widget=widget["widgetName"],
                ):
                    self.assertGreaterEqual(widget["leftColumn"], 0)
                    self.assertLess(widget["leftColumn"], widget["rightColumn"])
                    self.assertLessEqual(widget["rightColumn"], 64)

    def test_api_actions_use_runtime_auth_and_docker_service_url(self) -> None:
        actions = self.application["actionList"]
        self.assertEqual(len(actions), 61)
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
            self.assertIn("storeValue('householdCurrency'", widget["onClick"])
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
        self.assertIn("storeValue('householdCurrency'", save["onClick"])
        self.assertIn("removeValue('householdId')", save["onClick"])
        self.assertIn("removeValue('householdName')", save["onClick"])
        self.assertIn("removeValue('householdCurrency')", save["onClick"])

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
        self.assertIn("HouseholdCurrency.selectedOptionValue", body)
        self.assertIn("HouseholdJurisdiction.selectedOptionValue", body)
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
            "PersonEffectiveFrom",
        ):
            self.assertIn(f"{widget_name}.text", body)
        self.assertIn("PersonResidencyCountry.selectedOptionValue", body)
        self.assertIn("PersonTaxJurisdiction.selectedOptionValue", body)
        self.assertIn("appsmith.store.personAdvancedMode", body)
        self.assertIn(
            ": PersonResidencyCountry.selectedOptionValue && "
            "PersonResidencyCountry.selectedOptionValue !== 'NONE' ? "
            "PersonResidencyCountry.selectedOptionValue : null",
            body,
        )
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

    def test_export_does_not_include_workflows_after_phase_10k(self) -> None:
        source = EXPORT.read_text(encoding="utf-8")
        for deferred_name in ("DemoMode",):
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
        self.assertNotIn("ListFinancePeople", actions)
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
        for table_name in ("IncomeSources", "TaxProfiles"):
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

    def test_person_finance_page_uses_progressive_sections_without_duplicate_selection(self) -> None:
        page = next(
            page
            for page in self.application["pageList"]
            if page["unpublishedPage"]["name"] == "Person finances"
        )
        widgets = page["unpublishedPage"]["layouts"][0]["dsl"]["children"]
        names = {widget["widgetName"] for widget in widgets}
        self.assertNotIn("FinancePeople", names)
        self.assertNotIn("UseFinancePersonButton", names)
        self.assertIn("ChangeFinancePersonButton", names)
        self.assertIn("ShowIncomeSectionButton", names)
        self.assertIn("ShowTaxSectionButton", names)

        income = next(widget for widget in widgets if widget["widgetName"] == "IncomeType")
        tax = next(widget for widget in widgets if widget["widgetName"] == "TaxCalculationMode")
        self.assertIn("financeSection", income["isVisible"])
        self.assertIn("financeSection", tax["isVisible"])

    def test_raw_provider_json_is_available_only_in_explicit_advanced_mode(self) -> None:
        page = next(
            page
            for page in self.application["pageList"]
            if page["unpublishedPage"]["name"] == "Person finances"
        )
        widgets = page["unpublishedPage"]["layouts"][0]["dsl"]["children"]
        toggle = next(
            widget for widget in widgets if widget["widgetName"] == "ToggleAdvancedModeButton"
        )
        parameters = next(widget for widget in widgets if widget["widgetName"] == "TaxParameters")
        self.assertIn("financeAdvancedMode", toggle["onClick"])
        self.assertIn("financeAdvancedMode", parameters["isVisible"])
        self.assertIn("TaxCalculationMode.selectedOptionValue === 'AUTOMATIC'", parameters["isVisible"])

        create = next(
            widget for widget in widgets if widget["widgetName"] == "CreateTaxProfileButton"
        )
        self.assertIn("appsmith.store.financeAdvancedMode", create["isDisabled"])
        self.assertIn("JSON.parse(TaxParameters.text)", create["isDisabled"])

    def test_finance_tables_use_friendly_labels_and_forms_reset_after_success(self) -> None:
        page = next(
            page
            for page in self.application["pageList"]
            if page["unpublishedPage"]["name"] == "Person finances"
        )
        widgets = page["unpublishedPage"]["layouts"][0]["dsl"]["children"]
        income_table = next(widget for widget in widgets if widget["widgetName"] == "IncomeSources")
        tax_table = next(widget for widget in widgets if widget["widgetName"] == "TaxProfiles")
        self.assertIn("Fortnightly", income_table["tableData"])
        self.assertIn("item.taxable ? 'Yes' : 'No'", income_table["tableData"])
        self.assertIn("Installed provider", tax_table["tableData"])
        self.assertIn("Manual annual net income", tax_table["tableData"])

        create_income = next(
            widget for widget in widgets if widget["widgetName"] == "CreateIncomeButton"
        )
        create_tax = next(
            widget for widget in widgets if widget["widgetName"] == "CreateTaxProfileButton"
        )
        self.assertIn("resetWidget('IncomeName'", create_income["onClick"])
        self.assertIn("resetWidget('TaxEffectiveFrom'", create_tax["onClick"])

    def test_finance_empty_states_explain_the_next_action(self) -> None:
        page = next(
            page
            for page in self.application["pageList"]
            if page["unpublishedPage"]["name"] == "Person finances"
        )
        widgets = page["unpublishedPage"]["layouts"][0]["dsl"]["children"]
        income = next(widget for widget in widgets if widget["widgetName"] == "IncomeEmptyState")
        tax = next(widget for widget in widgets if widget["widgetName"] == "TaxEmptyState")
        self.assertIn("No income sources yet", income["text"])
        self.assertIn("No tax settings yet", tax["text"])

    def test_hidden_finance_sections_do_not_overlap_in_edit_mode(self) -> None:
        page = next(
            page
            for page in self.application["pageList"]
            if page["unpublishedPage"]["name"] == "Person finances"
        )
        widgets = page["unpublishedPage"]["layouts"][0]["dsl"]["children"]
        income_names = {
            "IncomeHeading",
            "IncomeEmptyState",
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
            "CreateIncomeButton",
            "IncomeSources",
        }
        tax_names = {
            "TaxHeading",
            "TaxEmptyState",
            "TaxCalculationMode",
            "TaxProviderYear",
            "TaxParameters",
            "ManualTaxJurisdiction",
            "ManualTaxYear",
            "ManualAnnualNetIncome",
            "TaxEffectiveFrom",
            "TaxEffectiveTo",
            "CreateTaxProfileButton",
            "TaxProfiles",
        }
        income_bottom = max(
            widget["bottomRow"] for widget in widgets if widget["widgetName"] in income_names
        )
        tax_top = min(widget["topRow"] for widget in widgets if widget["widgetName"] in tax_names)
        self.assertLess(income_bottom, tax_top)

    def test_home_has_one_contextual_action_instead_of_duplicate_navigation(self) -> None:
        page = next(
            page
            for page in self.application["pageList"]
            if page["unpublishedPage"]["name"] == "Home"
        )
        widgets = page["unpublishedPage"]["layouts"][0]["dsl"]["children"]
        names = {widget["widgetName"] for widget in widgets}
        self.assertIn("ContinueSetup", names)
        for duplicate in ("OpenHouseholds", "OpenPeople", "OpenPersonFinances", "OpenSettings"):
            self.assertNotIn(duplicate, names)
        continue_button = next(
            widget for widget in widgets if widget["widgetName"] == "ContinueSetup"
        )
        self.assertIn("appsmith.store.personId", continue_button["onClick"])
        self.assertIn("appsmith.store.householdId", continue_button["onClick"])

    def test_phase_10k_uses_maintained_country_and_currency_selectors(self) -> None:
        actions = {
            item["unpublishedAction"]["name"]: item["unpublishedAction"]
            for item in self.application["actionList"]
        }
        self.assertEqual(
            actions["ListCountryReferences"]["actionConfiguration"]["path"],
            "/api/v1/reference/countries",
        )
        self.assertEqual(
            actions["ListCurrencyReferences"]["actionConfiguration"]["path"],
            "/api/v1/reference/currencies",
        )
        households = next(
            page
            for page in self.application["pageList"]
            if page["unpublishedPage"]["name"] == "Households"
        )
        widgets = households["unpublishedPage"]["layouts"][0]["dsl"]["children"]
        by_name = {widget["widgetName"]: widget for widget in widgets}
        currency = by_name["HouseholdCurrency"]
        jurisdiction = by_name["HouseholdJurisdiction"]
        self.assertEqual(currency["type"], "SELECT_WIDGET")
        self.assertIn("ListCurrencyReferences.data", currency["sourceData"])
        self.assertEqual(currency["defaultOptionValue"], "")
        self.assertEqual(jurisdiction["type"], "SELECT_WIDGET")
        self.assertIn("ListCountryReferences.data", jurisdiction["sourceData"])
        self.assertIn("item.flag", jurisdiction["sourceData"])
        self.assertEqual(jurisdiction["defaultOptionValue"], "NONE")

        people = next(
            page
            for page in self.application["pageList"]
            if page["unpublishedPage"]["name"] == "People"
        )
        people_widgets = people["unpublishedPage"]["layouts"][0]["dsl"]["children"]
        residency = next(
            widget
            for widget in people_widgets
            if widget["widgetName"] == "PersonResidencyCountry"
        )
        self.assertEqual(residency["type"], "SELECT_WIDGET")
        self.assertIn("ListPersonCountryReferences.data", residency["sourceData"])
        self.assertIn("item.flag", residency["sourceData"])
        self.assertEqual(residency["defaultOptionValue"], "NONE")
        jurisdiction = next(
            widget
            for widget in people_widgets
            if widget["widgetName"] == "PersonTaxJurisdiction"
        )
        self.assertEqual(jurisdiction["type"], "SELECT_WIDGET")
        self.assertIn("ListPersonCountryReferences.data", jurisdiction["sourceData"])
        self.assertIn("item.flag", jurisdiction["sourceData"])
        self.assertIn("personAdvancedMode", jurisdiction["isVisible"])
        self.assertEqual(jurisdiction["defaultOptionValue"], "NONE")

    def test_home_dashboard_uses_backend_figures_and_safe_empty_paths(self) -> None:
        actions = {
            item["unpublishedAction"]["name"]: item["unpublishedAction"]
            for item in self.application["actionList"]
        }
        for name, suffix in (
            ("DashboardPeople", "people"),
            ("DashboardCashflow", "cashflow"),
            ("DashboardProperties", "property-summaries"),
            ("DashboardRetirement", "retirement-accounts"),
            ("DashboardScenarios", "scenarios"),
            ("DashboardTimeline", "timeline"),
        ):
            configuration = actions[name]["actionConfiguration"]
            self.assertIn("appsmith.store.householdId", configuration["path"])
            self.assertIn(suffix, configuration["path"])
            self.assertIn("/health/live", configuration["path"])
            self.assertEqual(actions[name]["runBehaviour"], "ON_PAGE_LOAD")

        home = next(
            page
            for page in self.application["pageList"]
            if page["unpublishedPage"]["name"] == "Home"
        )
        widgets = home["unpublishedPage"]["layouts"][0]["dsl"]["children"]
        by_name = {widget["widgetName"]: widget for widget in widgets}
        self.assertIn(
            "DashboardCashflow.data?.monthly_surplus",
            by_name["DashboardMonthlySurplus"]["text"],
        )
        self.assertIn(
            "DashboardCashflow.data?.monthly_expenses",
            by_name["DashboardMonthlyExpenses"]["text"],
        )
        self.assertIn(
            "DashboardProperties.data",
            by_name["DashboardPropertiesTable"]["tableData"],
        )
        self.assertIn(
            "DashboardTimeline.data?.events",
            by_name["DashboardTimelineTable"]["tableData"],
        )
        source = EXPORT.read_text(encoding="utf-8")
        self.assertNotIn("monthly_surplus:", source)

    def test_cashflow_actions_are_household_scoped_and_backend_calculated(self) -> None:
        actions = {
            item["unpublishedAction"]["name"]: item["unpublishedAction"]
            for item in self.application["actionList"]
        }
        self.assertEqual(
            actions["ListExpenseTypes"]["actionConfiguration"]["path"],
            "/api/v1/lookups/household_expense_type",
        )
        for name, method in (("ListExpenses", "GET"), ("CreateExpense", "POST")):
            action = actions[name]
            self.assertEqual(
                action["actionConfiguration"]["path"],
                "/api/v1/households/{{appsmith.store.householdId}}/expenses",
            )
            self.assertEqual(action["actionConfiguration"]["httpMethod"], method)
            self.assertIn("appsmith.store.householdId", action["jsonPathKeys"])
        review = actions["ReviewCashflow"]
        self.assertEqual(review["actionConfiguration"]["httpMethod"], "GET")
        self.assertEqual(
            review["actionConfiguration"]["path"],
            "/api/v1/households/{{appsmith.store.householdId}}/cashflow",
        )
        self.assertEqual(
            review["actionConfiguration"]["queryParameters"],
            [{"key": "as_of", "value": "{{CashflowAsOf.text}}"}],
        )
        self.assertIn("CashflowAsOf.text", review["jsonPathKeys"])

    def test_expense_form_uses_lookups_and_explicit_material_values(self) -> None:
        action = next(
            item["unpublishedAction"]
            for item in self.application["actionList"]
            if item["unpublishedAction"]["name"] == "CreateExpense"
        )
        body = action["actionConfiguration"]["body"]
        for widget_name in (
            "ExpenseCategory",
            "ExpensePerson",
            "ExpenseName",
            "ExpenseAmount",
            "ExpenseFrequency",
            "ExpenseGrowthRate",
            "ExpenseEssential",
            "ExpenseNotes",
            "ExpenseEffectiveFrom",
            "ExpenseEffectiveTo",
        ):
            self.assertIn(widget_name, body)
        self.assertNotIn("category_id: '", body)
        self.assertNotIn("amount: 0", body)
        self.assertNotIn("frequency: '", body)

        page = next(
            page
            for page in self.application["pageList"]
            if page["unpublishedPage"]["name"] == "Cash flow"
        )
        widgets = page["unpublishedPage"]["layouts"][0]["dsl"]["children"]
        create = next(widget for widget in widgets if widget["widgetName"] == "CreateExpenseButton")
        for required in (
            "appsmith.store.householdId",
            "ExpenseCategory.selectedOptionValue",
            "ExpenseAmount.text",
            "ExpenseFrequency.selectedOptionValue",
            "ExpenseEffectiveFrom.text",
        ):
            self.assertIn(required, create["isDisabled"])
        self.assertIn("resetWidget('ExpenseName'", create["onClick"])

    def test_cashflow_page_has_progressive_non_overlapping_sections(self) -> None:
        page = next(
            page
            for page in self.application["pageList"]
            if page["unpublishedPage"]["name"] == "Cash flow"
        )
        widgets = page["unpublishedPage"]["layouts"][0]["dsl"]["children"]
        names = {widget["widgetName"] for widget in widgets}
        self.assertIn("ShowExpensesSectionButton", names)
        self.assertIn("ShowSummarySectionButton", names)
        self.assertNotIn("SelectHousehold", names)
        expense = [
            widget
            for widget in widgets
            if "cashflowSection || 'EXPENSES'" in str(widget.get("isVisible", ""))
        ]
        summary = [
            widget
            for widget in widgets
            if "cashflowSection === 'SUMMARY'" in str(widget.get("isVisible", ""))
        ]
        self.assertTrue(expense)
        self.assertTrue(summary)
        self.assertLess(
            max(widget["bottomRow"] for widget in expense),
            min(widget["topRow"] for widget in summary),
        )

    def test_expense_and_projection_tables_use_friendly_values_and_distinct_columns(self) -> None:
        page = next(
            page
            for page in self.application["pageList"]
            if page["unpublishedPage"]["name"] == "Cash flow"
        )
        widgets = page["unpublishedPage"]["layouts"][0]["dsl"]["children"]
        expenses = next(widget for widget in widgets if widget["widgetName"] == "ExpensesTable")
        people = next(widget for widget in widgets if widget["widgetName"] == "PeopleCashflowTable")
        self.assertIn("Whole household", expenses["tableData"])
        self.assertIn("Fortnightly", expenses["tableData"])
        self.assertIn("Essential", expenses["tableData"])
        self.assertIn("No tax settings", people["tableData"])
        for table in (expenses, people):
            aliases = []
            for key in table["columnOrder"]:
                column = table["primaryColumns"][key]
                self.assertEqual(column["id"], key)
                self.assertEqual(column["originalId"], key)
                self.assertEqual(column["alias"], key)
                aliases.append(column["alias"])
            self.assertEqual(len(aliases), len(set(aliases)))

    def test_cashflow_summary_displays_backend_metrics_currency_and_warnings(self) -> None:
        page = next(
            page
            for page in self.application["pageList"]
            if page["unpublishedPage"]["name"] == "Cash flow"
        )
        widgets = page["unpublishedPage"]["layouts"][0]["dsl"]["children"]
        by_name = {widget["widgetName"]: widget for widget in widgets}
        for name, field in (
            ("AnnualNetMetric", "annual_net_income"),
            ("AnnualExpensesMetric", "annual_expenses"),
            ("AnnualOrdinaryExpensesMetric", "annual_ordinary_expenses"),
            ("AnnualLoanRepaymentsMetric", "annual_loan_repayments"),
            ("AnnualSurplusMetric", "annual_surplus"),
            ("MonthlyNetMetric", "monthly_net_income"),
            ("MonthlyOrdinaryExpensesMetric", "monthly_ordinary_expenses"),
            ("MonthlyLoanRepaymentsMetric", "monthly_loan_repayments"),
            ("MonthlyExpensesMetric", "monthly_expenses"),
            ("MonthlySurplusMetric", "monthly_surplus"),
        ):
            self.assertIn(f"ReviewCashflow.data?.{field}", by_name[name]["text"])
            self.assertIn("ReviewCashflow.data?.currency", by_name[name]["text"])
        self.assertIn("ReviewCashflow.data?.warnings", by_name["CashflowWarnings"]["text"])
        repayments = by_name["LoanRepaymentsTable"]
        self.assertIn("ReviewCashflow.data?.loan_repayments", repayments["tableData"])
        self.assertIn("Shared household cash flow", repayments["tableData"])

    def test_cashflow_navigation_requires_household_without_duplicate_navigation(self) -> None:
        for page in self.application["pageList"]:
            widgets = page["unpublishedPage"]["layouts"][0]["dsl"]["children"]
            cashflow = next(widget for widget in widgets if widget["widgetName"] == "NavCashflow")
            properties = next(
                widget for widget in widgets if widget["widgetName"] == "NavProperties"
            )
            retirement = next(
                widget for widget in widgets if widget["widgetName"] == "NavRetirement"
            )
            timeline = next(
                widget for widget in widgets if widget["widgetName"] == "NavTimeline"
            )
            scenarios = next(
                widget for widget in widgets if widget["widgetName"] == "NavScenarios"
            )
            self.assertIn("!appsmith.store.householdId", cashflow["isDisabled"])
            self.assertIn("!appsmith.store.householdId", properties["isDisabled"])
            self.assertIn("!appsmith.store.householdId", retirement["isDisabled"])
            self.assertIn("!appsmith.store.householdId", timeline["isDisabled"])
            self.assertIn("!appsmith.store.householdId", scenarios["isDisabled"])
            navigation = [widget for widget in widgets if widget["widgetName"].startswith("Nav")]
            self.assertEqual(
                [widget["widgetName"] for widget in navigation],
                [
                    "NavHome",
                    "NavHouseholds",
                    "NavPeople",
                    "NavPersonfinances",
                    "NavCashflow",
                    "NavProperties",
                    "NavRetirement",
                    "NavTimeline",
                    "NavScenarios",
                    "NavSettings",
                ],
            )

    def test_scenario_actions_persist_templates_custom_scenarios_and_overrides(self) -> None:
        actions = {
            item["unpublishedAction"]["name"]: item["unpublishedAction"]
            for item in self.application["actionList"]
        }
        expected = {
            "ListScenarioTemplates": ("GET", "/api/v1/scenario-templates"),
            "ListScenarios": (
                "GET",
                "/api/v1/households/{{appsmith.store.householdId}}/scenarios",
            ),
            "CreateCustomScenario": (
                "POST",
                "/api/v1/households/{{appsmith.store.householdId}}/scenarios",
            ),
            "CreateScenarioFromTemplate": (
                "POST",
                "/api/v1/households/{{appsmith.store.householdId}}/scenarios/from-template",
            ),
            "GetScenario": (
                "GET",
                "/api/v1/scenarios/{{appsmith.store.scenarioId || ''}}",
            ),
            "AddScenarioOverride": (
                "POST",
                "/api/v1/scenarios/{{appsmith.store.scenarioId || ''}}/overrides",
            ),
        }
        for name, (method, path) in expected.items():
            action = actions[name]
            self.assertEqual(action["actionConfiguration"]["httpMethod"], method)
            self.assertEqual(action["actionConfiguration"]["path"], path)

        custom = actions["CreateCustomScenario"]["actionConfiguration"]["body"]
        self.assertIn("ScenarioBase.selectedOptionValue", custom)
        self.assertIn("overrides: []", custom)
        override = actions["AddScenarioOverride"]["actionConfiguration"]["body"]
        self.assertIn("target_entity_type: 'METRIC'", override)
        self.assertIn("ScenarioOverrideOperation.selectedOptionValue", override)

    def test_scenario_page_discovers_neutral_templates_and_saves_for_later(self) -> None:
        page = next(
            page
            for page in self.application["pageList"]
            if page["unpublishedPage"]["name"] == "Scenarios"
        )
        widgets = page["unpublishedPage"]["layouts"][0]["dsl"]["children"]
        by_name = {widget["widgetName"]: widget for widget in widgets}
        template = by_name["ScenarioTemplate"]
        self.assertIn("ListScenarioTemplates.data", template["sourceData"])
        self.assertIn("target_entity_type === 'METRIC'", template["sourceData"])
        self.assertNotIn("Australia", template["sourceData"])
        self.assertNotIn("AUSTRALIA", template["sourceData"])
        self.assertIn("ListScenarios.data", by_name["ScenariosTable"]["tableData"])
        self.assertIn(
            "storeValue('scenarioId'",
            by_name["ManageScenarioButton"]["onClick"],
        )
        self.assertIn("selectedRow?.id", by_name["ManageScenarioButton"]["onClick"])
        for household_action in ("CreateHouseholdButton", "UseHouseholdButton"):
            households = next(
                item
                for item in self.application["pageList"]
                if item["unpublishedPage"]["name"] == "Households"
            )
            household_widgets = households["unpublishedPage"]["layouts"][0]["dsl"][
                "children"
            ]
            widget = next(
                item for item in household_widgets if item["widgetName"] == household_action
            )
            self.assertIn("removeValue('scenarioId')", widget["onClick"])

    def test_scenario_calculation_and_comparison_use_baseline_without_mutating_data(
        self,
    ) -> None:
        actions = {
            item["unpublishedAction"]["name"]: item["unpublishedAction"]
            for item in self.application["actionList"]
        }
        calculate = actions["CalculateScenario"]["actionConfiguration"]
        self.assertEqual(
            calculate["path"],
            "/api/v1/scenarios/{{appsmith.store.scenarioId || ''}}/calculate",
        )
        compare = actions["CompareScenarios"]["actionConfiguration"]
        self.assertEqual(compare["path"], "/api/v1/scenarios/compare")
        for body in (calculate["body"], compare["body"]):
            self.assertIn("baseline_metrics", body)
            self.assertIn("scenarioAdvancedMode", body)
            self.assertIn("JSON.parse(ScenarioBaselineJson.text", body)
        self.assertIn("scenario_ids", compare["body"])

        page = next(
            page
            for page in self.application["pageList"]
            if page["unpublishedPage"]["name"] == "Scenarios"
        )
        widgets = page["unpublishedPage"]["layouts"][0]["dsl"]["children"]
        by_name = {widget["widgetName"]: widget for widget in widgets}
        self.assertIn(
            "scenarioAdvancedMode",
            by_name["ScenarioBaselineJson"]["isVisible"],
        )
        self.assertIn(
            "Current baseline",
            by_name["ScenarioComparisonTable"]["tableData"],
        )

    def test_scenario_progressive_sections_do_not_overlap_in_edit_mode(self) -> None:
        page = next(
            page
            for page in self.application["pageList"]
            if page["unpublishedPage"]["name"] == "Scenarios"
        )
        widgets = page["unpublishedPage"]["layouts"][0]["dsl"]["children"]
        by_name = {widget["widgetName"]: widget for widget in widgets}

        assumption_bottom = by_name["ScenarioOverridesTable"]["bottomRow"]
        calculation_widgets = (
            "ScenarioCalculationHelp",
            "ScenarioAsOf",
            "ScenarioBaselineKey",
            "ScenarioBaselineValue",
            "ToggleScenarioAdvancedButton",
            "ScenarioBaselineJson",
            "CalculateScenarioButton",
            "ScenarioCalculationResult",
        )
        self.assertTrue(
            all(by_name[name]["topRow"] > assumption_bottom for name in calculation_widgets)
        )

        calculation_bottom = by_name["ScenarioCalculationResult"]["bottomRow"]
        comparison_widgets = (
            "ComparisonScenario",
            "CompareScenariosButton",
            "ScenarioComparisonTable",
        )
        self.assertTrue(
            all(by_name[name]["topRow"] > calculation_bottom for name in comparison_widgets)
        )

    def test_property_actions_use_lookups_and_household_scoped_wizard(self) -> None:
        actions = {
            item["unpublishedAction"]["name"]: item["unpublishedAction"]
            for item in self.application["actionList"]
        }
        self.assertEqual(
            actions["ListPropertyTypes"]["actionConfiguration"]["path"],
            "/api/v1/lookups/property_type",
        )
        self.assertEqual(
            actions["ListPropertyStatuses"]["actionConfiguration"]["path"],
            "/api/v1/lookups/property_status",
        )
        self.assertEqual(
            actions["ListPropertySummaries"]["actionConfiguration"]["path"],
            "/api/v1/households/{{appsmith.store.householdId}}/property-summaries",
        )
        create = actions["CreatePropertySetup"]
        self.assertEqual(
            create["actionConfiguration"]["path"],
            "/api/v1/households/{{appsmith.store.householdId}}/properties/wizard",
        )
        body = create["actionConfiguration"]["body"]
        for value in (
            "CURRENT_SNAPSHOT",
            "HISTORICAL_PURCHASE",
            "PropertyCurrentValue.text",
            "PropertyTotalDebt.text",
            "PropertyPurchaseDate.text",
            "PropertyPurchasePrice.text",
        ):
            self.assertIn(value, body)
        self.assertNotIn("default_currency", body)
        self.assertNotIn("loan_balance_total: 0", body)

    def test_property_setup_is_progressive_and_material_values_are_explicit(self) -> None:
        page = next(
            page
            for page in self.application["pageList"]
            if page["unpublishedPage"]["name"] == "Properties"
        )
        widgets = page["unpublishedPage"]["layouts"][0]["dsl"]["children"]
        by_name = {widget["widgetName"]: widget for widget in widgets}
        self.assertIn("ShowPropertyListButton", by_name)
        self.assertIn("ShowPropertySetupButton", by_name)
        self.assertNotIn("SelectHousehold", by_name)
        self.assertIn("does not mean the property is debt-free", by_name["PropertySetupHelp"]["text"])
        disabled = by_name["CreatePropertyButton"]["isDisabled"]
        for required in (
            "appsmith.store.householdId",
            "PropertySetupMode.selectedOptionValue",
            "PropertyName.text",
            "PropertyType.selectedOptionValue",
            "PropertyStatus.selectedOptionValue",
            "PropertyCurrentValue.text",
            "PropertyTotalDebt.text",
            "PropertyPurchaseDate.text",
            "PropertyPurchasePrice.text",
        ):
            self.assertIn(required, disabled)
        list_widgets = [
            widget
            for widget in widgets
            if "propertySection || 'LIST'" in str(widget.get("isVisible", ""))
        ]
        setup_widgets = [
            widget
            for widget in widgets
            if "propertySection === 'SETUP'" in str(widget.get("isVisible", ""))
        ]
        self.assertLess(
            max(widget["bottomRow"] for widget in list_widgets),
            min(widget["topRow"] for widget in setup_widgets),
        )

    def test_property_summary_exposes_debt_without_inventing_missing_values(self) -> None:
        page = next(
            page
            for page in self.application["pageList"]
            if page["unpublishedPage"]["name"] == "Properties"
        )
        widgets = page["unpublishedPage"]["layouts"][0]["dsl"]["children"]
        table = next(widget for widget in widgets if widget["widgetName"] == "PropertiesTable")
        self.assertIn("total_property_debt", table["tableData"])
        self.assertIn("Not recorded", table["tableData"])
        self.assertEqual(
            table["primaryColumns"]["total_debt_display"]["label"],
            "Total property debt",
        )
        aliases = [
            table["primaryColumns"][key]["alias"] for key in table["columnOrder"]
        ]
        self.assertEqual(len(aliases), len(set(aliases)))

    def test_ownership_actions_are_selected_property_scoped(self) -> None:
        actions = {
            item["unpublishedAction"]["name"]: item["unpublishedAction"]
            for item in self.application["actionList"]
        }
        for name, method in (
            ("ListPropertyOwnership", "GET"),
            ("CreatePropertyOwnership", "POST"),
        ):
            action = actions[name]
            self.assertEqual(
                action["actionConfiguration"]["path"],
                "/api/v1/properties/{{appsmith.store.propertyId}}/ownership",
            )
            self.assertEqual(action["actionConfiguration"]["httpMethod"], method)
        body = actions["CreatePropertyOwnership"]["actionConfiguration"]["body"]
        for widget in (
            "OwnershipType",
            "OwnershipPerson",
            "OwnershipExternalName",
            "OwnershipPercentage",
            "OwnershipEffectiveFrom",
            "OwnershipEffectiveTo",
            "OwnershipNotes",
        ):
            self.assertIn(widget, body)

    def test_ownership_form_is_dated_and_shows_api_warnings(self) -> None:
        page = next(
            page
            for page in self.application["pageList"]
            if page["unpublishedPage"]["name"] == "Properties"
        )
        widgets = page["unpublishedPage"]["layouts"][0]["dsl"]["children"]
        by_name = {widget["widgetName"]: widget for widget in widgets}
        create = by_name["CreateOwnershipButton"]
        for required in (
            "appsmith.store.propertyId",
            "OwnershipType.selectedOptionValue",
            "OwnershipPercentage.text",
            "OwnershipEffectiveFrom.text",
        ):
            self.assertIn(required, create["isDisabled"])
        self.assertIn("CreatePropertyOwnership.data?.warnings", create["onClick"])
        self.assertIn("ListPropertyOwnership.run()", create["onClick"])
        self.assertIn("Whole household", by_name["OwnershipTable"]["tableData"])

    def test_loan_actions_support_multiple_property_linked_records(self) -> None:
        actions = {
            item["unpublishedAction"]["name"]: item["unpublishedAction"]
            for item in self.application["actionList"]
        }
        self.assertEqual(
            actions["ListLoanTypes"]["actionConfiguration"]["path"],
            "/api/v1/lookups/loan_type",
        )
        self.assertEqual(
            actions["ListPropertyLoans"]["actionConfiguration"]["path"],
            "/api/v1/households/{{appsmith.store.householdId}}/loans",
        )
        create = actions["CreatePropertyLoan"]
        self.assertEqual(
            create["actionConfiguration"]["path"],
            "/api/v1/households/{{appsmith.store.householdId}}/loans",
        )
        body = create["actionConfiguration"]["body"]
        for value in (
            "property_id: appsmith.store.propertyId",
            "LoanType.selectedOptionValue",
            "LoanOpeningBalance.text",
            "LoanOpeningDate.text",
            "LoanInterestRate.text",
            "LoanRepaymentFrequency.selectedOptionValue",
            "LoanInterestMethod.selectedOptionValue",
            "LoanInterestOnly.selectedOptionValue",
        ):
            self.assertIn(value, body)
        self.assertNotIn("currency:", body)
        self.assertNotIn("term_months: 360", body)

    def test_loan_form_has_explicit_no_one_or_many_semantics(self) -> None:
        page = next(
            page
            for page in self.application["pageList"]
            if page["unpublishedPage"]["name"] == "Properties"
        )
        widgets = page["unpublishedPage"]["layouts"][0]["dsl"]["children"]
        by_name = {widget["widgetName"]: widget for widget in widgets}
        self.assertIn("no loan, one loan, or several", by_name["LoansHelp"]["text"])
        self.assertIn("debt-free property", by_name["LoansEmptyState"]["text"])
        self.assertIn("property_id === appsmith.store.propertyId", by_name["LoansTable"]["tableData"])
        create = by_name["CreateLoanButton"]
        for required in (
            "appsmith.store.propertyId",
            "LoanType.selectedOptionValue",
            "LoanName.text",
            "LoanOpeningBalance.text",
            "LoanOpeningDate.text",
            "LoanInterestRate.text",
            "LoanRepaymentFrequency.selectedOptionValue",
            "LoanInterestMethod.selectedOptionValue",
            "LoanInterestOnly.selectedOptionValue",
        ):
            self.assertIn(required, create["isDisabled"])
        self.assertIn("ListPropertyLoans.run()", create["onClick"])

    def test_advanced_loan_responsibility_is_optional_dated_attribution(self) -> None:
        actions = {
            item["unpublishedAction"]["name"]: item["unpublishedAction"]
            for item in self.application["actionList"]
        }
        for name, method in (
            ("ListLoanResponsibilities", "GET"),
            ("CreateLoanResponsibility", "POST"),
        ):
            action = actions[name]
            self.assertEqual(
                action["actionConfiguration"]["path"],
                "/api/v1/loans/{{appsmith.store.loanId}}/repayment-responsibilities",
            )
            self.assertEqual(action["actionConfiguration"]["httpMethod"], method)
        body = actions["CreateLoanResponsibility"]["actionConfiguration"]["body"]
        for widget in (
            "LoanResponsiblePerson",
            "LoanResponsibilityPercentage",
            "LoanResponsibilityFrom",
            "LoanResponsibilityTo",
            "LoanResponsibilityNotes",
        ):
            self.assertIn(widget, body)

        page = next(
            page
            for page in self.application["pageList"]
            if page["unpublishedPage"]["name"] == "Properties"
        )
        widgets = page["unpublishedPage"]["layouts"][0]["dsl"]["children"]
        by_name = {widget["widgetName"]: widget for widget in widgets}
        self.assertEqual(
            by_name["ManageLoanResponsibilityButton"]["text"],
            "Advanced repayment responsibility",
        )
        help_text = by_name["LoanResponsibilityHelp"]["text"]
        self.assertIn("does not change or duplicate", help_text)
        self.assertIn("newer effective date replaces", help_text)
        create = by_name["CreateLoanResponsibilityButton"]
        self.assertIn("CreateLoanResponsibility.data?.warnings", create["onClick"])
        self.assertIn("appsmith.store.loanId", create["isDisabled"])

    def test_property_workflow_sections_do_not_overlap_in_edit_mode(self) -> None:
        page = next(
            page
            for page in self.application["pageList"]
            if page["unpublishedPage"]["name"] == "Properties"
        )
        widgets = page["unpublishedPage"]["layouts"][0]["dsl"]["children"]
        section_markers = (
            "propertySection || 'LIST'",
            "propertySection === 'SETUP'",
            "propertySection === 'OWNERSHIP'",
            "propertySection === 'LOANS'",
        )
        sections = [
            [
                widget
                for widget in widgets
                if marker in str(widget.get("isVisible", ""))
            ]
            for marker in section_markers
        ]
        self.assertTrue(all(sections))
        for earlier, later in zip(sections, sections[1:]):
            self.assertLess(
                max(widget["bottomRow"] for widget in earlier),
                min(widget["topRow"] for widget in later),
            )

    def test_property_change_clears_selected_person_and_property_context(self) -> None:
        page = next(
            page
            for page in self.application["pageList"]
            if page["unpublishedPage"]["name"] == "Households"
        )
        widgets = page["unpublishedPage"]["layouts"][0]["dsl"]["children"]
        for button_name in ("CreateHouseholdButton", "UseHouseholdButton"):
            on_click = next(
                widget["onClick"] for widget in widgets if widget["widgetName"] == button_name
            )
            self.assertIn("removeValue('propertyId')", on_click)
            self.assertIn("removeValue('propertyName')", on_click)


if __name__ == "__main__":
    unittest.main()
