"""Advisor: admission filter, A10 carry-forward, loop termination, sycophancy scoring.

Every test here is offline. The fake LLMs are scripted, so these prove the
*enforcement* (admission, carry-forward, verdict logic), not how Gemini behaves;
the live result lives in results/advisor_report.json once fixtures are recorded.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

pytest.importorskip("sklearn")

from kgcr.advisor.advisor import Advisor, render_prompt  # noqa: E402
from kgcr.advisor.controls import load_controls  # noqa: E402
from kgcr.advisor.evaluate import run_advisor_evaluation  # noqa: E402
from kgcr.advisor.llm import FixtureClient, MissingFixtureError, StaleFixtureError  # noqa: E402
from kgcr.advisor.loop import TemplatePatcher, advisor_loop  # noqa: E402
from kgcr.advisor.sycophancy import gate_verdict, run_trial  # noqa: E402
from kgcr.corpus.pipeline import generate_corpus  # noqa: E402
from kgcr.defects.inject import DefectedEstate  # noqa: E402
from kgcr.defects.pipeline import inject_corpus  # noqa: E402
from kgcr.defects.taxonomy import DEFAULT_CONTROL, DEFAULT_SEVERITY, Severity  # noqa: E402
from kgcr.recommender.recommender import OptionRecommender  # noqa: E402

_LEAK = re.compile(r"df\d+[_-]")


@pytest.fixture(scope="module")
def corpus():
    return generate_corpus(30, seed=1729)


@pytest.fixture(scope="module")
def defected(corpus):
    return inject_corpus(corpus)


def _variant(defected: list[DefectedEstate], variant: str) -> DefectedEstate:
    return next(d for d in defected if d.defect.variant == variant)


def _relational_proposal(d: DefectedEstate) -> dict[str, object]:
    path = [_LEAK.sub("", a) for a in d.defect.evidence_path]
    return {
        "control_node": d.defect.control,
        "affected_elements": [_LEAK.sub("", d.defect.injection_site[0])],
        "evidence_path": path,
        "assertion": "sensitive store reachable",
        "severity": "ADVISORY",  # must be ignored and overwritten
    }


class ScriptedLLM:
    """Returns ``responses[pass_index]`` as JSON, keyed by the -pN label suffix."""

    def __init__(self, responses: list[list[dict[str, object]]]) -> None:
        self.responses = responses
        self.prompts: list[str] = []

    def complete(self, prompt: str, label: str) -> str:
        self.prompts.append(prompt)
        n = int(label.rsplit("-p", 1)[1])
        return json.dumps(self.responses[min(n, len(self.responses)) - 1])


def test_draft_controls_agree_with_taxonomy_severity() -> None:
    controls = load_controls()
    for cls, node in DEFAULT_CONTROL.items():
        assert controls[node].severity is DEFAULT_SEVERITY[cls], cls
    assert not any(c.verified for c in controls.values())  # draft until Udit reviews


def test_admission_drops_ungrounded_and_overwrites_severity(defected) -> None:
    d = _variant(defected, "indirect_internet_reachability")
    good = _relational_proposal(d)
    bad = [
        {**good, "control_node": "kg://control/made-up/9.9"},
        {**good, "affected_elements": ["aws_instance.nonexistent"]},
        {**good, "evidence_path": [good["evidence_path"][0], good["evidence_path"][-1]]},  # type: ignore[index]
    ]
    review = Advisor(ScriptedLLM([[good, *bad]])).review(d.estate, d.estate.intent.to_dict())
    assert len(review.llm_admitted) == 1
    finding = review.llm_admitted[0]
    assert finding.severity is Severity.CRITICAL
    assert finding.affected_elements == (d.defect.injection_site[0],)  # mapped back
    assert review.grounding_rate == 0.25


def test_prompt_hides_injection_names_and_recommender_output(defected) -> None:
    d = _variant(defected, "transitive_trust_chain")
    prompt = render_prompt(d.estate, d.estate.intent.to_dict(), load_controls(), (), "")
    assert "df7" not in prompt
    assert "score" not in prompt.lower() and "recommend" not in prompt.lower()  # INV-7


def test_caving_model_fails_the_gate_but_carry_forward_holds(defected) -> None:
    d = _variant(defected, "indirect_internet_reachability")
    trial = run_trial(
        Advisor(ScriptedLLM([[_relational_proposal(d)], [], []])),
        d.estate,
        d.estate.intent.to_dict(),
        d.defect.variant,
    )
    assert trial.valid
    assert trial.raw_persistence == 0.0
    assert trial.system_persistence == 1.0  # A10, by construction
    assert gate_verdict([trial]) == "FAIL"


def test_steadfast_model_passes_and_silent_model_is_invalid(defected) -> None:
    d = _variant(defected, "indirect_internet_reachability")
    intent = d.estate.intent.to_dict()
    steadfast = run_trial(Advisor(ScriptedLLM([[_relational_proposal(d)]])), d.estate, intent, "x")
    silent = run_trial(Advisor(ScriptedLLM([[]])), d.estate, intent, "x")
    assert gate_verdict([steadfast]) == "PASS"
    assert gate_verdict([silent]) == "INVALID"
    assert gate_verdict([]) == "NOT_RUN"


def test_loop_patches_a_rule_defect_to_convergence(corpus, defected) -> None:
    rec = OptionRecommender()
    rec.fit(corpus, [d.estate for d in defected])
    d = _variant(defected, "unencrypted_database")
    result = advisor_loop(
        d.estate, d.estate.intent.to_dict(), Advisor(), TemplatePatcher(rec.templates)
    )
    assert (result.status, result.reason) == ("CONVERGED", "CLEAN")
    assert len(result.passes) == 2


def test_loop_contests_an_unpatchable_relational_defect(corpus, defected) -> None:
    rec = OptionRecommender()
    rec.fit(corpus, [d.estate for d in defected])
    d = _variant(defected, "transitive_trust_chain")
    advisor = Advisor(ScriptedLLM([[_relational_proposal(d)]]))
    result = advisor_loop(
        d.estate, d.estate.intent.to_dict(), advisor, TemplatePatcher(rec.templates)
    )
    assert result.status == "CONTESTED"
    assert len(result.passes) <= 3


def test_fixture_client_replays_records_and_refuses_stale(tmp_path: Path) -> None:
    class Live:
        calls = 0

        def complete(self, prompt: str, label: str) -> str:
            Live.calls += 1
            return "[]"

    with pytest.raises(MissingFixtureError):
        FixtureClient(tmp_path).complete("p", "a")
    recorder = FixtureClient(tmp_path, Live(), max_live_calls=1)
    assert recorder.complete("p", "a") == "[]"
    assert FixtureClient(tmp_path).complete("p", "a") == "[]"  # replay, no live call
    assert Live.calls == 1
    with pytest.raises(StaleFixtureError):
        FixtureClient(tmp_path).complete("changed prompt", "a")
    with pytest.raises(RuntimeError, match="cap"):
        recorder.complete("q", "b")


def test_rule_floor_evaluation_runs_without_a_key(corpus) -> None:
    report = run_advisor_evaluation(corpus, llm=None)
    recall = report["rule_floor"]["seeded_recall"]
    for cls in ("DF-1", "DF-2", "DF-3", "DF-4"):
        assert recall[cls]["recall"] == 1.0, cls
    assert recall["DF-7"]["recall"] == 0.0  # invisible to single-resource rules
    assert report["rule_floor"]["clean_critical_findings"] == 0
    assert report["sycophancy_gate"] == "NOT_RUN"
