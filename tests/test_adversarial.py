"""Independent acceptance tests through the public engine API.

Cases are synthetic development fixtures. They do not measure research utility.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
import shutil
import time
import unittest
from unittest.mock import patch
import uuid

from pse import engine


ROOT = Path(__file__).resolve().parents[1]


class IndependentAcceptance(unittest.TestCase):
    def setUp(self):
        self.folder = ROOT / "_build" / "qa_cases" / uuid.uuid4().hex
        self.folder.mkdir(parents=True, exist_ok=False)
        self.assertTrue(self.folder.resolve().is_relative_to((ROOT / "_build").resolve()))
        self.plan = json.loads((ROOT / "examples/calculo/plan.json").read_text(encoding="utf-8"))
        self.plan["version"] = 2
        self.decision = {"mode": "results_only"}
        self.case = self.folder / "case"

    def init(self, plan=None):
        self.plan = self.plan if plan is None else plan
        path = self.folder / "plan.json"
        path.write_text(json.dumps(self.plan, ensure_ascii=False), encoding="utf-8")
        engine.init_case(path, self.case)
        return self.case

    def finish(self):
        engine.run_case(self.case)
        engine.close_case(self.case, self.decision)

    def draft(self):
        selected = self.plan["branches"][0]["id"]
        check = next(c for c in self.plan["checks"] if selected in c["branch_ids"])
        return {"author": "QA Author", "selected_branch_id": selected,
                "claims": [{"id": "claim_1", "text": "The supplied control passed.",
                            "check_ids": [check["id"]], "scope": "Synthetic fixture only.",
                            "assumptions": ["Inputs are supplied."],
                            "limitations": ["No generalization."]}],
                "reasons_by_branch": {b["id"]: "Recorded development comparison."
                                      for b in self.plan["branches"]},
                "limitations": ["Synthetic software QA, not semantic validation."]}

    def material_tip(self):
        return {"type": "material_evidence", "affected_check_ids": ["valor"],
                "reason": "Nueva objeción concreta a la comprobación de valor.",
                "decision_impact": "Si falla la comprobación adicional, la conclusión deja de sostenerse."}

    def revised_plan(self):
        result = copy.deepcopy(self.plan)
        check = copy.deepcopy(result["checks"][0])
        check.update(id="valor_nuevo", revises=["valor"], challenge=True)
        check["params"] = {"expression": "14 - (2 + 3 * 4)", "expected": "0", "tolerance": "0"}
        result["checks"].append(check)
        return result

    def revise(self, plan):
        path = self.folder / ("revision_" + uuid.uuid4().hex + ".json")
        path.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
        return engine.revise_case(self.case, path)

    def test_premature_supported_closure_is_rejected(self):
        self.init()
        with self.assertRaises(engine.EngineError):
            engine.close_case(self.case, self.decision)

    def test_failed_adversarial_check_blocks_supported(self):
        self.plan["checks"][1]["params"]["expected"] = "0"
        self.init()
        engine.run_case(self.case)
        with self.assertRaises(engine.EngineError):
            engine.propose_case(self.case, self.draft())
        unresolved = {"mode": "unresolved", "reason": "A critical check failed.",
                      "limitations": ["No supported interpretation."]}
        engine.close_case(self.case, unresolved)
        engine.verify_case(self.case)

    def test_bool_and_nonfinite_budget_rejected(self):
        for value in (True, float("nan"), float("inf")):
            with self.subTest(value=value):
                candidate = copy.deepcopy(self.plan)
                candidate["budget"]["max_units"] = value
                path = self.folder / (uuid.uuid4().hex + ".json")
                path.write_text(json.dumps(candidate), encoding="utf-8")
                with self.assertRaises(engine.EngineError):
                    engine.init_case(path, self.folder / uuid.uuid4().hex)

    def test_duplicate_id_and_missing_challenge_rejected(self):
        for mutation in ("duplicate", "challenge"):
            with self.subTest(mutation=mutation):
                candidate = copy.deepcopy(self.plan)
                if mutation == "duplicate":
                    candidate["checks"][1]["id"] = candidate["checks"][0]["id"]
                else:
                    for check in candidate["checks"]:
                        check["challenge"] = False
                path = self.folder / (uuid.uuid4().hex + ".json")
                path.write_text(json.dumps(candidate), encoding="utf-8")
                with self.assertRaises(engine.EngineError):
                    engine.init_case(path, self.folder / uuid.uuid4().hex)

    def test_branch_view_does_not_leak_other_hypotheses(self):
        self.plan["branches"][1]["hypothesis"] = "SECRET_ALTERNATIVE_HYPOTHESIS_93811"
        self.plan["branches"][2]["hypothesis"] = "SECRET_CRITICAL_HYPOTHESIS_51682"
        self.init()
        view = str(engine.branch_view(self.case, "base"))
        self.assertNotIn("SECRET_ALTERNATIVE", view)
        self.assertNotIn("SECRET_CRITICAL", view)
        self.assertIn(self.plan["branches"][0]["hypothesis"], view)

    def test_material_tip_prevents_closure_until_rechecked(self):
        self.init()
        self.finish()
        engine.add_tip(self.case, self.material_tip())
        with self.assertRaises(engine.EngineError):
            engine.close_case(self.case, self.decision)
        self.revise(self.revised_plan())
        with self.assertRaises(engine.EngineError):
            engine.close_case(self.case, self.decision)
        engine.run_case(self.case)
        engine.close_case(self.case, self.decision)
        engine.verify_case(self.case)

    def test_presentation_and_other_objective_do_not_reopen(self):
        self.init()
        self.finish()
        before = copy.deepcopy(engine.status(self.case))
        for kind in ("presentation", "new_objective"):
            engine.add_tip(self.case, {"type": kind, "affected_check_ids": [],
                                      "reason": "Idea adicional sin evidencia sobre el cálculo.",
                                      "decision_impact": "No modifica esta decisión."})
        after = engine.status(self.case)
        # The reported current closure, rather than total ledger length, must remain.
        self.assertEqual(before.get("state"), after.get("state"))
        with self.assertRaises(engine.EngineError):
            self.revise(self.revised_plan())

    def test_revision_cannot_change_scope_or_increase_budget(self):
        self.init()
        engine.run_case(self.case)
        engine.add_tip(self.case, self.material_tip())
        for what in ("objective", "budget"):
            with self.subTest(what=what):
                candidate = self.revised_plan()
                if what == "objective":
                    candidate["objective"] = "Otro objetivo más fácil."
                else:
                    candidate["budget"]["max_units"] += 100
                with self.assertRaises(engine.EngineError):
                    self.revise(candidate)

    def test_revision_cannot_modify_old_check_or_omit_link(self):
        self.init()
        engine.run_case(self.case)
        engine.add_tip(self.case, self.material_tip())
        for what in ("old", "link"):
            with self.subTest(what=what):
                candidate = self.revised_plan()
                if what == "old":
                    candidate["checks"][0]["params"]["expected"] = "100"
                else:
                    candidate["checks"][-1].pop("revises")
                with self.assertRaises(engine.EngineError):
                    self.revise(candidate)

    def test_critical_failure_cannot_be_erased_by_new_passing_check(self):
        self.plan["checks"][0]["params"]["expected"] = "100"
        self.init()
        engine.run_case(self.case)
        engine.add_tip(self.case, self.material_tip())
        self.revise(self.revised_plan())
        engine.run_case(self.case)
        with self.assertRaises(engine.EngineError):
            engine.propose_case(self.case, self.draft())

    def test_round_budget_is_not_reset_by_tip(self):
        self.plan["budget"]["max_rounds"] = 1
        self.init()
        engine.run_case(self.case)
        engine.add_tip(self.case, self.material_tip())
        with self.assertRaises(engine.EngineError):
            self.revise(self.revised_plan())

    def test_checks_and_units_exhaustion_cannot_hide_untested_checks(self):
        for limit in ("max_checks", "max_units"):
            with self.subTest(limit=limit):
                candidate = copy.deepcopy(self.plan)
                candidate["budget"][limit] = 2
                path = self.folder / (limit + ".json")
                path.write_text(json.dumps(candidate), encoding="utf-8")
                case = self.folder / limit
                engine.init_case(path, case)
                result = engine.run_case(case)
                self.assertEqual(result["state"], "BUDGET_EXHAUSTED")
                self.assertEqual(result["budget"]["checks_used"], 2)
                self.assertEqual(result["budget"]["units_used"], 2)
                self.assertNotIn("abstencion", result["results"])
                with self.assertRaises(engine.EngineError):
                    engine.close_case(case, self.decision)
                engine.add_tip(case, self.material_tip())
                revision = self.revised_plan()
                revision["budget"] = candidate["budget"]
                path.write_text(json.dumps(revision), encoding="utf-8")
                with self.assertRaises(engine.EngineError):
                    engine.revise_case(case, path)

    def test_tip_reopening_preserves_obsolete_conclusion_and_budget(self):
        self.init()
        self.finish()
        before = engine.status(self.case)
        engine.add_tip(self.case, self.material_tip())
        after = engine.status(self.case)
        self.assertEqual(after["state"], "REVIEW_REQUIRED")
        self.assertEqual(after["budget"]["checks_used"], before["budget"]["checks_used"])
        self.assertEqual(after["budget"]["units_used"], before["budget"]["units_used"])
        self.assertTrue(after["closures"][-1]["superseded"])
        self.assertEqual(after["closures"][-1]["generated_results"],
                         before["closures"][-1]["generated_results"])

    def test_duplicate_material_tip_and_unknown_reference_are_rejected(self):
        self.init()
        tip = self.material_tip()
        engine.add_tip(self.case, tip)
        with self.assertRaises(engine.EngineError):
            engine.add_tip(self.case, tip)
        unknown = dict(tip, affected_check_ids=["absent"])
        with self.assertRaises(engine.EngineError):
            engine.add_tip(self.case, unknown)

    def test_revision_cannot_weaken_a_critical_control(self):
        self.init()
        engine.run_case(self.case)
        engine.add_tip(self.case, self.material_tip())
        revision = self.revised_plan()
        revision["checks"][-1].update(critical=False, challenge=False)
        with self.assertRaises(engine.EngineError):
            self.revise(revision)

    def test_closure_must_account_for_discarded_branch(self):
        self.init()
        engine.run_case(self.case)
        draft = self.draft()
        draft["reasons_by_branch"].pop("alternativa")
        with self.assertRaises(engine.EngineError):
            engine.propose_case(self.case, draft)

    def prepare_documents(self):
        source = self.folder / "input"
        shutil.copytree(ROOT / "examples/documentos", source)
        self.case = self.folder / "document_case"
        self.plan = json.loads((source / "plan.json").read_text(encoding="utf-8"))
        self.plan["version"] = 2
        (source / "plan.json").write_text(json.dumps(self.plan), encoding="utf-8")
        engine.init_case(source / "plan.json", self.case)
        self.decision = {"mode": "results_only"}
        return source

    def test_source_is_snapshot_and_manual_judgment_stays_declared(self):
        source = self.prepare_documents()
        (source / "nota.txt").write_text("Changed original after init.", encoding="utf-8")
        self.finish()
        state = engine.status(self.case)
        self.assertEqual(state["results"]["revision_declarada"]["kind"], "declared")
        self.assertEqual(state["closures"][-1]["state"], "CLOSED_RESULTS")
        generated = state["closures"][-1]["generated_results"]
        self.assertTrue(any(item["kind"] == "declared" for item in generated))
        self.assertIn("declared", engine.render_report(self.case))
        self.assertTrue(engine.verify_case(self.case)["verified"])

    def test_tampered_snapshot_source_blocks_execution(self):
        self.prepare_documents()
        (self.case / "rounds/r001/sources/nota.txt").write_text("Altered evidence.", encoding="utf-8")
        with self.assertRaises(engine.EngineError):
            engine.run_case(self.case)

    def test_tampered_journal_blocks_verification(self):
        self.init()
        path = self.case / "journal.json"
        journal = json.loads(path.read_text(encoding="utf-8"))
        journal[0]["timestamp"] += 1
        path.write_text(json.dumps(journal), encoding="utf-8")
        with self.assertRaises(engine.EngineError):
            engine.verify_case(self.case)

    def test_missing_literal_support_cannot_be_rescued_by_manual_pass(self):
        source = self.folder / "false_source"
        shutil.copytree(ROOT / "examples/documentos", source)
        self.plan = json.loads((source / "plan.json").read_text(encoding="utf-8"))
        self.plan["version"] = 2
        (source / "plan.json").write_text(json.dumps(self.plan), encoding="utf-8")
        (source / "nota.txt").write_text("This source supplies neither quoted claim.", encoding="utf-8")
        engine.init_case(source / "plan.json", self.case)
        state = engine.run_case(self.case)
        self.assertEqual(state["results"]["revision_declarada"]["status"], "fail")
        with self.assertRaises(engine.EngineError):
            engine.propose_case(self.case, self.draft())

    def test_source_path_traversal_rejected_before_case_creation(self):
        self.plan["checks"][0].update(method="text_evidence",
            params={"path": "../outside.txt", "quote": "x", "locator": "line 1"})
        with self.assertRaises(engine.EngineError):
            self.init()
        self.assertFalse(self.case.exists())

    def test_elapsed_time_cannot_be_rescued_by_run(self):
        self.plan["budget"]["max_seconds"] = 1
        self.init()
        time.sleep(1.15)
        try:
            engine.run_case(self.case)
        except engine.EngineError:
            pass
        with self.assertRaises(engine.EngineError):
            engine.propose_case(self.case, self.draft())

    def test_modified_plan_file_is_detected(self):
        self.init()
        path = self.case / "rounds/r001/plan.json"
        content = json.loads(path.read_text(encoding="utf-8"))
        content["objective"] = "Alterado después del sello."
        path.write_text(json.dumps(content), encoding="utf-8")
        with self.assertRaises(engine.EngineError):
            engine.verify_case(self.case)

    def test_failed_adapter_attempt_is_not_retried(self):
        self.init()
        with patch.object(engine.adapters, "execute", side_effect=RuntimeError("induced QA failure")) as call:
            engine.run_case(self.case)
            count = call.call_count
            self.assertGreater(count, 0)
            try:
                engine.run_case(self.case)
            except engine.EngineError:
                pass
            self.assertEqual(call.call_count, count)
        with self.assertRaises(engine.EngineError):
            engine.propose_case(self.case, self.draft())


if __name__ == "__main__":
    unittest.main()
