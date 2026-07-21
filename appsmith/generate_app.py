"""Generate the importable Appsmith application used by Phase 10."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

OUTPUT = Path(__file__).with_name("household-financial-planner.json")
API_URL = "http://api:8000"
PAGES = (
    ("Onboarding", "onboarding"),
    ("Dashboard", "dashboard"),
    ("People", "people"),
    ("Properties", "properties"),
    ("Property Wizard", "property-wizard"),
    ("Timeline", "timeline"),
    ("Scenarios", "scenarios"),
    ("Settings", "settings"),
)


def text(name: str, value: str, top: int, bottom: int, left: int = 2, right: int = 62) -> dict[str, Any]:
    return {
        "widgetName": name,
        "displayName": "Text",
        "type": "TEXT_WIDGET",
        "widgetId": name.lower(),
        "parentId": "0",
        "topRow": top,
        "bottomRow": bottom,
        "leftColumn": left,
        "rightColumn": right,
        "text": value,
        "isVisible": True,
        "isLoading": False,
        "renderMode": "CANVAS",
        "version": 1,
        "fontFamily": "{{appsmith.theme.fontFamily.appFont}}",
        "fontSize": "1rem",
        "textAlign": "LEFT",
        "textColor": "#172B4D",
        "fontStyle": "",
        "overflow": "NONE",
        "shouldTruncate": False,
        "animateLoading": True,
        "dynamicBindingPathList": [{"key": "fontFamily"}, {"key": "text"}],
        "dynamicTriggerPathList": [],
    }


def button(
    name: str,
    label: str,
    on_click: str,
    top: int,
    left: int,
    right: int,
    *,
    disabled: bool | str = False,
) -> dict[str, Any]:
    bindings = [{"key": "buttonColor"}, {"key": "borderRadius"}]
    if isinstance(disabled, str):
        bindings.append({"key": "isDisabled"})
    return {
        "widgetName": name,
        "displayName": "Button",
        "type": "BUTTON_WIDGET",
        "widgetId": name.lower(),
        "parentId": "0",
        "topRow": top,
        "bottomRow": top + 4,
        "leftColumn": left,
        "rightColumn": right,
        "text": label,
        "onClick": on_click,
        "isVisible": True,
        "isDisabled": disabled,
        "isLoading": False,
        "renderMode": "CANVAS",
        "version": 1,
        "buttonVariant": "PRIMARY",
        "buttonColor": "{{appsmith.theme.colors.primaryColor}}",
        "borderRadius": "{{appsmith.theme.borderRadius.appBorderRadius}}",
        "animateLoading": True,
        "responsiveBehavior": "hug",
        "dynamicBindingPathList": bindings,
        "dynamicTriggerPathList": [{"key": "onClick"}],
    }


def input_widget(
    name: str,
    label: str,
    top: int,
    left: int,
    right: int,
    *,
    required: bool | str = False,
    visible: bool | str = True,
) -> dict[str, Any]:
    bindings = [{"key": "borderRadius"}]
    if isinstance(required, str):
        bindings.append({"key": "isRequired"})
    if isinstance(visible, str):
        bindings.append({"key": "isVisible"})
    return {
        "widgetName": name,
        "displayName": "Input",
        "type": "INPUT_WIDGET_V2",
        "widgetId": name.lower(),
        "parentId": "0",
        "topRow": top,
        "bottomRow": top + 7,
        "leftColumn": left,
        "rightColumn": right,
        "label": label,
        "labelPosition": "Top",
        "defaultText": "",
        "placeholderText": label,
        "inputType": "TEXT",
        "isRequired": required,
        "isVisible": visible,
        "isDisabled": False,
        "isLoading": False,
        "renderMode": "CANVAS",
        "version": 2,
        "borderRadius": "{{appsmith.theme.borderRadius.appBorderRadius}}",
        "dynamicBindingPathList": bindings,
        "dynamicTriggerPathList": [],
    }


def select_widget(
    name: str,
    label: str,
    options: str,
    top: int,
    left: int,
    right: int,
    *,
    default: str = "",
) -> dict[str, Any]:
    return {
        "widgetName": name,
        "displayName": "Select",
        "type": "SELECT_WIDGET",
        "widgetId": name.lower(),
        "parentId": "0",
        "topRow": top,
        "bottomRow": top + 7,
        "leftColumn": left,
        "rightColumn": right,
        "labelText": label,
        "options": options,
        "defaultOptionValue": default,
        "placeholderText": f"Choose {label.lower()}",
        "isVisible": True,
        "isDisabled": False,
        "isLoading": False,
        "renderMode": "CANVAS",
        "version": 1,
        "dynamicBindingPathList": [{"key": "options"}, {"key": "defaultOptionValue"}],
        "dynamicTriggerPathList": [],
    }


def table(name: str, data: str, top: int = 22, bottom: int = 55) -> dict[str, Any]:
    return {
        "widgetName": name,
        "displayName": "Table",
        "type": "TABLE_WIDGET_V2",
        "widgetId": name.lower(),
        "parentId": "0",
        "topRow": top,
        "bottomRow": bottom,
        "leftColumn": 2,
        "rightColumn": 62,
        "tableData": data,
        "isVisible": True,
        "isLoading": False,
        "renderMode": "CANVAS",
        "version": 2,
        "searchKey": "",
        "primaryColumns": {},
        "dynamicBindingPathList": [{"key": "tableData"}],
        "dynamicTriggerPathList": [],
    }


def common_widgets(page_name: str) -> list[dict[str, Any]]:
    widgets = [
        text("PageTitle", page_name, 1, 6),
        text(
            "HouseholdContext",
            "{{appsmith.store.householdName || 'Choose or create a household to begin'}}",
            6,
            10,
        ),
    ]
    for index, (name, _) in enumerate(PAGES):
        widgets.append(
            button(
                f"Nav{name.replace(' ', '')}",
                name,
                f"{{{{navigateTo('{name}', {{}}, 'SAME_WINDOW')}}}}",
                11,
                index * 8,
                (index + 1) * 8,
            )
        )
    return widgets


def page_widgets(name: str) -> list[dict[str, Any]]:
    widgets = common_widgets(name)
    if name == "Onboarding":
        widgets += [
            text("Welcome", "Set up the household you want to explore. Nothing is assumed or created automatically.", 17, 21),
            input_widget("HouseholdName", "Household name", 22, 2, 32, required=True),
            input_widget("HouseholdCurrency", "Currency code (for example AUD or USD)", 22, 33, 47, required=True),
            input_widget("HouseholdJurisdiction", "Jurisdiction code", 22, 48, 62, required=True),
            button(
                "CreateHouseholdButton",
                "Create household",
                "{{CreateHousehold.run(() => { storeValue('householdId', CreateHousehold.data.id); storeValue('householdName', CreateHousehold.data.display_name); navigateTo('People'); }, () => showAlert(CreateHousehold.data.detail || 'Could not create household', 'error'))}}",
                31,
                2,
                20,
                disabled="{{!(HouseholdName.text || '').trim() || !(HouseholdCurrency.text || '').trim() || !(HouseholdJurisdiction.text || '').trim()}}",
            ),
            text("ExistingHouseholdsLabel", "Or continue with an existing household", 38, 42),
            table("ExistingHouseholds", "{{ListHouseholds.data}}", 43, 68),
            button(
                "UseHouseholdButton",
                "Use selected household",
                "{{storeValue('householdId', ExistingHouseholds.selectedRow?.id); storeValue('householdName', ExistingHouseholds.selectedRow?.display_name); navigateTo('Dashboard')}}",
                70,
                2,
                22,
                disabled="{{!ExistingHouseholds.selectedRow?.id}}",
            ),
        ]
    elif name == "Dashboard":
        widgets += [
            text("DashboardHelp", "A calm overview of the household records already entered. Unknown values stay unknown.", 17, 21),
            text("PeopleCount", "People: {{ListPeople.data.length || 0}}", 22, 27, 2, 20),
            text("PropertyCount", "Properties: {{ListProperties.data.length || 0}}", 22, 27, 22, 40),
            text("ScenarioCount", "Saved scenarios: {{ListScenarios.data.length || 0}}", 22, 27, 42, 62),
            table("RecentTimeline", "{{(ListTimeline.data.events || []).slice(0, 8)}}", 29, 58),
        ]
    elif name == "People":
        widgets += [
            text("PeopleHelp", "Add the people whose finances are part of this household.", 17, 21),
            table("PeopleTable", "{{ListPeople.data}}", 22, 50),
            input_widget("PersonName", "Display name", 52, 2, 32, required=True),
            button("AddPersonButton", "Add person", "{{CreatePerson.run(() => ListPeople.run(), () => showAlert('Could not add person', 'error'))}}", 60, 2, 18, disabled="{{!PersonName.text}}"),
        ]
    elif name == "Properties":
        widgets += [
            text("PropertiesHelp", "Homes and other properties can be owned, rented in part, vacant, planned or historical.", 17, 21),
            table("PropertiesTable", "{{ListProperties.data}}", 22, 55),
            button("OpenPropertyWizard", "Add a property", "{{navigateTo('Property Wizard')}}", 57, 2, 18),
        ]
    elif name == "Property Wizard":
        widgets += [
            text("PropertyWizardHelp", "Record either a current snapshot or a historical purchase. Values and debt are explicit rather than guessed.", 17, 21),
            select_widget("SetupMode", "Starting point", "{{[{label: 'Current snapshot', value: 'CURRENT_SNAPSHOT'}, {label: 'Historical purchase', value: 'HISTORICAL_PURCHASE'}]}}", 22, 2, 22, default="CURRENT_SNAPSHOT"),
            input_widget("PropertyName", "Property name", 22, 23, 43, required=True),
            select_widget("PropertyType", "Property type", "{{ListPropertyTypes.data.map(item => ({label: item.display_name, value: item.id}))}}", 22, 44, 62),
            select_widget("PropertyStatus", "Current status", "{{ListPropertyStatuses.data.map(item => ({label: item.display_name, value: item.id}))}}", 31, 2, 22),
            input_widget("PropertyEffectiveDate", "Snapshot or purchase date (YYYY-MM-DD)", 31, 23, 43, required=True),
            input_widget("PropertyValue", "Property value or purchase price", 31, 44, 62, required=True),
            input_widget(
                "PropertyDebt",
                "Current loan balance (enter 0 only when there is no debt)",
                40,
                2,
                32,
                required="{{SetupMode.selectedOptionValue === 'CURRENT_SNAPSHOT'}}",
                visible="{{SetupMode.selectedOptionValue === 'CURRENT_SNAPSHOT'}}",
            ),
            button("CreatePropertyButton", "Create property", "{{CreateProperty.run(() => navigateTo('Properties'), () => showAlert(CreateProperty.data.detail || 'Could not create property', 'error'))}}", 49, 2, 20, disabled="{{!PropertyName.text || !PropertyType.selectedOptionValue || !PropertyStatus.selectedOptionValue || !PropertyEffectiveDate.text || !PropertyValue.text || (SetupMode.selectedOptionValue === 'CURRENT_SNAPSHOT' && !PropertyDebt.text)}}"),
        ]
    elif name == "Timeline":
        widgets += [
            text("TimelineHelp", "Observed history, plans and projections are labelled so estimates are never presented as facts.", 17, 21),
            table("TimelineTable", "{{ListTimeline.data.events || []}}", 22, 60),
        ]
    elif name == "Scenarios":
        widgets += [
            text("ScenariosHelp", "Saved scenarios are reusable planning layers. Comparing them never rewrites household records.", 17, 21),
            table("ScenariosTable", "{{ListScenarios.data}}", 22, 50),
            input_widget("ScenarioName", "Scenario name", 52, 2, 32, required=True),
            button("CreateScenarioButton", "Save scenario", "{{CreateScenario.run(() => ListScenarios.run(), () => showAlert('Could not save scenario', 'error'))}}", 60, 2, 18, disabled="{{!ScenarioName.text}}"),
        ]
    else:
        widgets += [
            text("SettingsHelp", "Connection details stay in your Appsmith browser store and are not included in exports.", 17, 21),
            input_widget("BearerToken", "Bearer token (production)", 22, 2, 62),
            input_widget("DevelopmentSubject", "Development subject (local testing only)", 30, 2, 32),
            input_widget("SelectedHouseholdId", "Household ID", 38, 2, 32),
            input_widget("SelectedHouseholdName", "Household display name", 38, 33, 62),
            button("SaveSettings", "Save connection", "{{storeValue('apiToken', BearerToken.text, false); storeValue('developmentSubject', DevelopmentSubject.text, false); storeValue('householdId', SelectedHouseholdId.text); storeValue('householdName', SelectedHouseholdName.text); showAlert('Connection saved for this session', 'success')}}", 47, 2, 22),
            table("PropertyTypes", "{{ListPropertyTypes.data}}", 54, 75),
            table("PropertyStatuses", "{{ListPropertyStatuses.data}}", 77, 98),
        ]
    return widgets


def datasource() -> dict[str, Any]:
    return {
        "name": "HouseholdPlannerAPI",
        "pluginId": "restapi-plugin",
        "datasourceConfiguration": {"url": API_URL},
        "isValid": True,
        "invalids": [],
        "messages": [],
        "new": True,
        "userPermissions": [],
    }


def action(page: str, name: str, method: str, path: str, *, body: str = "", on_load: bool = False) -> dict[str, Any]:
    identifier = f"{page.replace(' ', '')}_{name}"
    configuration: dict[str, Any] = {
        "timeoutInMillisecond": 10000,
        "paginationType": "NONE",
        "path": path,
        "headers": [
            {"key": "Authorization", "value": "Bearer {{appsmith.store.apiToken || ''}}"},
            {"key": "X-Development-Subject", "value": "{{appsmith.store.developmentSubject || ''}}"},
            {"key": "Content-Type", "value": "application/json"},
        ],
        "encodeParamsToggle": True,
        "queryParameters": [],
        "bodyFormData": [],
        "httpMethod": method,
        "formData": {"apiContentType": "application/json" if body else "none"},
    }
    if body:
        configuration["body"] = body
    entity = {
        "name": name,
        "validName": name,
        "datasource": datasource(),
        "pageId": page,
        "actionConfiguration": configuration,
        "runBehaviour": "ON_PAGE_LOAD" if on_load else "MANUAL",
        "dynamicBindingPathList": [],
        "isValid": True,
        "invalids": [],
        "messages": [],
        "jsonPathKeys": [],
        "confirmBeforeExecute": False,
        "userPermissions": [],
    }
    return {
        "id": identifier,
        "pluginType": "API",
        "pluginId": "restapi-plugin",
        "unpublishedAction": entity,
        "publishedAction": deepcopy(entity),
        "new": False,
        "userPermissions": ["read:actions", "execute:actions", "manage:actions"],
    }


def actions() -> list[dict[str, Any]]:
    household = "{{appsmith.store.householdId}}"
    return [
        action("Onboarding", "ListHouseholds", "GET", "/api/v1/households", on_load=True),
        action("Onboarding", "CreateHousehold", "POST", "/api/v1/households", body="{{JSON.stringify({display_name: String(HouseholdName.text || '').trim(), currency: String(HouseholdCurrency.text || '').trim().toUpperCase(), jurisdiction: String(HouseholdJurisdiction.text || '').trim().toUpperCase()})}}"),
        action("Dashboard", "ListPeople", "GET", f"/api/v1/households/{household}/people", on_load=True),
        action("Dashboard", "ListProperties", "GET", f"/api/v1/households/{household}/properties", on_load=True),
        action("Dashboard", "ListTimeline", "GET", f"/api/v1/households/{household}/timeline", on_load=True),
        action("Dashboard", "ListScenarios", "GET", f"/api/v1/households/{household}/scenarios", on_load=True),
        action("People", "ListPeople", "GET", f"/api/v1/households/{household}/people", on_load=True),
        action("People", "CreatePerson", "POST", f"/api/v1/households/{household}/people", body="{{JSON.stringify({display_name: PersonName.text, effective_from: new Date().toISOString().slice(0, 10)})}}"),
        action("Properties", "ListProperties", "GET", f"/api/v1/households/{household}/properties", on_load=True),
        action("Property Wizard", "ListPropertyTypes", "GET", "/api/v1/lookups/property_type", on_load=True),
        action("Property Wizard", "ListPropertyStatuses", "GET", "/api/v1/lookups/property_status", on_load=True),
        action("Property Wizard", "CreateProperty", "POST", f"/api/v1/households/{household}/properties/wizard", body="{{JSON.stringify({mode: SetupMode.selectedOptionValue, property: {display_name: PropertyName.text, property_type_id: PropertyType.selectedOptionValue, current_status_id: PropertyStatus.selectedOptionValue, purchase_date: SetupMode.selectedOptionValue === 'HISTORICAL_PURCHASE' ? PropertyEffectiveDate.text : null, purchase_price: SetupMode.selectedOptionValue === 'HISTORICAL_PURCHASE' ? Number(PropertyValue.text) : null}, baseline: SetupMode.selectedOptionValue === 'CURRENT_SNAPSHOT' ? {baseline_date: PropertyEffectiveDate.text, property_value: Number(PropertyValue.text), loan_balance_total: Number(PropertyDebt.text), status_id: PropertyStatus.selectedOptionValue} : null, ownership: []})}}"),
        action("Timeline", "ListTimeline", "GET", f"/api/v1/households/{household}/timeline", on_load=True),
        action("Scenarios", "ListScenarios", "GET", f"/api/v1/households/{household}/scenarios", on_load=True),
        action("Scenarios", "CreateScenario", "POST", f"/api/v1/households/{household}/scenarios", body='{{JSON.stringify({display_name: ScenarioName.text})}}'),
        action("Settings", "ListPropertyTypes", "GET", "/api/v1/lookups/property_type", on_load=True),
        action("Settings", "ListPropertyStatuses", "GET", "/api/v1/lookups/property_status", on_load=True),
    ]


def build() -> dict[str, Any]:
    all_actions = actions()
    pages: list[dict[str, Any]] = []
    for index, (name, slug) in enumerate(PAGES):
        page_actions = [item for item in all_actions if item["unpublishedAction"]["pageId"] == name]
        on_load = [
            {
                "id": item["id"],
                "name": item["unpublishedAction"]["name"],
                "pluginType": "API",
                "confirmBeforeExecute": False,
                "jsonPathKeys": [],
                "timeoutInMillisecond": 10000,
            }
            for item in page_actions
            if item["unpublishedAction"]["runBehaviour"] == "ON_PAGE_LOAD"
        ]
        layout = {
            "id": name,
            "viewMode": False,
            "dsl": {
                "widgetName": "MainContainer",
                "backgroundColor": "#F7F8FA",
                "rightColumn": 1224,
                "snapColumns": 64,
                "detachFromLayout": True,
                "widgetId": "0",
                "topRow": 0,
                "bottomRow": 1100,
                "containerStyle": "none",
                "snapRows": 110,
                "parentRowSpace": 1,
                "type": "CANVAS_WIDGET",
                "canExtend": True,
                "version": 77,
                "minHeight": 1100,
                "parentColumnSpace": 1,
                "dynamicBindingPathList": [],
                "children": page_widgets(name),
            },
            "layoutOnLoadActions": [[item] for item in on_load],
            "layoutOnLoadActionErrors": [],
            "validOnPageLoadActions": True,
            "deleted": False,
            "policies": [],
            "userPermissions": [],
        }
        page = {"name": name, "slug": slug, "layouts": [layout], "userPermissions": [], "policies": []}
        pages.append({"unpublishedPage": page, "publishedPage": deepcopy(page), "deleted": False, "gitSyncId": f"phase10_{index}"})

    page_refs = [{"id": name, "isDefault": index == 0} for index, (name, _) in enumerate(PAGES)]
    return {
        "clientSchemaVersion": 1,
        "serverSchemaVersion": 6,
        "exportedApplication": {
            "name": "Household Financial Planner",
            "isPublic": False,
            "pages": page_refs,
            "publishedPages": deepcopy(page_refs),
            "viewMode": False,
            "appIsExample": False,
            "color": "#36B37E",
            "icon": "home",
            "slug": "household-financial-planner",
            "evaluationVersion": 2,
            "applicationVersion": 2,
            "collapseInvisibleWidgets": True,
            "isManualUpdate": False,
            "deleted": False,
        },
        "datasourceList": [],
        "customJSLibList": [],
        "pageList": pages,
        "pageOrder": [name for name, _ in PAGES],
        "publishedPageOrder": [name for name, _ in PAGES],
        "publishedDefaultPageName": "Onboarding",
        "unpublishedDefaultPageName": "Onboarding",
        "actionList": all_actions,
        "actionCollectionList": [],
        "updatedResources": {"actionList": [item["id"] for item in all_actions], "pageList": [name for name, _ in PAGES], "actionCollectionList": []},
        "editModeTheme": {"name": "Default", "displayName": "Modern", "isSystemTheme": True, "deleted": False},
        "publishedTheme": {"name": "Default", "displayName": "Modern", "isSystemTheme": True, "deleted": False},
    }


def main() -> None:
    OUTPUT.write_text(json.dumps(build(), indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
