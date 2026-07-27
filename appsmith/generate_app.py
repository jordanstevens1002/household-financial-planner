"""Generate the importable Appsmith application used by Phase 10."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

OUTPUT = Path(__file__).with_name("household-financial-planner.json")
API_URL = "http://api:8000"
PAGES = (("Home", "home"), ("Settings", "settings"))


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


def common_widgets(page_name: str) -> list[dict[str, Any]]:
    widgets = [
        text("PageTitle", page_name, 1, 6),
        text(
            "FoundationNotice",
            "Phase 10A provides the tested application shell and connection settings. Household workflows arrive in the next focused PR.",
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
    if name == "Home":
        widgets += [
            text("Welcome", "Open Settings to configure a local development identity or production bearer token, then verify the API connection.", 17, 24),
            button("OpenSettings", "Open settings", "{{navigateTo('Settings')}}", 26, 2, 18),
        ]
    else:
        widgets += [
            text("SettingsHelp", "Connection details stay in the current browser session and are never included in the export.", 17, 21),
            input_widget("BearerToken", "Bearer token (production)", 22, 2, 62),
            input_widget("DevelopmentSubject", "Development subject (local testing only)", 30, 2, 32),
            button("SaveSettings", "Save connection", "{{storeValue('apiToken', BearerToken.text || '', false); storeValue('developmentSubject', DevelopmentSubject.text || '', false); showAlert('Connection saved for this session', 'success')}}", 39, 2, 20),
            button("TestConnection", "Test API connection", "{{HealthCheck.run(() => showAlert('API connection is ready', 'success'), () => showAlert('Could not reach the API', 'error'))}}", 39, 22, 42),
            text("ConnectionStatus", "API status: {{HealthCheck.data.status || 'not checked'}}", 46, 51),
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
    return [action("Settings", "HealthCheck", "GET", "/health/ready", on_load=True)]


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
        "publishedDefaultPageName": "Home",
        "unpublishedDefaultPageName": "Home",
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
