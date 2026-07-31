"""Regression tests for the paper's strict tool-set matching rule."""

import sys
from pathlib import Path

import pytest


EVALUATOR_DIR = Path(__file__).resolve().parents[1] / "eval" / "evaluators"
sys.path.insert(0, str(EVALUATOR_DIR))

import evaluate_reactive  # noqa: E402
import evaluate_traces  # noqa: E402


EVALUATORS = (evaluate_reactive, evaluate_traces)


def _trace(*tool_names):
    return {
        "steps": [{
            "step_id": 1,
            "tool_executions": [
                {"tool_name": name, "arguments": {}} for name in tool_names
            ],
        }],
    }


@pytest.mark.parametrize("evaluator", EVALUATORS)
def test_exact_expected_tool_set_passes(evaluator):
    task = {"expected_tools": [{"tool": "book_hotel", "params": {}}]}

    result = evaluator.check_expected_tools(_trace("book_hotel"), task)

    assert result["passed"] is True
    assert result["reason"] == "correct"


@pytest.mark.parametrize("evaluator", EVALUATORS)
def test_extra_tool_call_fails(evaluator):
    task = {"expected_tools": [{"tool": "book_hotel", "params": {}}]}

    result = evaluator.check_expected_tools(
        _trace("book_hotel", "check_balance"), task
    )

    assert result["passed"] is False
    assert result["reason"] == "unexpected_call"

