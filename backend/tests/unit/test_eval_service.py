"""Unit tests for the eval scoring math + judge prompt shape.

We don't hit the LLM here — that's covered by the live `python -m app.eval_cli` run.
These tests cover the pure-Python aggregation and JSON-shape guarantees so a
regression in score math gets caught in CI.
"""

from __future__ import annotations

import json

from app.services.eval_service import (
    AXES,
    AxisScore,
    CaseResult,
    EvalReport,
    _judge_prompt,
    load_golden,
)


def _make_case(case_id: str, base_scores: dict[str, float], cand_scores: dict[str, float]) -> CaseResult:
    axes = {axis: AxisScore(baseline=base_scores[axis], candidate=cand_scores[axis]) for axis in AXES}
    return CaseResult(
        case_id=case_id,
        axes=axes,
        judge_reasoning="test",
        candidate_subject="x", candidate_body="x",
        baseline_subject="y", baseline_body="y",
    )


def test_case_result_computes_means_and_ratio():
    case = _make_case(
        "x",
        {a: 5.0 for a in AXES},
        {a: 7.0 for a in AXES},
    )
    assert case.baseline_mean == 5.0
    assert case.candidate_mean == 7.0
    assert abs(case.percent_of_baseline - 1.4) < 1e-9


def test_eval_report_aggregates_across_cases():
    c1 = _make_case("a", {a: 4.0 for a in AXES}, {a: 6.0 for a in AXES})
    c2 = _make_case("b", {a: 6.0 for a in AXES}, {a: 9.0 for a in AXES})
    report = EvalReport(results=[c1, c2], judge_model="judge/x", candidate_model="cand/y")
    assert report.baseline_mean == 5.0
    assert report.candidate_mean == 7.5
    assert abs(report.percent_of_baseline - 1.5) < 1e-9


def test_per_axis_means_returns_each_axis():
    case = _make_case("x", {a: 3.0 for a in AXES}, {a: 6.0 for a in AXES})
    report = EvalReport(results=[case], judge_model="j", candidate_model="c")
    per = report.per_axis_means()
    assert set(per.keys()) == set(AXES)
    for axis in AXES:
        assert per[axis] == (3.0, 6.0)


def test_zero_baseline_does_not_div_by_zero():
    case = _make_case("z", {a: 0.0 for a in AXES}, {a: 5.0 for a in AXES})
    report = EvalReport(results=[case], judge_model="j", candidate_model="c")
    assert report.percent_of_baseline == 1.0
    assert case.percent_of_baseline == 1.0


def test_judge_prompt_contains_both_emails_and_rubric():
    prospect = {"name": "X", "title": "Y", "domain": "z.com"}
    sender = {"name": "Me", "company": "Co", "offer": "do thing"}
    a = {"subject": "subj A", "body": "body A"}
    b = {"subject": "subj B", "body": "body B"}
    prompt = _judge_prompt(prospect, sender, a, b)
    assert "subj A" in prompt and "subj B" in prompt
    assert "body A" in prompt and "body B" in prompt
    for axis in AXES:
        assert axis in prompt
    # Verify the strict JSON shape the judge must return.
    assert '"a":' in prompt and '"b":' in prompt and '"winner"' in prompt


def test_golden_file_loads_and_each_case_has_required_fields():
    cases = load_golden()
    assert len(cases) >= 1
    for case in cases:
        assert "id" in case
        for field in ("name", "title", "domain"):
            assert field in case["prospect"]
        for field in ("name", "company", "offer"):
            assert field in case["sender"]
        for field in ("subject", "body"):
            assert field in case["baseline"]
        # Sanity: baseline must be a non-trivial email.
        assert len(case["baseline"]["body"]) > 100
