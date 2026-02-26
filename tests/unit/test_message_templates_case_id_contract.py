from __future__ import annotations

import inspect
from collections.abc import Callable

from triage_automation.infrastructure.matrix import message_templates
from triage_automation.infrastructure.matrix.message_templates import (
    INFORMATIONAL_CASE_ID_TEMPLATE_BUILDERS,
    STRUCTURAL_CASE_ID_TEMPLATE_BUILDERS,
)


def test_case_id_template_builder_sets_are_disjoint_and_complete() -> None:
    structural = set(STRUCTURAL_CASE_ID_TEMPLATE_BUILDERS)
    informational = set(INFORMATIONAL_CASE_ID_TEMPLATE_BUILDERS)

    assert structural
    assert informational
    assert structural.isdisjoint(informational)

    expected_all = structural | informational
    discovered = _discover_room_template_builders_with_case_id()
    assert discovered == expected_all


def test_structural_templates_match_parser_bound_contract() -> None:
    expected_structural = {
        "build_room2_case_decision_template_message",
        "build_room2_case_decision_template_formatted_html",
        "build_room2_decision_error_message",
        "build_room3_reply_template_message",
        "build_room3_invalid_format_reprompt",
    }

    assert set(STRUCTURAL_CASE_ID_TEMPLATE_BUILDERS) == expected_structural


def _discover_room_template_builders_with_case_id() -> set[str]:
    discovered: set[str] = set()
    for name, value in vars(message_templates).items():
        if not name.startswith("build_room"):
            continue
        if not callable(value):
            continue
        signature = inspect.signature(value)
        if "case_id" not in signature.parameters:
            continue
        discovered.add(name)
    return discovered
