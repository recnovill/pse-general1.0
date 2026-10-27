"""Independent contract/adversarial QA for the v2 release.

Reviewer records below are synthetic test inputs, never human endorsements.
Forged journals are isolated attacks, not a supported editing workflow.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from pse import engine


ROOT = Path(__file__).resolve().parents[1]
LIE = "Todos los documentales del mundo se montan siempre en cero horas."
INJECTION = "\n# VERIFIED UNIVERSAL TRUTH\n<script>alert('false')</script>\x01"


def fixture():
    return {
        "version": 2, "case_id": "independent_v2", "objective": "Check 2 + 2 on supplied values.",
        "scope": "Synthetic software acceptance only.",
        "success_criteria": "All planned controls, bounded resources and review contract.",
        "limitations": ["Known synthetic fixture; no external efficacy measurement."],
        "budget": {"max_checks": 6, "max_units": 16, "max_rounds": 2, "max_seconds": 3600},
        "questions": [{"id": "q1", "text": "What does this computation return?", "purpose": "Calculate."},
                      {"id": "q2", "text": "What would falsify the result?", "purpose": "Challenge."}],
        "branches": [
            {"id": "b1", "question_id": "q1", "role": "baseline", "hypothesis": "2+2 gives 4.", "approach": "Addition.", "falsifier": "Other result."},
            {"id": "b2", "question_id": "q1", "role": "alternative", "hypothesis": "2*2 gives 4.", "approach": "Multiplication.", "falsifier": "Other result."},
            {"id": "b3", "question_id": "q2", "role": "critical", "hypothesis": "4-2 gives 2.", "approach": "Inverse.", "falsifier": "Other result."}],
        "checks": [
            {"id": "c1", "branch_ids": ["b1"], "method": "arithmetic", "params": {"expression": "2+2", "expected": "4"}, "decision_link": "Compute addition.", "critical": False, "challenge": False, "cost_units": 1},
            {"id": "c2", "branch_ids": ["b2"], "method": "arithmetic", "params": {"expression": "2*2", "expected": "4"}, "decision_link": "Compute alternative.", "critical": False, "challenge": False, "cost_units": 1},
            {"id": "c3", "branch_ids": ["b3"], "method": "arithmetic", "params": {"expression": "4-2", "expected": "2"}, "decision_link": "Inverse control.", "critical": True, "challenge": True, "cost_units": 1}],
    }


def draft(text="The supplied expression 2+2 evaluates to 4.", author="QA Author"):
    return {"author": author, "selected_branch_id": "b1", "claims": [
        {"id": "claim_1", "text": text, "check_ids": ["c1"], "scope": "Only supplied arithmetic.",
         "assumptions": ["Inputs mean the stated arithmetic values."], "limitations": ["No worldly inference."]}],
        "reasons_by_branch": {"b1": "Direct computation.", "b2": "Same numeric value by another operation.", "b3": "Inverse control passes."},
        "limitations": ["This is a declared interpretation in synthetic QA."]}


def review(proposal, reviewer="QA Reviewer", verdict="approve"):
    return {"proposal_id": proposal["proposal_id"], "proposal_sha256": proposal["proposal_sha256"],
            "reviewer": reviewer, "verdict": verdict,
            "claims": [{"claim_id": c["id"], "verdict": "supported" if verdict == "approve" else "unsupported",
                        "reason": "Synthetic test review, not an independent human judgment.",
                        "check_ids": c["check_ids"]} for c in proposal["draft"]["claims"]],
            "challenge": {"check_id": "c3", "finding": "The inverse computation passed.",
                          "alternative_explanation": "Arithmetic alone cannot validate worldly interpretation."},
            "scope_assessment": "Limited to supplied arithmetic.",
            "uncertainties": ["Reviewer labels are not authenticated."]}


class ReleaseV2Acceptance(unittest.TestCase):
    def setUp(self):
        parent = ROOT / "_build" / "qa_v2"
        parent.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(prefix="case_", dir=parent)
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        self.case = self.folder / "case"
        self.plan = fixture()

    def init(self, *, run=True, case=None, plan=None):
        plan = self.plan if plan is None else plan
        case = self.case if case is None else case
        source = self.folder / (case.name + "_plan.json")
        source.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
        engine.init_case(source, case)
        if run:
            engine.run_case(case)
        return case

    def propose(self, data=None):
        return engine.propose_case(self.case, draft() if data is None else data)

    def approve(self, data=None):
        proposal = self.propose(data)
        engine.review_case(self.case, review(proposal))
        return proposal

    def close_reviewed(self, proposal):
        return engine.close_case(self.case, {"mode": "reviewed", "proposal_id": proposal["proposal_id"]})

    def rehash(self, journal):
        """Attacker recomputes chain; structure must still fail when illegal."""
        previous = "0" * 64
        for seq, event in enumerate(journal):
            event["seq"] = seq
            event["previous"] = previous
            clean = {k: v for k, v in event.items() if k != "sha256"}
            event["sha256"] = hashlib.sha256(json.dumps(clean, sort_keys=True, separators=(",", ":"),
                                                        ensure_ascii=False, allow_nan=False).encode()).hexdigest()
            previous = event["sha256"]
        (self.case / "journal.json").write_text(json.dumps(journal), encoding="utf-8")

    def journal(self):
        return json.loads((self.case / "journal.json").read_text(encoding="utf-8"))

    def assert_safe_report(self, report):
        self.assertNotIn("\n# VERIFIED UNIVERSAL TRUTH", report)
        self.assertNotIn("\x01", report)
        # HTML may be escaped or preserved inside a literal indented JSON block.
        # Both keep source material from becoming executable report structure.
        for line in report.splitlines():
            if "<script>" in line:
                self.assertTrue(line.startswith("    "), line)

    def test_v1_plan_requires_explicit_migration(self):
        self.plan["version"] = 1
        with self.assertRaises(engine.EngineError):
            self.init(run=False)
        self.assertFalse(self.case.exists())

    def test_c12_legacy_free_conclusion_is_rejected(self):
        self.init()
        with self.assertRaises(engine.EngineError):
            engine.close_case(self.case, {"requested_status": "supported", "conclusion": LIE,
                "selected_branch_id": "b1", "reasons_by_branch": draft()["reasons_by_branch"], "limitations": ["None."]})
        self.assertNotIn("CLOSED", engine.status(self.case)["state"])

    def test_results_only_cannot_smuggle_conclusion_or_winner(self):
        self.init()
        for key, value in (("conclusion", LIE), ("selected_branch_id", "b1"), ("assurance", "verified")):
            with self.subTest(key=key), self.assertRaises(engine.EngineError):
                engine.close_case(self.case, {"mode": "results_only", key: value})

    def test_results_only_generated_calculation_has_no_interpretation(self):
        self.init()
        engine.close_case(self.case, {"mode": "results_only"})
        closed = engine.status(self.case)["closures"][-1]
        self.assertEqual(closed["state"], "CLOSED_RESULTS")
        self.assertNotIn("selected_branch_id", closed)
        self.assertNotIn("conclusion", closed)
        self.assertEqual(len(closed["generated_results"]), 3)
        self.assertTrue(all(r["kind"] == "computed" for r in closed["generated_results"]))
        self.assertNotIn(LIE, engine.render_report(self.case))

    def test_results_only_keeps_failed_checks_without_selecting_winner(self):
        self.plan["checks"][0]["params"]["expected"] = "5"
        self.init()
        with self.assertRaises(engine.EngineError):
            self.propose()
        engine.close_case(self.case, {"mode": "results_only"})
        self.assertEqual(engine.status(self.case)["results"]["c1"]["status"], "fail")

    def test_no_review_cannot_close_reviewed(self):
        self.init()
        proposal = self.propose()
        with self.assertRaises(engine.EngineError):
            self.close_reviewed(proposal)

    def test_legitimate_reviewed_closure_and_reads(self):
        self.init()
        proposal = self.approve()
        engine.status(self.case)
        engine.verify_case(self.case)
        engine.review_packet(self.case, proposal["proposal_id"])
        self.close_reviewed(proposal)
        state = engine.status(self.case)
        self.assertEqual(state["state"], "CLOSED_REVIEWED_DECLARED")
        self.assertEqual(state["budget"]["units_used"], 5)
        self.assertTrue(engine.verify_case(self.case)["verified"])

    def test_approved_false_claim_remains_declared_semantic_limit(self):
        self.init()
        proposal = self.approve(draft(LIE))
        self.close_reviewed(proposal)
        state = engine.status(self.case)
        self.assertEqual(state["state"], "CLOSED_REVIEWED_DECLARED")
        self.assertIn(LIE, json.dumps(state["closures"][-1], ensure_ascii=False))
        self.assertNotIn(LIE, json.dumps(state["closures"][-1]["generated_results"], ensure_ascii=False))
        self.assertIn("DECLARED", engine.render_report(self.case))

    def test_author_and_reviewer_normalize_nfkc_casefold_spaces(self):
        self.init()
        proposal = self.propose(draft(author="QA Author"))
        for same in ("QA Author", "qa   AUTHOR", " qa AUTHOR ", "ＱＡ Ａｕｔｈｏｒ"):
            with self.subTest(same=same), self.assertRaises(engine.EngineError):
                engine.review_case(self.case, review(proposal, reviewer=same))

    def test_draft_unknown_reference_and_missing_branch_reason_rejected(self):
        self.init()
        for mutation in ("unknown", "branch", "duplicate_claim"):
            data = draft()
            if mutation == "unknown":
                data["claims"][0]["check_ids"] = ["foreign_check"]
            elif mutation == "branch":
                data["reasons_by_branch"].pop("b2")
            else:
                data["claims"].append(copy.deepcopy(data["claims"][0]))
            with self.subTest(mutation=mutation), self.assertRaises(engine.EngineError):
                self.propose(data)

    def test_review_digest_exact_and_cross_case_bound(self):
        self.init()
        proposal = self.propose()
        forged = review(proposal)
        forged["proposal_sha256"] = "f" * 64
        with self.assertRaises(engine.EngineError):
            engine.review_case(self.case, forged)
        other = self.folder / "other_case"
        other_plan = copy.deepcopy(self.plan)
        other_plan["case_id"] = "other_independent_case"
        self.init(case=other, plan=other_plan)
        engine.propose_case(other, draft())
        with self.assertRaises(engine.EngineError):
            engine.review_case(other, review(proposal))

    def test_review_requires_exact_claim_and_reference_coverage(self):
        self.init()
        proposal = self.propose()
        for mutation in ("missing", "duplicate", "unknown", "wrong_ref"):
            data = review(proposal)
            if mutation == "missing":
                data["claims"] = []
            elif mutation == "duplicate":
                data["claims"].append(copy.deepcopy(data["claims"][0]))
            elif mutation == "unknown":
                data["claims"][0]["claim_id"] = "claim_absent"
            else:
                data["claims"][0]["check_ids"] = ["c2"]
            with self.subTest(mutation=mutation), self.assertRaises(engine.EngineError):
                engine.review_case(self.case, data)

    def test_review_challenge_and_approval_requirements(self):
        self.init()
        proposal = self.propose()
        for mutation in ("noncritical", "uncertain", "unsupported"):
            data = review(proposal)
            if mutation == "noncritical":
                data["challenge"]["check_id"] = "c1"
            else:
                data["claims"][0]["verdict"] = mutation
            with self.subTest(mutation=mutation), self.assertRaises(engine.EngineError):
                engine.review_case(self.case, data)

    def test_rejected_candidate_cannot_close_repeat_or_duplicate(self):
        self.init()
        proposal = self.propose()
        engine.review_case(self.case, review(proposal, verdict="reject"))
        for action in (lambda: self.close_reviewed(proposal), lambda: engine.review_case(self.case, review(proposal)), lambda: self.propose()):
            with self.assertRaises(engine.EngineError):
                action()

    def test_any_new_tip_invalidates_pending_review_context(self):
        self.init()
        proposal = self.propose()
        engine.add_tip(self.case, {"type": "presentation", "affected_check_ids": [],
                                  "reason": "Change layout only.", "decision_impact": "No semantic change."})
        with self.assertRaises(engine.EngineError):
            engine.review_case(self.case, review(proposal))

    def test_material_tip_invalidates_approved_proposal(self):
        self.init()
        proposal = self.approve()
        engine.add_tip(self.case, {"type": "material_evidence", "affected_check_ids": ["c1"],
                                  "reason": "Potential input error.", "decision_impact": "May change claim."})
        with self.assertRaises(engine.EngineError):
            self.close_reviewed(proposal)
        with self.assertRaises(engine.EngineError):
            engine.close_case(self.case, {"mode": "results_only"})

    def test_proposal_review_caps_and_units_persist(self):
        self.init()
        for index in range(3):
            proposal = self.propose(draft(text=f"Declared bounded interpretation {index}."))
            engine.review_case(self.case, review(proposal, verdict="reject"))
        state = engine.status(self.case)
        self.assertEqual(state["budget"]["units_used"], 9)
        self.assertEqual(state["budget"]["proposals_used"], 3)
        self.assertEqual(state["budget"]["reviews_used"], 3)
        with self.assertRaises(engine.EngineError):
            self.propose(draft(text="Fourth proposal."))
        engine.add_tip(self.case, {"type": "material_evidence", "affected_check_ids": ["c1"],
                                  "reason": "Additional bounded control required.", "decision_impact": "May affect supplied arithmetic."})
        revised = copy.deepcopy(self.plan)
        check = copy.deepcopy(revised["checks"][0])
        check.update(id="c4", revises=["c1"])
        revised["checks"].append(check)
        path = self.folder / "revision.json"
        path.write_text(json.dumps(revised), encoding="utf-8")
        engine.revise_case(self.case, path)
        engine.run_case(self.case)
        after = engine.status(self.case)["budget"]
        self.assertEqual((after["proposals_used"], after["reviews_used"], after["units_used"]), (3, 3, 10))
        with self.assertRaises(engine.EngineError):
            self.propose(draft(text="Fourth proposal after revision still forbidden."))

    def test_review_cannot_exceed_unit_budget_unresolved_can_close(self):
        self.plan["budget"]["max_units"] = 4
        self.init()
        proposal = self.propose()
        with self.assertRaises(engine.EngineError):
            engine.review_case(self.case, review(proposal))
        self.assertEqual(engine.status(self.case)["budget"]["units_used"], 4)
        engine.close_case(self.case, {"mode": "unresolved", "reason": "Review budget exhausted.", "limitations": ["No endorsed interpretation."]})
        self.assertEqual(engine.status(self.case)["state"], "CLOSED_UNRESOLVED")

    def test_expired_current_close_blocked_historical_close_still_valid(self):
        self.init()
        proposal = self.approve()
        created = self.journal()[0]["timestamp"]
        with patch.object(engine.time, "time", return_value=created + 4000):
            with self.assertRaises(engine.EngineError):
                self.close_reviewed(proposal)
        self.close_reviewed(proposal)
        with patch.object(engine.time, "time", return_value=created + 4000):
            self.assertTrue(engine.verify_case(self.case)["verified"])
            self.assertEqual(engine.status(self.case)["state"], "CLOSED_REVIEWED_DECLARED")

    def test_forged_chain_without_review_is_structurally_rejected(self):
        self.init()
        proposal = self.approve()
        self.close_reviewed(proposal)
        events = [e for e in self.journal() if e["action"] != "reviewed"]
        self.rehash(events)
        with self.assertRaises(engine.EngineError):
            engine.verify_case(self.case)

    def test_forged_result_kind_cannot_promote_computation(self):
        self.init()
        events = self.journal()
        event = next(e for e in events if e["action"] == "check_result")
        event["payload"]["result"]["kind"] = "declared"
        self.rehash(events)
        with self.assertRaises(engine.EngineError):
            engine.verify_case(self.case)

    def test_forged_result_without_attempt_is_rejected(self):
        self.init()
        events = self.journal()
        target = next(e for e in events if e["action"] == "attempt_started")
        events.remove(target)
        self.rehash(events)
        with self.assertRaises(engine.EngineError):
            engine.verify_case(self.case)

    def test_forged_result_missing_typed_facts_is_rejected_at_verify(self):
        self.init()
        events = self.journal()
        event = next(e for e in events if e["action"] == "check_result")
        event["payload"]["result"]["details"] = {}
        self.rehash(events)
        with self.assertRaises(engine.EngineError):
            engine.verify_case(self.case)

    def test_forged_results_close_without_all_checks_is_rejected(self):
        self.init()
        engine.close_case(self.case, {"mode": "results_only"})
        events = self.journal()
        events = [e for e in events if not (e["action"] in ("attempt_started", "check_result") and e["payload"]["check_id"] == "c2")]
        self.rehash(events)
        with self.assertRaises(engine.EngineError):
            engine.verify_case(self.case)

    def test_forged_closure_edited_generated_summary_is_rejected(self):
        self.init()
        engine.close_case(self.case, {"mode": "results_only"})
        events = self.journal()
        events[-1]["payload"]["generated_results"][0]["injected_conclusion"] = LIE
        self.rehash(events)
        with self.assertRaises(engine.EngineError):
            engine.verify_case(self.case)

    def test_report_external_markdown_html_is_escaped(self):
        self.plan["objective"] += INJECTION
        self.init()
        proposal = self.approve(draft(text="The arithmetic passed." + INJECTION))
        self.close_reviewed(proposal)
        report = engine.render_report(self.case)
        self.assert_safe_report(report)

    def test_adapter_free_summary_never_promoted_to_generated_fact(self):
        self.init(run=False)
        real_execute = engine.adapters.execute
        def malicious_summary(check, root):
            result = real_execute(check, root)
            result["summary"] = LIE + INJECTION
            return result
        with patch.object(engine.adapters, "execute", side_effect=malicious_summary):
            engine.run_case(self.case)
        engine.close_case(self.case, {"mode": "results_only"})
        generated = engine.status(self.case)["closures"][-1]["generated_results"]
        self.assertNotIn(LIE, json.dumps(generated, ensure_ascii=False))
        self.assertNotIn(LIE, engine.render_report(self.case))

    def test_csv_ceiling_detected_without_changing_threshold_and_equality_passes(self):
        (self.folder / "rows.csv").write_text("id,truth,baseline,candidate\na,0,1,0\nb,2,3,2\n", encoding="utf-8")
        params = {"path": "rows.csv", "id_column": "id", "truth_column": "truth", "baseline_column": "baseline",
                  "candidate_column": "candidate", "min_absolute_improvement": "2", "min_relative_improvement": "0.1"}
        self.plan["checks"][0].update(method="csv_compare", params=params)
        self.init()
        result = engine.status(self.case)["results"]["c1"]
        self.assertEqual(result["status"], "inconclusive")
        self.assertEqual(result["details"]["design_status"], "threshold_above_comparator_ceiling")
        self.assertEqual(result["details"]["min_absolute_improvement"]["exact"], "2")
        self.assertEqual(result["details"]["max_possible_absolute_improvement"]["exact"], "1")
        equal_plan = copy.deepcopy(self.plan)
        equal_plan["checks"][0]["params"]["min_absolute_improvement"] = "1"
        equal = self.init(case=self.folder / "equal_case", plan=equal_plan)
        self.assertEqual(engine.status(equal)["results"]["c1"]["status"], "pass")
        impossible_relative = copy.deepcopy(equal_plan)
        impossible_relative["checks"][0]["params"]["min_relative_improvement"] = "1.01"
        with self.assertRaises(engine.EngineError):
            self.init(case=self.folder / "relative_case", plan=impossible_relative, run=False)

    def test_region_label_stays_declared_input(self):
        self.plan["checks"][0].update(method="numeric_interval", params={"value": "5", "error": "0",
            "regions": [{"id": "WORLDLY_CLAIM", "lower": "4", "upper": "6"}], "expected": "WORLDLY_CLAIM"})
        self.init()
        engine.close_case(self.case, {"mode": "results_only"})
        records = engine.status(self.case)["closures"][-1]["generated_results"]
        self.assertIn("WORLDLY_CLAIM", json.dumps(records))
        for item in records:
            nondeclared = {k: v for k, v in item.items() if k != "declared_inputs"}
            self.assertNotIn("WORLDLY_CLAIM", json.dumps(nondeclared))

    def test_manual_finding_never_becomes_computed_fact_or_candidate_review(self):
        (self.folder / "evidence.txt").write_text("Literal fixture evidence.", encoding="utf-8")
        record = {"reviewer": "Manual fixture", "method": "Declared review.", "verdict": "pass",
                  "finding": LIE + INJECTION, "limitations": ["Known synthetic false interpretation."], "evidence_paths": ["evidence.txt"]}
        (self.folder / "manual.json").write_text(json.dumps(record), encoding="utf-8")
        self.plan["checks"][0].update(method="manual_review", params={"path": "manual.json", "evidence": [
            {"path": "evidence.txt", "quote": "Literal fixture evidence.", "locator": "Line 1"}]})
        self.init()
        proposal = self.propose()
        with self.assertRaises(engine.EngineError):
            self.close_reviewed(proposal)
        engine.close_case(self.case, {"mode": "results_only"})
        records = engine.status(self.case)["closures"][-1]["generated_results"]
        self.assertTrue(any(r["kind"] == "declared" for r in records))
        for item in records:
            nondeclared = {k: v for k, v in item.items() if k != "declared_inputs"}
            self.assertNotIn(LIE, json.dumps(nondeclared, ensure_ascii=False))
        report = engine.render_report(self.case)
        self.assert_safe_report(report)

    def test_cli_rejects_c12_and_completes_review_workflow(self):
        self.init()
        def cli(*args):
            return subprocess.run([sys.executable, "-B", "-m", "pse", *map(str, args)],
                cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
        bad = self.folder / "bad.json"
        bad.write_text(json.dumps({"mode": "results_only", "conclusion": LIE}), encoding="utf-8")
        failed = cli("close", self.case, "--decision", bad)
        self.assertEqual(failed.returncode, 2, failed.stdout + failed.stderr)
        candidate_path = self.folder / "draft.json"
        candidate_path.write_text(json.dumps(draft()), encoding="utf-8")
        proposed = cli("propose", self.case, "--draft", candidate_path)
        self.assertEqual(proposed.returncode, 0, proposed.stderr)
        proposal = json.loads(proposed.stdout)
        packet = cli("review-packet", self.case, proposal["proposal_id"])
        self.assertEqual(packet.returncode, 0, packet.stderr)
        self.assertNotIn("suggested_approval", json.loads(packet.stdout))
        review_path = self.folder / "review.json"
        review_path.write_text(json.dumps(review(proposal)), encoding="utf-8")
        reviewed = cli("review", self.case, "--review", review_path)
        self.assertEqual(reviewed.returncode, 0, reviewed.stderr)
        decision = self.folder / "decision.json"
        decision.write_text(json.dumps({"mode": "reviewed", "proposal_id": proposal["proposal_id"]}), encoding="utf-8")
        closed = cli("close", self.case, "--decision", decision)
        self.assertEqual(closed.returncode, 0, closed.stderr)
        verified = cli("verify", self.case)
        self.assertEqual(verified.returncode, 0, verified.stderr)
        self.assertTrue(json.loads(verified.stdout)["verified"])


if __name__ == "__main__":
    unittest.main()
