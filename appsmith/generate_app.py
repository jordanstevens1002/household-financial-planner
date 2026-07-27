"""Generate the importable Appsmith application used by Phase 10."""

from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

OUTPUT = Path(__file__).with_name("household-financial-planner.json")
API_URL = "http://api:8000"
PAGES = (
    ("Home", "home"),
    ("Households", "households"),
    ("People", "people"),
    ("Person finances", "person-finances"),
    ("Settings", "settings"),
)


def text(
    name: str,
    value: str,
    top: int,
    bottom: int,
    left: int = 2,
    right: int = 62,
    *,
    visible: bool | str = True,
) -> dict[str, Any]:
    bindings = [{"key": "fontFamily"}, {"key": "text"}]
    if isinstance(visible, str):
        bindings.append({"key": "isVisible"})
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
        "isVisible": visible,
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
        "dynamicBindingPathList": bindings,
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
    visible: bool | str = True,
) -> dict[str, Any]:
    bindings = [{"key": "buttonColor"}, {"key": "borderRadius"}]
    if label.startswith("{{"):
        bindings.append({"key": "text"})
    if isinstance(disabled, str):
        bindings.append({"key": "isDisabled"})
    if isinstance(visible, str):
        bindings.append({"key": "isVisible"})
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
        "isVisible": visible,
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
    visible: bool | str = True,
) -> dict[str, Any]:
    bindings = [{"key": "sourceData"}]
    if isinstance(visible, str):
        bindings.append({"key": "isVisible"})
    if default.startswith("{{"):
        bindings.append({"key": "defaultOptionValue"})
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
        "sourceData": options,
        "optionLabel": "label",
        "optionValue": "value",
        "defaultOptionValue": default,
        "placeholderText": f"Choose {label.lower()}",
        "isVisible": visible,
        "isDisabled": False,
        "isLoading": False,
        "renderMode": "CANVAS",
        "version": 1,
        "dynamicBindingPathList": bindings,
        "dynamicTriggerPathList": [],
    }


def table(
    name: str,
    data: str,
    columns: tuple[tuple[str, str, bool], ...],
    top: int,
    bottom: int,
    *,
    label: str,
    visible: bool | str = True,
) -> dict[str, Any]:
    primary_columns = {
        key: {
            "index": index,
            "width": 150,
            "originalId": key,
            "id": key,
            "alias": key,
            "horizontalAlignment": "LEFT",
            "verticalAlignment": "CENTER",
            "columnType": "text",
            "textSize": "PARAGRAPH",
            "enableFilter": True,
            "enableSort": True,
            "isVisible": visible,
            "isDisabled": False,
            "isCellVisible": True,
            "isDerived": False,
            "label": label,
            "computedValue": (
                f'{{{{({name}.tableData || []).map((currentRow) => currentRow["{key}"])}}}}'
            ),
        }
        for index, (key, label, visible) in enumerate(columns)
    }
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
        "isVisible": visible,
        "isLoading": False,
        "renderMode": "CANVAS",
        "version": 3,
        "defaultPageSize": 0,
        "isVisibleDownload": True,
        "isVisibleFilters": True,
        "isVisibleSearch": True,
        "isVisiblePagination": True,
        "label": label,
        "searchKey": "",
        "columnOrder": [key for key, _, _ in columns],
        "primaryColumns": primary_columns,
        "derivedColumns": {},
        "columnSizeMap": {},
        "dynamicBindingPathList": [
            {"key": "tableData"},
            *([{"key": "isVisible"}] if isinstance(visible, str) else []),
            *[{"key": f"primaryColumns.{key}.computedValue"} for key, _, _ in columns],
        ],
        "dynamicTriggerPathList": [],
    }


def common_widgets(page_name: str) -> list[dict[str, Any]]:
    widgets = [
        text("PageTitle", page_name, 1, 6),
        text(
            "HouseholdContext",
            "{{appsmith.store.householdName || 'No household selected'}}",
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
                disabled=(
                    "{{!appsmith.store.personId}}"
                    if name == "Person finances"
                    else False
                ),
            )
        )
    return widgets


def page_widgets(name: str) -> list[dict[str, Any]]:
    widgets = common_widgets(name)
    if name == "Home":
        widgets += [
            text(
                "Welcome",
                "Connect to the API, then create or choose the household you want to explore.",
                17,
                24,
            ),
            text(
                "SelectedHousehold",
                "Current household: {{appsmith.store.householdName || 'none selected'}}",
                25,
                30,
            ),
            button(
                "ContinueSetup",
                "{{appsmith.store.personId ? 'Continue with ' + appsmith.store.personName : appsmith.store.householdId ? 'Add or choose a person' : 'Choose a household'}}",
                "{{navigateTo(appsmith.store.personId ? 'Person finances' : appsmith.store.householdId ? 'People' : 'Households')}}",
                32,
                2,
                26,
            ),
        ]
    elif name == "Households":
        widgets += [
            text(
                "HouseholdHelp",
                "Create a household or select one you already use. Currency is always explicit.",
                17,
                21,
            ),
            input_widget("HouseholdName", "Household name", 22, 2, 30, required=True),
            input_widget(
                "HouseholdCurrency",
                "Currency code (for example AUD or USD)",
                22,
                31,
                47,
                required=True,
            ),
            input_widget("HouseholdJurisdiction", "Jurisdiction (optional)", 22, 48, 62),
            button(
                "CreateHouseholdButton",
                "Create household",
                "{{CreateHousehold.run(async () => { await storeValue('householdId', CreateHousehold.data.id, true); await storeValue('householdName', CreateHousehold.data.display_name, true); await removeValue('personId'); await removeValue('personName'); showAlert('Household created and selected', 'success'); ListHouseholds.run(); navigateTo('Home'); }, () => showAlert(JSON.stringify(CreateHousehold.data?.detail || 'Could not create household'), 'error'))}}",
                31,
                2,
                20,
                disabled="{{!(HouseholdName.text || '').trim() || !/^[A-Za-z]{3}$/.test((HouseholdCurrency.text || '').trim())}}",
            ),
            text("ExistingHouseholdsLabel", "Your households", 38, 42),
            table(
                "ExistingHouseholds",
                "{{Array.isArray(ListHouseholds.data) ? ListHouseholds.data : []}}",
                (
                    ("id", "ID", False),
                    ("display_name", "Household", True),
                    ("currency", "Currency", True),
                    ("jurisdiction", "Jurisdiction", True),
                ),
                43,
                68,
                label="Households",
            ),
            button(
                "UseHouseholdButton",
                "Use selected household",
                "{{(async () => { await storeValue('householdId', ExistingHouseholds.selectedRow.id, true); await storeValue('householdName', ExistingHouseholds.selectedRow.display_name, true); await removeValue('personId'); await removeValue('personName'); showAlert('Household selected', 'success'); navigateTo('Home'); })()}}",
                70,
                2,
                22,
                disabled="{{!ExistingHouseholds.selectedRow || !ExistingHouseholds.selectedRow.id}}",
            ),
            button(
                "RefreshHouseholdsButton",
                "Refresh list",
                "{{ListHouseholds.run()}}",
                70,
                24,
                40,
            ),
        ]
    elif name == "People":
        widgets += [
            text(
                "PeopleHelp",
                "Add the people whose finances may later form part of this household. This records identity only; income, tax and other financial details are not complete yet.",
                17,
                23,
            ),
            text(
                "PeopleHouseholdRequired",
                "{{appsmith.store.householdId ? 'Adding people to ' + appsmith.store.householdName : 'Choose a household before adding people'}}",
                24,
                28,
            ),
            input_widget("PersonDisplayName", "Display name", 29, 2, 24, required=True),
            input_widget("PersonLegalName", "Legal name (optional)", 29, 25, 47),
            input_widget("PersonDateOfBirth", "Date of birth (optional, YYYY-MM-DD)", 29, 48, 62),
            input_widget(
                "PersonResidencyCountry",
                "Tax residency country (optional, two-letter code)",
                38,
                2,
                24,
            ),
            input_widget(
                "PersonTaxJurisdiction",
                "Tax jurisdiction (optional)",
                38,
                25,
                47,
            ),
            input_widget(
                "PersonEffectiveFrom",
                "Effective from (YYYY-MM-DD)",
                38,
                48,
                62,
                required=True,
            ),
            button(
                "CreatePersonButton",
                "Add person",
                "{{CreatePerson.run(() => { showAlert('Person added', 'success'); ListPeople.run(); }, () => showAlert(JSON.stringify(CreatePerson.data?.detail || 'Could not add person'), 'error'))}}",
                47,
                2,
                18,
                disabled="{{!appsmith.store.householdId || !(PersonDisplayName.text || '').trim() || !/^\\d{4}-\\d{2}-\\d{2}$/.test((PersonEffectiveFrom.text || '').trim()) || ((PersonDateOfBirth.text || '').trim() && !/^\\d{4}-\\d{2}-\\d{2}$/.test(PersonDateOfBirth.text.trim())) || ((PersonResidencyCountry.text || '').trim() && !/^[A-Za-z]{2}$/.test(PersonResidencyCountry.text.trim()))}}",
            ),
            button(
                "RefreshPeopleButton",
                "Refresh people",
                "{{ListPeople.run()}}",
                47,
                20,
                36,
                disabled="{{!appsmith.store.householdId}}",
            ),
            text("PeopleListLabel", "People in this household", 54, 58),
            table(
                "ExistingPeople",
                "{{Array.isArray(ListPeople.data) ? ListPeople.data : []}}",
                (
                    ("id", "ID", False),
                    ("display_name", "Display name", True),
                    ("legal_name", "Legal name", True),
                    ("date_of_birth", "Date of birth", True),
                    ("tax_residency_country", "Tax residency", True),
                    ("tax_jurisdiction", "Tax jurisdiction", True),
                    ("is_active", "Active", True),
                    ("effective_from", "Effective from", True),
                ),
                59,
                88,
                label="People",
            ),
            button(
                "ManagePersonFinancesButton",
                "Manage selected person's finances",
                "{{storeValue('personId', ExistingPeople.selectedRow.id, true); storeValue('personName', ExistingPeople.selectedRow.display_name, true); navigateTo('Person finances')}}",
                90,
                2,
                28,
                disabled="{{!ExistingPeople.selectedRow || !ExistingPeople.selectedRow.id}}",
            ),
        ]
    elif name == "Person finances":
        widgets += [
            text(
                "PersonFinanceHelp",
                "Record income and choose either an installed tax provider or a manual annual net-income estimate. Provider-specific settings stay explicit JSON so extensions do not require changes to this page.",
                17,
                24,
            ),
            text(
                "PersonFinanceContext",
                "Person: {{appsmith.store.personName || 'choose a person below'}}",
                25,
                29,
            ),
            button(
                "ChangeFinancePersonButton",
                "Change person",
                "{{navigateTo('People')}}",
                30,
                2,
                14,
            ),
            button(
                "ShowIncomeSectionButton",
                "Income",
                "{{storeValue('financeSection', 'INCOME', false)}}",
                30,
                16,
                28,
            ),
            button(
                "ShowTaxSectionButton",
                "Tax settings",
                "{{storeValue('financeSection', 'TAX', false)}}",
                30,
                30,
                44,
            ),
            button(
                "ToggleAdvancedModeButton",
                "{{appsmith.store.financeAdvancedMode ? 'Leave advanced mode' : 'Advanced mode'}}",
                "{{storeValue('financeAdvancedMode', !appsmith.store.financeAdvancedMode, false)}}",
                30,
                46,
                62,
                visible="{{appsmith.store.financeSection === 'TAX'}}",
            ),
            text(
                "AdvancedModeHelp",
                "Advanced mode exposes raw provider JSON for specialist settings. Most people can leave it off and use the provider defaults.",
                38,
                44,
                visible="{{appsmith.store.financeSection === 'TAX' && appsmith.store.financeAdvancedMode}}",
            ),
            text(
                "IncomeHeading",
                "Income sources",
                47,
                51,
                visible="{{(appsmith.store.financeSection || 'INCOME') === 'INCOME'}}",
            ),
            text(
                "IncomeEmptyState",
                "{{Array.isArray(ListIncomeSources.data) && ListIncomeSources.data.length ? '' : 'No income sources yet. Add the first recurring income below.'}}",
                52,
                56,
                visible="{{(appsmith.store.financeSection || 'INCOME') === 'INCOME'}}",
            ),
            select_widget(
                "IncomeType",
                "Income type",
                "{{Array.isArray(ListIncomeTypes.data) ? ListIncomeTypes.data.map((item) => ({label: item.display_name, value: item.id})) : []}}",
                62,
                2,
                20,
                visible="{{(appsmith.store.financeSection || 'INCOME') === 'INCOME'}}",
            ),
            input_widget(
                "IncomeName",
                "Income name",
                62,
                21,
                40,
                required=True,
                visible="{{(appsmith.store.financeSection || 'INCOME') === 'INCOME'}}",
            ),
            input_widget(
                "IncomeAmount",
                "Gross amount",
                62,
                41,
                52,
                required=True,
                visible="{{(appsmith.store.financeSection || 'INCOME') === 'INCOME'}}",
            ),
            select_widget(
                "IncomeFrequency",
                "Frequency",
                "{{[{label: 'Weekly', value: 'WEEKLY'}, {label: 'Fortnightly', value: 'FORTNIGHTLY'}, {label: 'Monthly', value: 'MONTHLY'}, {label: 'Quarterly', value: 'QUARTERLY'}, {label: 'Annual', value: 'ANNUAL'}]}}",
                62,
                53,
                62,
                visible="{{(appsmith.store.financeSection || 'INCOME') === 'INCOME'}}",
            ),
            select_widget(
                "IncomeTaxable",
                "Tax treatment",
                "{{[{label: 'Taxable', value: 'true'}, {label: 'Not taxable', value: 'false'}]}}",
                71,
                2,
                20,
                default="true",
                visible="{{(appsmith.store.financeSection || 'INCOME') === 'INCOME'}}",
            ),
            input_widget(
                "IncomeEffectiveFrom",
                "Effective from (YYYY-MM-DD)",
                71,
                21,
                40,
                required=True,
                visible="{{(appsmith.store.financeSection || 'INCOME') === 'INCOME'}}",
            ),
            input_widget(
                "IncomeEffectiveTo",
                "Effective to (optional, YYYY-MM-DD)",
                71,
                41,
                62,
                visible="{{(appsmith.store.financeSection || 'INCOME') === 'INCOME'}}",
            ),
            input_widget(
                "IncomeGrowthRate",
                "Annual growth % (optional)",
                80,
                2,
                20,
                visible="{{(appsmith.store.financeSection || 'INCOME') === 'INCOME'}}",
            ),
            input_widget(
                "IncomeSalarySacrifice",
                "Pre-tax contribution (optional)",
                80,
                21,
                40,
                visible="{{(appsmith.store.financeSection || 'INCOME') === 'INCOME'}}",
            ),
            input_widget(
                "IncomeNotes",
                "Notes (optional)",
                80,
                41,
                62,
                visible="{{(appsmith.store.financeSection || 'INCOME') === 'INCOME'}}",
            ),
            button(
                "CreateIncomeButton",
                "Add income source",
                "{{CreateIncome.run(() => { showAlert('Income source added', 'success'); ListIncomeSources.run(); resetWidget('IncomeType', true); resetWidget('IncomeName', true); resetWidget('IncomeAmount', true); resetWidget('IncomeFrequency', true); resetWidget('IncomeTaxable', true); resetWidget('IncomeEffectiveFrom', true); resetWidget('IncomeEffectiveTo', true); resetWidget('IncomeGrowthRate', true); resetWidget('IncomeSalarySacrifice', true); resetWidget('IncomeNotes', true); }, () => showAlert(JSON.stringify(CreateIncome.data?.detail || 'Could not add income source'), 'error'))}}",
                89,
                2,
                20,
                disabled="{{!appsmith.store.personId || !IncomeType.selectedOptionValue || !(IncomeName.text || '').trim() || !/^\\d+(\\.\\d{1,2})?$/.test((IncomeAmount.text || '').trim()) || !IncomeFrequency.selectedOptionValue || !IncomeTaxable.selectedOptionValue || !/^\\d{4}-\\d{2}-\\d{2}$/.test((IncomeEffectiveFrom.text || '').trim()) || ((IncomeEffectiveTo.text || '').trim() && !/^\\d{4}-\\d{2}-\\d{2}$/.test(IncomeEffectiveTo.text.trim())) || ((IncomeGrowthRate.text || '').trim() && !/^-?\\d+(\\.\\d{1,4})?$/.test(IncomeGrowthRate.text.trim())) || ((IncomeSalarySacrifice.text || '').trim() && !/^\\d+(\\.\\d{1,2})?$/.test(IncomeSalarySacrifice.text.trim()))}}",
                visible="{{(appsmith.store.financeSection || 'INCOME') === 'INCOME'}}",
            ),
            table(
                "IncomeSources",
                "{{Array.isArray(ListIncomeSources.data) ? ListIncomeSources.data.map((item) => ({...item, frequency: ({WEEKLY: 'Weekly', FORTNIGHTLY: 'Fortnightly', MONTHLY: 'Monthly', QUARTERLY: 'Quarterly', ANNUAL: 'Annual'})[item.frequency] || item.frequency, taxable: item.taxable ? 'Yes' : 'No'})) : []}}",
                (
                    ("id", "ID", False),
                    ("display_name", "Income", True),
                    ("gross_amount", "Gross amount", True),
                    ("frequency", "Frequency", True),
                    ("taxable", "Taxable", True),
                    ("annual_growth_rate", "Annual growth %", True),
                    ("effective_from", "Effective from", True),
                    ("effective_to", "Effective to", True),
                ),
                95,
                119,
                label="Income sources",
                visible="{{(appsmith.store.financeSection || 'INCOME') === 'INCOME'}}",
            ),
            text(
                "TaxHeading",
                "Tax settings",
                122,
                126,
                visible="{{appsmith.store.financeSection === 'TAX'}}",
            ),
            text(
                "TaxEmptyState",
                "{{Array.isArray(ListTaxProfiles.data) && ListTaxProfiles.data.length ? '' : 'No tax settings yet. Choose an installed provider or enter a manual annual net income.'}}",
                127,
                131,
                visible="{{appsmith.store.financeSection === 'TAX'}}",
            ),
            select_widget(
                "TaxCalculationMode",
                "Calculation method",
                "{{[{label: 'Installed tax provider', value: 'AUTOMATIC'}, {label: 'Manual annual net income', value: 'MANUAL_NET'}]}}",
                137,
                2,
                24,
                default="AUTOMATIC",
                visible="{{appsmith.store.financeSection === 'TAX'}}",
            ),
            select_widget(
                "TaxProviderYear",
                "Provider and tax year",
                "{{Array.isArray(ListTaxProviders.data) ? ListTaxProviders.data.flatMap((provider) => provider.supported_tax_years.map((year) => ({label: provider.display_name + ' — ' + year, value: provider.jurisdiction + '|' + year}))) : []}}",
                137,
                25,
                48,
                visible="{{appsmith.store.financeSection === 'TAX' && TaxCalculationMode.selectedOptionValue === 'AUTOMATIC'}}",
            ),
            input_widget(
                "TaxParameters",
                "Provider settings as JSON (use {} for defaults)",
                146,
                49,
                62,
                visible="{{appsmith.store.financeSection === 'TAX' && TaxCalculationMode.selectedOptionValue === 'AUTOMATIC' && appsmith.store.financeAdvancedMode}}",
            ),
            input_widget(
                "ManualTaxJurisdiction",
                "Jurisdiction",
                146,
                2,
                20,
                visible="{{appsmith.store.financeSection === 'TAX' && TaxCalculationMode.selectedOptionValue === 'MANUAL_NET'}}",
            ),
            input_widget(
                "ManualTaxYear",
                "Tax year",
                146,
                21,
                40,
                visible="{{appsmith.store.financeSection === 'TAX' && TaxCalculationMode.selectedOptionValue === 'MANUAL_NET'}}",
            ),
            input_widget(
                "ManualAnnualNetIncome",
                "Annual net income",
                146,
                41,
                62,
                visible="{{appsmith.store.financeSection === 'TAX' && TaxCalculationMode.selectedOptionValue === 'MANUAL_NET'}}",
            ),
            input_widget(
                "TaxEffectiveFrom",
                "Effective from (YYYY-MM-DD)",
                155,
                2,
                24,
                required=True,
                visible="{{appsmith.store.financeSection === 'TAX'}}",
            ),
            input_widget(
                "TaxEffectiveTo",
                "Effective to (optional, YYYY-MM-DD)",
                155,
                25,
                48,
                visible="{{appsmith.store.financeSection === 'TAX'}}",
            ),
            button(
                "CreateTaxProfileButton",
                "Save tax settings",
                "{{CreateTaxProfile.run(() => { showAlert('Tax settings saved', 'success'); ListTaxProfiles.run(); resetWidget('TaxProviderYear', true); resetWidget('TaxParameters', true); resetWidget('ManualTaxJurisdiction', true); resetWidget('ManualTaxYear', true); resetWidget('ManualAnnualNetIncome', true); resetWidget('TaxEffectiveFrom', true); resetWidget('TaxEffectiveTo', true); }, () => showAlert(JSON.stringify(CreateTaxProfile.data?.detail || 'Could not save tax settings'), 'error'))}}",
                164,
                2,
                20,
                disabled="{{!appsmith.store.personId || !TaxCalculationMode.selectedOptionValue || !/^\\d{4}-\\d{2}-\\d{2}$/.test((TaxEffectiveFrom.text || '').trim()) || ((TaxEffectiveTo.text || '').trim() && !/^\\d{4}-\\d{2}-\\d{2}$/.test(TaxEffectiveTo.text.trim())) || (TaxCalculationMode.selectedOptionValue === 'AUTOMATIC' && (!TaxProviderYear.selectedOptionValue || (appsmith.store.financeAdvancedMode && (TaxParameters.text || '').trim() && (() => { try { JSON.parse(TaxParameters.text); return false; } catch (error) { return true; } })()))) || (TaxCalculationMode.selectedOptionValue === 'MANUAL_NET' && (!(ManualTaxJurisdiction.text || '').trim() || !(ManualTaxYear.text || '').trim() || !/^\\d+(\\.\\d{1,2})?$/.test((ManualAnnualNetIncome.text || '').trim())))}}",
                visible="{{appsmith.store.financeSection === 'TAX'}}",
            ),
            table(
                "TaxProfiles",
                "{{Array.isArray(ListTaxProfiles.data) ? ListTaxProfiles.data.map((item) => ({...item, calculation_mode: (item.settings?.calculation_mode || 'AUTOMATIC') === 'MANUAL_NET' ? 'Manual annual net income' : 'Installed provider', manual_annual_net_income: item.settings?.manual_annual_net_income || ''})) : []}}",
                (
                    ("id", "ID", False),
                    ("jurisdiction", "Jurisdiction", True),
                    ("tax_year", "Tax year", True),
                    ("calculation_mode", "Method", True),
                    ("manual_annual_net_income", "Manual annual net", True),
                    ("effective_from", "Effective from", True),
                    ("effective_to", "Effective to", True),
                ),
                170,
                194,
                label="Tax profiles",
                visible="{{appsmith.store.financeSection === 'TAX'}}",
            ),
        ]
    else:
        widgets += [
            text(
                "SettingsHelp",
                "Connection details stay in the current browser session and are never included in the export.",
                17,
                21,
            ),
            input_widget("BearerToken", "Bearer token (production)", 22, 2, 62),
            input_widget(
                "DevelopmentSubject",
                "Development subject (local testing only)",
                30,
                2,
                32,
            ),
            button(
                "SaveSettings",
                "Save connection",
                "{{(async () => { await storeValue('apiToken', BearerToken.text || '', false); await storeValue('developmentSubject', DevelopmentSubject.text || '', false); if (!appsmith.store.householdId) { showAlert('Connection saved for this session', 'success'); return; } RestoreSelectedHousehold.run(async () => { const household = Array.isArray(RestoreSelectedHousehold.data) ? RestoreSelectedHousehold.data.find((item) => item.id === appsmith.store.householdId) : undefined; if (household) { await storeValue('householdName', household.display_name, true); showAlert('Connection saved and household restored', 'success'); } else { await removeValue('householdId'); await removeValue('householdName'); showAlert('The saved household is no longer available. Choose another household.', 'error'); navigateTo('Households'); } }, () => showAlert('Connection saved, but the saved household could not be verified', 'error')); })()}}",
                39,
                2,
                20,
            ),
            button(
                "TestConnection",
                "Test API connection",
                "{{HealthCheck.run(() => showAlert('API connection is ready', 'success'), () => showAlert('Could not reach the API', 'error'))}}",
                39,
                22,
                42,
            ),
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
    dynamic_binding_paths = [{"key": "body"}] if body.startswith("{{") else []
    dynamic_sources = [path, body]
    json_path_keys = [
        match.group(1).strip()
        for source in dynamic_sources
        for match in re.finditer(r"\{\{(.*?)\}\}", source)
    ]
    entity = {
        "name": name,
        "validName": name,
        "datasource": datasource(),
        "pageId": page,
        "actionConfiguration": configuration,
        "runBehaviour": "ON_PAGE_LOAD" if on_load else "MANUAL",
        "dynamicBindingPathList": dynamic_binding_paths,
        "isValid": True,
        "invalids": [],
        "messages": [],
        "jsonPathKeys": json_path_keys,
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
        action("Households", "ListHouseholds", "GET", "/api/v1/households", on_load=True),
        action(
            "Households",
            "CreateHousehold",
            "POST",
            "/api/v1/households",
            body="{{({ display_name: String(HouseholdName.text || '').trim(), currency: String(HouseholdCurrency.text || '').trim().toUpperCase(), jurisdiction: String(HouseholdJurisdiction.text || '').trim().toUpperCase() || null })}}",
        ),
        action(
            "People",
            "ListPeople",
            "GET",
            f"/api/v1/households/{household}/people",
            on_load=True,
        ),
        action(
            "People",
            "CreatePerson",
            "POST",
            f"/api/v1/households/{household}/people",
            body="{{({ display_name: String(PersonDisplayName.text || '').trim(), legal_name: String(PersonLegalName.text || '').trim() || null, date_of_birth: String(PersonDateOfBirth.text || '').trim() || null, tax_residency_country: String(PersonResidencyCountry.text || '').trim().toUpperCase() || null, tax_jurisdiction: String(PersonTaxJurisdiction.text || '').trim() || null, effective_from: String(PersonEffectiveFrom.text || '').trim() })}}",
        ),
        action(
            "Person finances",
            "ListIncomeTypes",
            "GET",
            "/api/v1/lookups/income_type",
            on_load=True,
        ),
        action(
            "Person finances",
            "ListTaxProviders",
            "GET",
            "/api/v1/tax-providers",
            on_load=True,
        ),
        action(
            "Person finances",
            "ListIncomeSources",
            "GET",
            "/api/v1/people/{{appsmith.store.personId}}/income-sources",
            on_load=True,
        ),
        action(
            "Person finances",
            "CreateIncome",
            "POST",
            "/api/v1/people/{{appsmith.store.personId}}/income-sources",
            body="{{({ income_type_id: IncomeType.selectedOptionValue, display_name: String(IncomeName.text || '').trim(), gross_amount: Number(IncomeAmount.text), frequency: IncomeFrequency.selectedOptionValue, salary_sacrifice_amount: String(IncomeSalarySacrifice.text || '').trim() ? Number(IncomeSalarySacrifice.text) : null, annual_growth_rate: String(IncomeGrowthRate.text || '').trim() ? Number(IncomeGrowthRate.text) : null, taxable: IncomeTaxable.selectedOptionValue === 'true', notes: String(IncomeNotes.text || '').trim() || null, effective_from: String(IncomeEffectiveFrom.text || '').trim(), effective_to: String(IncomeEffectiveTo.text || '').trim() || null })}}",
        ),
        action(
            "Person finances",
            "ListTaxProfiles",
            "GET",
            "/api/v1/people/{{appsmith.store.personId}}/tax-profiles",
            on_load=True,
        ),
        action(
            "Person finances",
            "CreateTaxProfile",
            "POST",
            "/api/v1/people/{{appsmith.store.personId}}/tax-profiles",
            body="{{TaxCalculationMode.selectedOptionValue === 'AUTOMATIC' ? ({ jurisdiction: TaxProviderYear.selectedOptionValue.split('|')[0], tax_year: TaxProviderYear.selectedOptionValue.split('|')[1], settings: { calculation_mode: 'AUTOMATIC', parameters: appsmith.store.financeAdvancedMode ? JSON.parse(TaxParameters.text || '{}') : {} }, effective_from: String(TaxEffectiveFrom.text || '').trim(), effective_to: String(TaxEffectiveTo.text || '').trim() || null }) : ({ jurisdiction: String(ManualTaxJurisdiction.text || '').trim().toUpperCase(), tax_year: String(ManualTaxYear.text || '').trim(), settings: { calculation_mode: 'MANUAL_NET', manual_annual_net_income: Number(ManualAnnualNetIncome.text) }, effective_from: String(TaxEffectiveFrom.text || '').trim(), effective_to: String(TaxEffectiveTo.text || '').trim() || null })}}",
        ),
        action("Settings", "HealthCheck", "GET", "/health/ready", on_load=True),
        action(
            "Settings",
            "RestoreSelectedHousehold",
            "GET",
            "/api/v1/households",
        ),
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
