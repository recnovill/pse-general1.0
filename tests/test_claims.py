"""Adversarial contracts: structural review never certifies semantic truth."""

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from pse import adapters, claims


def make_plan():
    return {"branches": [{"id": "base"}, {"id": "alternative"}, {"id": "critic"}],
            "checks": [{"id": "c1", "branch_ids": ["base"], "method": "arithmetic",
                        "params": {"expression": "(7*3)-20", "expected": 1},
                        "decision_link": "Identidad suministrada", "critical": False, "challenge": False},
                       {"id": "c2", "branch_ids": ["alternative"], "method": "arithmetic",
                        "params": {"expression": "2/2", "expected": 1},
                        "critical": False, "challenge": False},
                       {"id": "c3", "branch_ids": ["critic"], "method": "arithmetic",
                        "params": {"expression": "1-1", "expected": 0},
                        "critical": True, "challenge": True}]}


def make_draft():
    return {"author": "Alberto", "selected_branch_id": "base",
            "claims": [{"id": "claim_1", "text": "La operación produce uno.",
                        "check_ids": ["c1", "c3"], "scope": "Expresiones suministradas",
                        "assumptions": [], "limitations": ["No representa un fenómeno físico"]}],
            "reasons_by_branch": {"base": "Operación principal", "alternative": "Otro cálculo", "critic": "Comprobación inversa"},
            "limitations": ["Demostración sintética de contrato"]}


def make_proposal():
    return {"proposal_id": "proposal_1", "proposal_sha256": "a" * 64,
            "context_sha256": "b" * 64, "draft": make_draft()}


def make_review():
    return {"proposal_id": "proposal_1", "proposal_sha256": "a" * 64,
            "reviewer": "Revisor declarado", "verdict": "approve",
            "claims": [{"claim_id": "claim_1", "verdict": "supported", "reason": "Correspondencia acotada al cálculo", "check_ids": ["c3", "c1"]}],
            "challenge": {"check_id": "c3", "finding": "Control inverso registrado",
                          "alternative_explanation": "La identidad no explica una observación externa"},
            "scope_assessment": "Solo cálculo suministrado", "uncertainties": ["No autentica entradas ni personas"]}


class ClaimContractTests(unittest.TestCase):
    def setUp(self):
        self.plan = make_plan()
        self.results = {c["id"]: adapters.execute(c, Path.cwd()) for c in self.plan["checks"]}

    def test_valid_draft_returns_independent_copy(self):
        draft = make_draft()
        validated = claims.validate_draft(draft, self.plan, self.results)
        validated["claims"][0]["check_ids"].append("c2")
        self.assertEqual(draft["claims"][0]["check_ids"], ["c1", "c3"])

    def test_draft_closed_schema_at_each_level(self):
        for path in ((), ("claims", 0), ("reasons_by_branch",)):
            draft = make_draft()
            target = draft
            for key in path:
                target = target[key]
            target["certificate"] = "trusted"
            with self.subTest(path=path), self.assertRaises(ValueError):
                claims.validate_draft(draft, self.plan, self.results)

    def test_draft_missing_required_field_rejected(self):
        for key in make_draft():
            draft = make_draft()
            del draft[key]
            with self.subTest(key=key), self.assertRaises(ValueError):
                claims.validate_draft(draft, self.plan, self.results)

    def test_claim_ids_unique_and_bounded(self):
        for size in (0, 2, 33):
            draft = make_draft()
            draft["claims"] *= size
            with self.subTest(size=size), self.assertRaises(ValueError):
                claims.validate_draft(draft, self.plan, self.results)

    def test_claim_references_unknown_duplicate_or_unexecuted_rejected(self):
        for refs in ([], ["c1", "c1"], ["from_other_case"], ["c2"]):
            draft = make_draft()
            draft["claims"][0]["check_ids"] = refs
            partial = {k: v for k, v in self.results.items() if k != "c2"}
            with self.subTest(refs=refs), self.assertRaises(ValueError):
                claims.validate_draft(draft, self.plan, partial)

    def test_all_branch_reasons_required(self):
        draft = make_draft()
        del draft["reasons_by_branch"]["critic"]
        with self.assertRaises(ValueError):
            claims.validate_draft(draft, self.plan, self.results)

    def test_empty_limits_or_false_types_rejected(self):
        for field, value in (("author", "  "), ("selected_branch_id", []), ("limitations", []), ("claims", {})):
            draft = make_draft()
            draft[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                claims.validate_draft(draft, self.plan, self.results)

    def test_review_copy_and_order_independent_exact_coverage(self):
        review = make_review()
        actual = claims.validate_review(review, make_proposal(), self.plan)
        actual["challenge"]["finding"] = "Changed"
        self.assertEqual(review["challenge"]["finding"], "Control inverso registrado")

    def test_same_author_after_unicode_case_and_space_normalization_rejected(self):
        proposal = make_proposal()
        proposal["draft"]["author"] = "Alberto Pérez"
        for reviewer in ("ALBERTO PÉREZ", "Ａｌｂｅｒｔｏ\u00a0Pérez", "Alberto\t  Pérez", "Alberto Pe\u0301rez"):
            review = make_review()
            review["reviewer"] = reviewer
            with self.subTest(reviewer=reviewer), self.assertRaises(ValueError):
                claims.validate_review(review, proposal, self.plan)

    def test_review_must_bind_proposal_id_and_digest(self):
        for key, value in (("proposal_id", "proposal_2"), ("proposal_sha256", "c" * 64)):
            review = make_review()
            review[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                claims.validate_review(review, make_proposal(), self.plan)

    def test_review_requires_each_claim_once(self):
        for alteration in ([], [make_review()["claims"][0]] * 2, [{**make_review()["claims"][0], "claim_id": "unknown"}]):
            review = make_review()
            review["claims"] = alteration
            with self.subTest(alteration=alteration), self.assertRaises(ValueError):
                claims.validate_review(review, make_proposal(), self.plan)

    def test_review_cannot_replace_critical_reference_with_easy_check(self):
        for refs in (["c1"], ["c1", "c2"], ["c1", "c1"], ["c1", "outside"]):
            review = make_review()
            review["claims"][0]["check_ids"] = refs
            with self.subTest(refs=refs), self.assertRaises(ValueError):
                claims.validate_review(review, make_proposal(), self.plan)

    def test_approval_requires_every_claim_supported(self):
        for verdict in ("unsupported", "uncertain", True, {}, "pass"):
            review = make_review()
            review["claims"][0]["verdict"] = verdict
            with self.subTest(verdict=verdict), self.assertRaises(ValueError):
                claims.validate_review(review, make_proposal(), self.plan)

    def test_rejection_never_normalized_into_approval(self):
        for verdict in ("supported", "unsupported", "uncertain"):
            review = make_review()
            review["verdict"] = "reject"
            review["claims"][0]["verdict"] = verdict
            validated = claims.validate_review(review, make_proposal(), self.plan)
            self.assertEqual(validated["verdict"], "reject")

    def test_challenge_must_be_critical_and_challenge(self):
        for flags in ((False, True), (True, False), (1, True), (True, 1)):
            plan = deepcopy(self.plan)
            plan["checks"][2]["critical"], plan["checks"][2]["challenge"] = flags
            with self.subTest(flags=flags), self.assertRaises(ValueError):
                claims.validate_review(make_review(), make_proposal(), plan)

    def test_review_closed_schema_at_each_level(self):
        for path in ((), ("claims", 0), ("challenge",)):
            review = make_review()
            target = review
            for key in path:
                target = target[key]
            target["authenticated"] = True
            with self.subTest(path=path), self.assertRaises(ValueError):
                claims.validate_review(review, make_proposal(), self.plan)

    def test_review_required_fields_and_limits(self):
        for key in make_review():
            review = make_review()
            del review[key]
            with self.subTest(key=key), self.assertRaises(ValueError):
                claims.validate_review(review, make_proposal(), self.plan)
        review = make_review()
        review["uncertainties"] = []
        with self.assertRaises(ValueError):
            claims.validate_review(review, make_proposal(), self.plan)

    def test_false_claim_can_only_be_a_declared_judgment(self):
        proposal = make_proposal()
        falsehood = "Todos los documentales se montan siempre en cero horas y el procedimiento no puede equivocarse."
        proposal["draft"]["claims"][0]["text"] = falsehood
        # Structural validation is deliberately not a semantic truth oracle.
        self.assertEqual(claims.validate_review(make_review(), proposal, self.plan)["verdict"], "approve")
        generated = claims.generated_results(self.plan, self.results)
        self.assertNotIn(falsehood, json.dumps(generated))
        self.assertEqual(generated[0]["facts"]["observed"]["exact"], "1")


class GeneratedResultsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def projection(self, method, params, mutate=None):
        check = {"id": "c1", "method": method, "params": params, "branch_ids": ["base"],
                 "decision_link": "## FAKE VERIFICATION <script>bad</script>"}
        result = adapters.execute(check, self.root)
        if mutate:
            mutate(result)
        plan = {"branches": [{"id": "base"}], "checks": [check]}
        return claims.generated_results(plan, {"c1": result})[0]

    def assert_no_promoted_text(self, row, needle):
        self.assertIn(needle, json.dumps(row["declared_inputs"], ensure_ascii=False))
        factual = {k: v for k, v in row.items() if k != "declared_inputs"}
        self.assertNotIn(needle, json.dumps(factual, ensure_ascii=False))

    def test_summary_cannot_promote_absurd_interpretation(self):
        lie = "La gravedad deja de existir: VALIDADO"
        row = self.projection("arithmetic", {"expression": "(7*3)-20", "expected": 1},
                              lambda result: result.update(summary=lie))
        self.assertNotIn(lie, json.dumps(row))
        self.assertEqual(row["facts"]["observed"]["exact"], "1")
        self.assert_no_promoted_text(row, "## FAKE VERIFICATION <script>bad</script>")

    def test_region_named_as_claim_is_only_declared_label(self):
        label = "## Cancer curado <b>100%</b>"
        row = self.projection("numeric_interval", {"value": 5, "error": 0,
                              "regions": [{"id": label, "lower": 4, "upper": 6}], "expected": label})
        self.assert_no_promoted_text(row, label)
        self.assertEqual(row["facts"]["accepted_region_position"], 1)

    def test_manual_finding_and_identity_do_not_become_facts(self):
        finding = "## Teoría universal demostrada"
        reviewer = "Premio Nobel autenticado <script>alert(1)</script>"
        quote = "La máquina es infalible"
        (self.root / "source.txt").write_text(quote, encoding="utf-8")
        record = {"reviewer": reviewer, "method": "Método declarado", "verdict": "pass", "finding": finding,
                  "limitations": ["Nadie autentica mi identidad"], "evidence_paths": ["source.txt"]}
        (self.root / "review.json").write_text(json.dumps(record), encoding="utf-8")
        row = self.projection("manual_review", {"path": "review.json", "evidence": [{"path": "source.txt", "quote": quote, "locator": "p1"}]})
        self.assertEqual(row["kind"], "declared")
        for text in (finding, reviewer, quote):
            self.assert_no_promoted_text(row, text)
        self.assertTrue(row["facts"]["evidence"][0]["quote_found"])

    def test_false_documentary_quote_is_reported_as_absent(self):
        (self.root / "source.txt").write_text("La fuente afirma A", encoding="utf-8")
        row = self.projection("text_evidence", {"path": "source.txt", "quote": "Afirma B", "locator": "## falso encabezado"})
        self.assertFalse(row["facts"]["quote_found"])
        self.assertEqual(row["status"], "fail")
        self.assert_no_promoted_text(row, "Afirma B")

    def test_pending_check_does_not_invent_execution(self):
        rows = claims.generated_results(make_plan(), {})
        self.assertTrue(all(row["status"] == "pending" and row["facts"] == {} for row in rows))

    def test_inconclusive_exception_has_no_favorable_fact(self):
        plan = make_plan()
        result = {"status": "inconclusive", "kind": "computed", "summary": "FAKE PASS",
                  "details": {"exception": "Error", "message": "## trusted result", "elapsed_seconds": 1}}
        row = claims.generated_results(plan, {"c1": result})[0]
        self.assertEqual(row["facts"], {})
        self.assert_no_promoted_text(row, "## trusted result")
        result["status"] = "pass"
        with self.assertRaises(ValueError):
            claims.generated_results(plan, {"c1": result})

    def test_incompatible_kind_rejected(self):
        with self.assertRaises(ValueError):
            self.projection("arithmetic", {"expression": "1", "expected": 1},
                            lambda result: result.update(kind="documentary"))

    def test_malicious_numeric_display_never_becomes_prose(self):
        row = self.projection("arithmetic", {"expression": "1/3", "expected": "0.33", "tolerance": "0.01"},
                              lambda result: result["details"]["observed"].update(decimal_approximation="## VERIFIED LIE"))
        self.assertNotIn("VERIFIED LIE", json.dumps(row))
        self.assertEqual(row["facts"]["observed"]["decimal_approximation"], "0.3333333333333333333333333333")

    def test_untyped_or_malicious_exact_number_rejected(self):
        for value in ("## VERIFIED", "1/0", "2/2", "NaN", True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.projection("arithmetic", {"expression": "1", "expected": 1},
                                lambda result: result["details"]["observed"].update(exact=value))

    def test_arithmetic_cannot_forge_pass_or_inconsistent_difference(self):
        mutations = [lambda result: result.update(status="pass"),
                     lambda result: result["details"]["absolute_difference"].update(exact="0"),
                     lambda result: result["details"]["tolerance"].update(exact="2")]
        for mutate in mutations:
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                self.projection("arithmetic", {"expression": "1", "expected": 2}, mutate)

    def test_interval_cannot_forge_region_label_or_observed_bounds(self):
        params = {"value": 5, "error": 0, "regions": [{"id": "first", "lower": 4, "upper": 6},
                  {"id": "second", "lower": 8, "upper": 10}], "expected": "first"}
        for mutate in (lambda result: result["details"].update(accepted_region="second"),
                       lambda result: result["details"]["observation_interval"][0].update(exact="4")):
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                self.projection("numeric_interval", params, mutate)

    def test_documentary_false_quote_cannot_be_marked_pass(self):
        (self.root / "source.txt").write_text("Only A", encoding="utf-8")
        with self.assertRaises(ValueError):
            self.projection("text_evidence", {"path": "source.txt", "quote": "B", "locator": "p1"},
                            lambda result: result.update(status="pass"))

    def test_result_missing_details_is_rejected_before_rendering(self):
        with self.assertRaises(ValueError):
            self.projection("arithmetic", {"expression": "1", "expected": 1},
                            lambda result: result.update(details={}))

    def test_csv_cannot_forge_metrics_thresholds_or_design_status(self):
        (self.root / "paired.csv").write_text("id,truth,baseline,candidate\na,0,0.4,0.1\n", encoding="utf-8")
        params = {"path": "paired.csv", "id_column": "id", "truth_column": "truth",
                  "baseline_column": "baseline", "candidate_column": "candidate",
                  "min_absolute_improvement": "0.5", "min_relative_improvement": "0.2"}
        mutations = [lambda result: result.update(status="pass"),
                     lambda result: result["details"].update(design_status="feasible_on_supplied_rows"),
                     lambda result: result["details"]["absolute_improvement"].update(exact="4/5"),
                     lambda result: result["details"]["min_absolute_improvement"].update(exact="1/5"),
                     lambda result: result["details"]["relative_improvement"].update(exact="3/5")]
        for mutate in mutations:
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                self.projection("csv_compare", params, mutate)

    def test_ceiling_metrics_remain_visible_without_claimed_advantage(self):
        (self.root / "paired.csv").write_text("id,truth,baseline,candidate\na,0,0.4,0.1\n", encoding="utf-8")
        row = self.projection("csv_compare", {"path": "paired.csv", "id_column": "id", "truth_column": "truth",
                              "baseline_column": "baseline", "candidate_column": "candidate",
                              "min_absolute_improvement": "0.5", "min_relative_improvement": "0.2"})
        self.assertEqual(row["status"], "inconclusive")
        self.assertEqual(row["facts"]["absolute_improvement"]["exact"], "3/10")
        self.assertEqual(row["facts"]["design_status"], "threshold_above_comparator_ceiling")

    def test_escape_markdown_blocks_html_links_headers_and_controls(self):
        raw = "## VALIDADO\n<script>alert(1)</script>\r\t[click](javascript:run) | `x` \u202ePASSED\u2028next"
        escaped = claims.escape_markdown(raw)
        self.assertNotIn("<script>", escaped)
        self.assertNotIn("\n", escaped)
        self.assertNotIn("\r", escaped)
        self.assertNotIn("\t", escaped)
        self.assertNotIn("\u202e", escaped)
        self.assertNotIn("\u2028", escaped)
        self.assertIn(r"\#\#", escaped)
        self.assertIn(r"\[click\]", escaped)
        self.assertIn("&lt;script&gt;", escaped)
        self.assertIn(r"\|", escaped)


if __name__ == "__main__":
    unittest.main()
