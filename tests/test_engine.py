"""Runtime contracts, persistence and negative paths; not research efficacy."""
from copy import deepcopy
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pse import engine
from pse.__main__ import main


def plan_fixture():
    return {
        "version": 2, "case_id": "test_case", "objective": "Compare three explicit approaches",
        "scope": "Small deterministic fixture", "success_criteria": "All critical controls and chosen branch pass",
        "limitations": ["Synthetic example, no external validity"],
        "budget": {"max_checks": 6, "max_units": 12, "max_rounds": 2, "max_seconds": 3600},
        "questions": [{"id": "q1", "text": "Is the operation consistent?", "purpose": "Check result"},
                      {"id": "q2", "text": "Could a counterexample defeat it?", "purpose": "Challenge result"}],
        "branches": [
            {"id": "b1", "question_id": "q1", "role": "baseline", "hypothesis": "Direct sum works", "approach": "Direct addition", "falsifier": "Wrong sum"},
            {"id": "b2", "question_id": "q1", "role": "alternative", "hypothesis": "Product works", "approach": "Multiplication", "falsifier": "Wrong product"},
            {"id": "b3", "question_id": "q2", "role": "critical", "hypothesis": "Inverse is consistent", "approach": "Inverse check", "falsifier": "Wrong difference"}],
        "checks": [
            {"id": "c1", "branch_ids": ["b1"], "method": "arithmetic", "params": {"expression": "2+2", "expected": 4}, "decision_link": "Baseline identity", "critical": False, "challenge": False, "cost_units": 1},
            {"id": "c2", "branch_ids": ["b2"], "method": "arithmetic", "params": {"expression": "2*2", "expected": 4}, "decision_link": "Alternative identity", "critical": False, "challenge": False, "cost_units": 1},
            {"id": "c3", "branch_ids": ["b3"], "method": "arithmetic", "params": {"expression": "4-2", "expected": 2}, "decision_link": "Adversarial inverse", "critical": True, "challenge": True, "cost_units": 1}]
    }


def decision(supported=True):
    """Compatibility helper for result-only or unresolved test closures."""
    return {"mode": "results_only"} if supported else {"mode": "unresolved", "reason": "Fixture cannot establish a conclusion", "limitations": ["Fixture only"]}


def draft_fixture():
    return {"author": "Fixture author", "selected_branch_id": "b1",
            "claims": [{"id": "claim_1", "text": "The supplied addition evaluates to four", "check_ids": ["c1"],
                        "scope": "The supplied arithmetic expression only", "assumptions": [], "limitations": ["No external interpretation"]}],
            "reasons_by_branch": {"b1": "Direct check", "b2": "Alternative considered", "b3": "Countercheck considered"},
            "limitations": ["Synthetic declared review fixture"]}


def review_fixture(proposal, verdict="approve"):
    """Declared test fixture; production never manufactures an approval."""
    return {"proposal_id": proposal["proposal_id"], "proposal_sha256": proposal["proposal_sha256"],
            "reviewer": "Fixture reviewer", "verdict": verdict,
            "claims": [{"claim_id": c["id"], "verdict": "supported" if verdict == "approve" else "uncertain",
                        "reason": "Declared synthetic assessment for a contract test", "check_ids": c["check_ids"]}
                       for c in proposal["draft"]["claims"]],
            "challenge": {"check_id": "c3", "finding": "The inverse control passed", "alternative_explanation": "This only describes fixture arithmetic"},
            "scope_assessment": "Limited to the supplied expressions", "uncertainties": ["Not external scientific validation"]}


def material_tip():
    return {"type": "material_evidence", "affected_check_ids": ["c3"],
            "reason": "Additional boundary case identified", "decision_impact": "May invalidate inverse"}


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.case = self.root / "case"
        self.plan = plan_fixture()

    def tearDown(self):
        self.temp.cleanup()

    def write(self, name, data):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False) if isinstance(data, (dict, list)) else data, encoding="utf-8")
        return path

    def init(self):
        return engine.init_case(self.write("plan.json", self.plan), self.case)

    def reviewed_close(self):
        proposal = engine.propose_case(self.case, draft_fixture())
        engine.review_case(self.case, review_fixture(proposal))
        return engine.close_case(self.case, {"mode": "reviewed", "proposal_id": proposal["proposal_id"]})

    def revision(self):
        plan = deepcopy(self.plan)
        added = deepcopy(plan["checks"][2])
        added.update(id="c4", revises=["c3"], decision_link="Additional inverse boundary checks the material objection")
        added["params"] = {"expression": "0-2", "expected": -2}
        plan["checks"].append(added)
        return plan

    def documentary(self):
        self.write("evidence/source.txt", "The recorded value is four.")
        self.plan["checks"][0].update(method="text_evidence", params={"path": "evidence/source.txt", "quote": "recorded value is four", "locator": "sentence 1"})

    def test_complete_lifecycle_and_no_reexecution(self):
        self.assertEqual(self.init()["state"], "READY")
        self.assertEqual(engine.run_case(self.case)["budget"]["checks_used"], 3)
        self.assertEqual(engine.run_case(self.case)["budget"]["checks_used"], 3)
        state = self.reviewed_close()
        self.assertEqual(state["state"], "CLOSED_REVIEWED_DECLARED")
        self.assertEqual(state["closures"][-1]["result_evidence_mode"], "COMPUTED")
        self.assertEqual(state["closures"][-1]["evidence_mode"], "DECLARED_REVIEW")
        self.assertTrue(engine.verify_case(self.case)["verified"])
        self.assertIn("The supplied addition evaluates to four", engine.render_report(self.case))
        with self.assertRaises(engine.EngineError):
            engine.run_case(self.case)

    def test_individual_view_excludes_other_branches_and_results(self):
        self.init()
        view = engine.branch_view(self.case, "b1")
        text = json.dumps(view)
        self.assertNotIn("Product works", text)
        self.assertNotIn("Inverse is consistent", text)
        self.assertNotIn("results", view)
        self.assertEqual(view["branch"]["id"], "b1")
        engine.run_case(self.case)
        with self.assertRaises(engine.EngineError):
            engine.branch_view(self.case, "b1")

    def test_init_no_overwrite(self):
        self.init()
        original = (self.case / "journal.json").read_bytes()
        with self.assertRaises(engine.EngineError):
            self.init()
        self.assertEqual((self.case / "journal.json").read_bytes(), original)

    def test_invalid_input_leaves_no_case(self):
        self.plan["checks"][0]["params"]["expression"] = "__import__('os')"
        with self.assertRaises(engine.EngineError):
            self.init()
        self.assertFalse(self.case.exists())
        self.assertFalse(list(self.root.glob(".pse-create-*")))

    def test_invalid_plan_contracts(self):
        for field, value in (("max_checks", True), ("max_units", 0), ("max_seconds", float("inf"))):
            plan = plan_fixture()
            plan["budget"][field] = value
            with self.subTest(field=field), self.assertRaises(engine.EngineError):
                engine.validate_plan(plan)
        for mutate in (lambda p: p["branches"][1].update(approach=" DIRECT  addition ".strip()),
                       lambda p: p["questions"][1].update(text="IS THE  OPERATION CONSISTENT?"),
                       lambda p: p["checks"][2].update(challenge=False),
                       lambda p: p["checks"][2].update(critical=False),
                       lambda p: p["branches"][0].update(id="q1"),
                       lambda p: p["checks"][0].update(branch_ids=["missing"])):
            plan = plan_fixture(); mutate(plan)
            with self.assertRaises(engine.EngineError):
                engine.validate_plan(plan)

    def test_duplicate_json_and_nonfinite_rejected(self):
        for data in ('{"version":1,"version":2}', '{"a":NaN}', '{"a":Infinity}'):
            with self.subTest(data=data), self.assertRaises(engine.EngineError):
                engine.read_json(self.write("bad.json", data))

    def test_early_close_requires_unresolved(self):
        self.init()
        with self.assertRaises(engine.EngineError):
            self.reviewed_close()
        state = engine.close_case(self.case, decision(False))
        self.assertEqual(state["state"], "CLOSED_UNRESOLVED")
        self.assertEqual(state["closures"][-1]["evidence_mode"], "NO_EXECUTED_CHECKS")

    def test_critical_failure_blocks_supported_but_continues_checks(self):
        self.plan["checks"][0].update(critical=True)
        self.plan["checks"][0]["params"]["expected"] = 5
        self.init()
        result = engine.run_case(self.case)
        self.assertEqual(len(result["results"]), 3)
        self.assertEqual(result["results"]["c1"]["status"], "fail")
        with self.assertRaises(engine.EngineError):
            self.reviewed_close()

    def test_failed_selected_branch_blocks_even_when_not_critical(self):
        self.plan["checks"][0]["params"]["expected"] = 5
        self.init(); engine.run_case(self.case)
        with self.assertRaises(engine.EngineError):
            self.reviewed_close()

    def test_failed_other_branch_may_be_discarded_with_reason(self):
        self.plan["checks"][1]["params"]["expected"] = 5
        self.init(); engine.run_case(self.case)
        self.assertEqual(self.reviewed_close()["state"], "CLOSED_REVIEWED_DECLARED")

    def test_closure_requires_every_branch_reason_and_limitations(self):
        self.init(); engine.run_case(self.case)
        for kind in ("reason", "limitations", "selection"):
            d = draft_fixture()
            if kind == "reason": del d["reasons_by_branch"]["b3"]
            elif kind == "limitations": d["limitations"] = []
            else: d["selected_branch_id"] = "missing"
            with self.subTest(kind=kind), self.assertRaises(engine.EngineError):
                engine.propose_case(self.case, d)

    def test_check_budget_is_global_and_no_attempt_for_unaffordable_check(self):
        self.plan["budget"]["max_checks"] = 2
        self.init()
        state = engine.run_case(self.case)
        self.assertEqual(state["state"], "BUDGET_EXHAUSTED")
        self.assertEqual(state["budget"]["checks_used"], 2)
        self.assertNotIn("c3", state["results"])
        self.assertEqual(engine.run_case(self.case)["budget"]["checks_used"], 2)
        self.assertEqual(engine.close_case(self.case, decision(False))["state"], "CLOSED_UNRESOLVED")

    def test_units_budget(self):
        self.plan["budget"]["max_units"] = 2
        self.init()
        state = engine.run_case(self.case)
        self.assertEqual(state["budget"]["units_used"], 2)
        self.assertEqual(state["state"], "BUDGET_EXHAUSTED")

    def test_walltime_includes_idle_case_lifetime(self):
        self.plan["budget"]["max_seconds"] = 5
        with patch.object(engine.time, "time", return_value=1000): self.init()
        with patch.object(engine.time, "time", return_value=1006):
            state = engine.run_case(self.case)
            self.assertEqual(state["budget"]["checks_used"], 0)
            self.assertEqual(state["state"], "BUDGET_EXHAUSTED")

    def test_adapter_failure_consumes_budget_and_is_recorded(self):
        self.init()
        with patch.object(engine.adapters, "execute", side_effect=RuntimeError("controlled fault")):
            state = engine.run_case(self.case)
        self.assertEqual(state["budget"]["checks_used"], 3)
        self.assertTrue(all(r["status"] == "inconclusive" for r in state["results"].values()))
        self.assertIn("controlled fault", state["results"]["c1"]["details"]["message"])
        self.assertEqual(engine.run_case(self.case)["budget"]["checks_used"], 3)

    def test_interruption_does_not_refund_or_retry(self):
        self.init()
        with patch.object(engine.adapters, "execute", side_effect=KeyboardInterrupt), self.assertRaises(KeyboardInterrupt):
            engine.run_case(self.case)
        self.assertEqual(engine.status(self.case)["budget"]["checks_used"], 1)
        state = engine.run_case(self.case)
        self.assertEqual(state["results"]["c1"]["status"], "inconclusive")
        self.assertTrue(state["results"]["c1"]["details"]["interrupted"])
        self.assertEqual(state["budget"]["checks_used"], 3)

    def test_source_snapshot_is_portable_and_original_changes_do_not_affect_it(self):
        self.documentary(); self.init()
        self.write("evidence/source.txt", "Original edited later")
        self.assertEqual(engine.run_case(self.case)["results"]["c1"]["status"], "pass")
        text = (self.case / "journal.json").read_text(encoding="utf-8")
        self.assertNotIn(str(self.root), text)

    def test_source_mutation_detected_before_attempt(self):
        self.documentary(); self.init()
        source = self.case / "rounds/r001/sources/evidence/source.txt"
        source.write_text("The changed value is four.", encoding="utf-8")
        with self.assertRaises(engine.EngineError): engine.run_case(self.case)
        events = engine.read_json(self.case / "journal.json")
        self.assertEqual(len(events), 1)

    def test_plan_and_journal_mutations_detected(self):
        self.init()
        sealed = self.case / "rounds/r001/plan.json"
        content = sealed.read_bytes()
        plan = engine.read_json(sealed); plan["scope"] = "Changed scope"
        sealed.write_text(json.dumps(plan), encoding="utf-8")
        with self.assertRaises(engine.EngineError): engine.verify_case(self.case)
        sealed.write_bytes(content)
        engine.run_case(self.case)
        events = engine.read_json(self.case / "journal.json")
        events[2]["payload"]["result"]["status"] = "fail"
        (self.case / "journal.json").write_text(json.dumps(events), encoding="utf-8")
        with self.assertRaises(engine.EngineError): engine.verify_case(self.case)

    def test_runtime_change_detected(self):
        self.init()
        with patch.object(engine, "_runtime", return_value="0" * 64), self.assertRaises(engine.EngineError):
            engine.verify_case(self.case)

    def test_path_escape_rejected_before_case_created(self):
        self.plan["checks"][0].update(method="text_evidence", params={"path": "../secret.txt", "quote": "secret", "locator": "line 1"})
        with self.assertRaises(engine.EngineError): self.init()
        self.assertFalse(self.case.exists())

    def test_lock_blocks_mutation_without_changing_journal(self):
        self.init()
        (self.case / ".pse.lock").write_text("test", encoding="utf-8")
        with self.assertRaises(engine.EngineError): engine.run_case(self.case)
        self.assertEqual(engine.status(self.case)["budget"]["checks_used"], 0)

    def test_tip_scope_and_duplicate_controls(self):
        self.init(); engine.run_case(self.case); self.reviewed_close()
        for kind, action in (("presentation", "KEEP_SCOPE"), ("new_objective", "OUT_OF_SCOPE")):
            tip = {"type": kind, "affected_check_ids": [], "reason": "Change heading", "decision_impact": "None on current evidence"}
            result = engine.add_tip(self.case, tip)
            self.assertEqual(result["tip"]["action"], action)
            self.assertEqual(result["status"]["state"], "CLOSED_REVIEWED_DECLARED")
            with self.assertRaises(engine.EngineError): engine.add_tip(self.case, tip)

    def test_material_tip_supersedes_closure_and_requires_linked_new_controls(self):
        self.init(); engine.run_case(self.case); self.reviewed_close()
        state = engine.add_tip(self.case, material_tip())["status"]
        self.assertEqual(state["state"], "REVIEW_REQUIRED")
        self.assertTrue(state["closures"][-1]["superseded"])
        with self.assertRaises(engine.EngineError): self.reviewed_close()
        with self.assertRaises(engine.EngineError): engine.run_case(self.case)
        engine.revise_case(self.case, self.write("revision.json", self.revision()))
        with self.assertRaises(engine.EngineError): self.reviewed_close()
        state = engine.run_case(self.case)
        self.assertEqual(state["budget"]["checks_used"], 4)
        self.assertEqual(state["budget"]["rounds_used"], 2)
        closed = self.reviewed_close()
        self.assertEqual(len(closed["closures"]), 2)
        self.assertTrue(closed["closures"][0]["superseded"])
        self.assertFalse(closed["closures"][1]["superseded"])
        self.assertTrue(closed["exploratory_revision"])

    def test_revision_cannot_change_criteria_existing_check_or_budget(self):
        self.init(); engine.run_case(self.case); engine.add_tip(self.case, material_tip())
        for change in (lambda p: p.update(success_criteria="Easier"),
                       lambda p: p["budget"].update(max_checks=100),
                       lambda p: p["checks"][2]["params"].update(expected=99),
                       lambda p: p["checks"][-1].pop("revises"),
                       lambda p: p["checks"][-1].update(critical=False, challenge=False)):
            plan = self.revision(); change(plan)
            with self.assertRaises(engine.EngineError): engine.revise_case(self.case, self.write("revision.json", plan))
        self.assertEqual(engine.status(self.case)["round"], 1)

    def test_favorable_revision_never_erases_historical_critical_failure(self):
        self.plan["checks"][2]["params"]["expected"] = 5
        self.init(); engine.run_case(self.case); engine.add_tip(self.case, material_tip())
        engine.revise_case(self.case, self.write("revision.json", self.revision()))
        state = engine.run_case(self.case)
        self.assertEqual(state["results"]["c3"]["status"], "fail")
        self.assertEqual(state["results"]["c4"]["status"], "pass")
        with self.assertRaises(engine.EngineError): self.reviewed_close()

    def test_revision_rounds_and_remaining_budget(self):
        self.plan["budget"]["max_checks"] = 3
        self.init(); engine.run_case(self.case); engine.add_tip(self.case, material_tip())
        with self.assertRaises(engine.EngineError): engine.revise_case(self.case, self.write("revision.json", self.revision()))
        self.assertEqual(engine.status(self.case)["budget"]["checks_used"], 3)

    def test_declared_review_never_reported_as_computed(self):
        self.write("source.txt", "Recorded observation")
        self.write("review.json", {"reviewer": "Declared reviewer", "method": "Fixture review", "verdict": "pass", "finding": "The recorded observation matches", "limitations": ["Not independent validation"], "evidence_paths": ["source.txt"]})
        self.plan["checks"][0].update(method="manual_review", params={"path": "review.json", "evidence": [{"path": "source.txt", "quote": "Recorded observation", "locator": "line 1"}]})
        self.init(); engine.run_case(self.case)
        closed = self.reviewed_close()
        self.assertEqual(closed["closures"][-1]["evidence_mode"], "DECLARED_REVIEW")
        self.assertEqual(closed["results"]["c1"]["kind"], "declared")

    def test_cli_contract_and_report_no_overwrite(self):
        plan = self.write("plan.json", self.plan)
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(["init", str(plan), "--out", str(self.case)]), 0)
            self.assertEqual(main(["run", str(self.case)]), 0)
            self.assertEqual(main(["close", str(self.case), "--decision", str(self.write("decision.json", decision()))]), 0)
            self.assertEqual(main(["report", str(self.case), "--out", str(self.root / "report.md")]), 0)
            self.assertEqual(main(["report", str(self.case), "--out", str(self.root / "report.md")]), 2)
        self.assertIn("CLOSED_RESULTS", output.getvalue())
        self.assertTrue((self.root / "report.md").is_file())

    def rewrite_chain(self, events):
        """Deliberately rehash a malformed fixture to test contracts beyond hashes."""
        previous = engine.ZERO
        for i, event in enumerate(events):
            event.update(seq=i, previous=previous)
            event.pop("sha256", None)
            event["sha256"] = engine._digest(event)
            previous = event["sha256"]
        (self.case / "journal.json").write_text(json.dumps(events), encoding="utf-8")

    def test_legacy_plan_requires_explicit_migration(self):
        self.plan["version"] = 1
        with self.assertRaisesRegex(engine.EngineError, "migrate"):
            self.init()
        self.assertFalse(self.case.exists())

    def test_legacy_free_conclusion_rejected_without_write(self):
        self.init(); engine.run_case(self.case)
        before = (self.case / "journal.json").read_bytes()
        for old in ({"requested_status": "supported", "conclusion": "The moon is cheese"},
                    {"mode": "results_only", "conclusion": "The moon is cheese"}):
            with self.assertRaises(engine.EngineError):
                engine.close_case(self.case, old)
        self.assertEqual(before, (self.case / "journal.json").read_bytes())

    def test_results_only_preserves_negative_without_selecting_branch(self):
        self.plan["checks"][2]["params"]["expected"] = 99
        self.init(); engine.run_case(self.case)
        result = engine.close_case(self.case, {"mode": "results_only"})
        self.assertEqual(result["state"], "CLOSED_RESULTS")
        closure = result["closures"][-1]
        self.assertNotIn("selected_branch_id", closure)
        self.assertNotIn("conclusion", closure)
        self.assertEqual(closure["generated_results"][-1]["status"], "fail")

    def test_status_and_review_packet_do_not_invalidate_proposal(self):
        self.init(); engine.run_case(self.case)
        proposal = engine.propose_case(self.case, draft_fixture())
        before = (self.case / "journal.json").read_bytes()
        engine.status(self.case); engine.verify_case(self.case)
        packet = engine.review_packet(self.case, proposal["proposal_id"])
        self.assertTrue(packet["context_current"])
        self.assertEqual(packet["proposal_sha256"], proposal["proposal_sha256"])
        self.assertNotIn("verdict", packet)
        self.assertEqual(before, (self.case / "journal.json").read_bytes())
        engine.review_case(self.case, review_fixture(proposal))
        state = engine.close_case(self.case, {"mode": "reviewed", "proposal_id": proposal["proposal_id"]})
        self.assertEqual(state["state"], "CLOSED_REVIEWED_DECLARED")

    def test_proposals_and_reviews_consume_global_units(self):
        self.plan["budget"]["max_units"] = 4
        self.init(); engine.run_case(self.case)
        proposal = engine.propose_case(self.case, draft_fixture())
        b = engine.status(self.case)["budget"]
        self.assertEqual((b["checks_used"], b["proposals_used"], b["reviews_used"], b["units_used"]), (3, 1, 0, 4))
        with self.assertRaises(engine.EngineError):
            engine.review_case(self.case, review_fixture(proposal))
        with self.assertRaises(engine.EngineError):
            engine.close_case(self.case, {"mode": "reviewed", "proposal_id": proposal["proposal_id"]})
        self.assertEqual(engine.close_case(self.case, decision(False))["state"], "CLOSED_UNRESOLVED")

    def test_three_proposal_and_review_limit_is_global(self):
        self.init(); engine.run_case(self.case)
        for n in range(3):
            draft = draft_fixture(); draft["claims"][0]["text"] += f"; declared variant {n}"
            proposal = engine.propose_case(self.case, draft)
            engine.review_case(self.case, review_fixture(proposal, "reject"))
        b = engine.status(self.case)["budget"]
        self.assertEqual((b["proposals_used"], b["reviews_used"], b["units_used"]), (3, 3, 9))
        engine.add_tip(self.case, material_tip())
        engine.revise_case(self.case, self.write("revision.json", self.revision()))
        engine.run_case(self.case)
        with self.assertRaisesRegex(engine.EngineError, "Proposal limit"):
            engine.propose_case(self.case, draft_fixture())
        self.assertEqual(engine.status(self.case)["budget"]["units_used"], 10)

    def test_rejected_proposal_cannot_be_resubmitted_or_reviewed_twice(self):
        self.init(); engine.run_case(self.case)
        proposal = engine.propose_case(self.case, draft_fixture())
        engine.review_case(self.case, review_fixture(proposal, "reject"))
        with self.assertRaises(engine.EngineError): engine.propose_case(self.case, draft_fixture())
        with self.assertRaises(engine.EngineError): engine.review_case(self.case, review_fixture(proposal))
        with self.assertRaises(engine.EngineError): engine.close_case(self.case, {"mode": "reviewed", "proposal_id": proposal["proposal_id"]})
        self.assertEqual(engine.status(self.case)["budget"]["units_used"], 5)

    def test_changed_hash_cannot_review_original_proposal(self):
        self.init(); engine.run_case(self.case)
        proposal = engine.propose_case(self.case, draft_fixture())
        review = review_fixture(proposal); review["proposal_sha256"] = "0" * 64
        with self.assertRaises(engine.EngineError): engine.review_case(self.case, review)
        self.assertEqual(engine.status(self.case)["budget"]["reviews_used"], 0)

    def test_presentation_tip_invalidates_even_approved_proposal(self):
        self.init(); engine.run_case(self.case)
        proposal = engine.propose_case(self.case, draft_fixture())
        engine.review_case(self.case, review_fixture(proposal))
        engine.add_tip(self.case, {"type": "presentation", "affected_check_ids": [], "reason": "Clarify a heading", "decision_impact": "No change claimed to evidence"})
        self.assertFalse(engine.review_packet(self.case, proposal["proposal_id"])["context_current"])
        with self.assertRaisesRegex(engine.EngineError, "stale"):
            engine.close_case(self.case, {"mode": "reviewed", "proposal_id": proposal["proposal_id"]})
        fresh = engine.propose_case(self.case, draft_fixture())
        self.assertNotEqual(fresh["context_sha256"], proposal["context_sha256"])
        self.assertNotEqual(fresh["proposal_sha256"], proposal["proposal_sha256"])

    def test_material_tip_and_new_round_invalidate_proposal(self):
        self.init(); engine.run_case(self.case)
        proposal = engine.propose_case(self.case, draft_fixture())
        engine.add_tip(self.case, material_tip())
        with self.assertRaises(engine.EngineError): engine.review_case(self.case, review_fixture(proposal))
        engine.revise_case(self.case, self.write("revision.json", self.revision()))
        engine.run_case(self.case)
        with self.assertRaisesRegex(engine.EngineError, "stale"):
            engine.review_case(self.case, review_fixture(proposal))

    def test_elapsed_deadline_blocks_proposal_review_and_factual_close(self):
        self.plan["budget"]["max_seconds"] = 5
        with patch.object(engine.time, "time", return_value=1000):
            self.init(); engine.run_case(self.case)
            proposal = engine.propose_case(self.case, draft_fixture())
        with patch.object(engine.time, "time", return_value=1006):
            with self.assertRaises(engine.EngineError): engine.propose_case(self.case, draft_fixture())
            with self.assertRaises(engine.EngineError): engine.review_case(self.case, review_fixture(proposal))
            with self.assertRaises(engine.EngineError): engine.close_case(self.case, {"mode": "results_only"})
            self.assertEqual(engine.close_case(self.case, decision(False))["state"], "CLOSED_UNRESOLVED")

    def test_historical_reviewed_closure_survives_later_deadline(self):
        self.plan["budget"]["max_seconds"] = 5
        with patch.object(engine.time, "time", return_value=1000):
            self.init(); engine.run_case(self.case); self.reviewed_close()
        with patch.object(engine.time, "time", return_value=1000000):
            self.assertTrue(engine.verify_case(self.case)["verified"])
            self.assertEqual(engine.status(self.case)["state"], "CLOSED_REVIEWED_DECLARED")

    def test_replay_refuses_rehashed_result_kind_change(self):
        self.init(); engine.run_case(self.case)
        events = engine.read_json(self.case / "journal.json")
        events[2]["payload"]["result"]["kind"] = "declared"
        self.rewrite_chain(events)
        with self.assertRaisesRegex(engine.EngineError, "kind differs"):
            engine.verify_case(self.case)

    def test_replay_refuses_rehashed_closure_without_review(self):
        self.init(); engine.run_case(self.case); self.reviewed_close()
        events = engine.read_json(self.case / "journal.json")
        events = [e for e in events if e["action"] != "reviewed"]
        self.rewrite_chain(events)
        with self.assertRaisesRegex(engine.EngineError, "approved proposal review"):
            engine.verify_case(self.case)

    def test_replay_refuses_rehashed_close_after_deadline(self):
        self.plan["budget"]["max_seconds"] = 5
        with patch.object(engine.time, "time", return_value=1000):
            self.init(); engine.run_case(self.case); self.reviewed_close()
        events = engine.read_json(self.case / "journal.json")
        events[-1]["timestamp"] = 1006
        self.rewrite_chain(events)
        with self.assertRaisesRegex(engine.EngineError, "Budget exhausted"):
            engine.verify_case(self.case)

    def test_approved_false_claim_remains_declared_not_computed_truth(self):
        self.init(); engine.run_case(self.case)
        draft = draft_fixture(); draft["claims"][0]["text"] = "The moon is cheese"
        proposal = engine.propose_case(self.case, draft)
        # Intentional dishonest declaration illustrates the explicit boundary.
        engine.review_case(self.case, review_fixture(proposal))
        closure = engine.close_case(self.case, {"mode": "reviewed", "proposal_id": proposal["proposal_id"]})["closures"][-1]
        self.assertEqual(closure["state"], "CLOSED_REVIEWED_DECLARED")
        self.assertEqual(closure["evidence_mode"], "DECLARED_REVIEW")
        self.assertEqual(closure["assurance"], "REVIEW_DECLARED_NOT_SEMANTICALLY_VERIFIED")
        self.assertNotIn("The moon is cheese", json.dumps(closure["generated_results"]))
        self.assertIn("no verificada", engine.render_report(self.case))

    def test_clock_rollback_rejected_before_journal_write(self):
        with patch.object(engine.time, "time", return_value=1000): self.init()
        before = (self.case / "journal.json").read_bytes()
        with patch.object(engine.time, "time", return_value=999), self.assertRaises(engine.EngineError):
            engine.close_case(self.case, decision(False))
        self.assertEqual(before, (self.case / "journal.json").read_bytes())

    def test_cli_proposal_review_packet_and_review(self):
        self.init(); engine.run_case(self.case)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(main(["propose", str(self.case), "--draft", str(self.write("draft.json", draft_fixture()))]), 0)
        proposal = json.loads(output.getvalue())
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(["review-packet", str(self.case), proposal["proposal_id"]]), 0)
            self.assertEqual(main(["review", str(self.case), "--review", str(self.write("review.json", review_fixture(proposal)))]), 0)
            self.assertEqual(main(["close", str(self.case), "--decision", str(self.write("close.json", {"mode": "reviewed", "proposal_id": proposal["proposal_id"]}))]), 0)
        self.assertEqual(engine.status(self.case)["budget"]["units_used"], 5)


if __name__ == "__main__":
    unittest.main()
