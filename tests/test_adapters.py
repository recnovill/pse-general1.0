"""Technical regression and adversarial tests, not scientific efficacy trials."""

import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest

from pse import adapters


def check(method, **params):
    return {"method": method, "params": params}


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def write(self, name, data):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(data, dict):
            data = json.dumps(data, ensure_ascii=False)
        path.write_text(data, encoding="utf-8")
        return path

    def run_check(self, item):
        result = adapters.execute(item, self.root)
        self.assertEqual(set(result), {"status", "kind", "summary", "details"})
        json.dumps(result, allow_nan=False)
        return result

    def csv_spec(self, **changes):
        params = dict(path="data/paired.csv", id_column="id", truth_column="truth",
                      baseline_column="baseline", candidate_column="candidate",
                      min_absolute_improvement="0.2", min_relative_improvement="0.1")
        params.update(changes)
        return check("csv_compare", **params)

    def manual_spec(self, **review_changes):
        self.write("source.txt", "La observación quedó registrada.")
        review = dict(reviewer="Revisor declarado", method="Revisión de contenido",
                      verdict="pass", finding="La observación consta en el registro",
                      limitations=["No acredita autenticidad externa"], evidence_paths=["source.txt"])
        review.update(review_changes)
        self.write("review.json", review)
        return check("manual_review", path="review.json", evidence=[dict(path="source.txt", quote="observación", locator="párrafo 1")])

    def test_decimal_arithmetic_is_exact(self):
        result = self.run_check(check("arithmetic", expression="0.1 + 0.2", expected="0.3"))
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["details"]["observed"]["exact"], "3/10")
        self.assertEqual(result["kind"], "computed")

    def test_variables_and_rational_expression(self):
        item = check("arithmetic", expression="(a - b)**2 / 3", variables={"a": "5", "b": "2"}, expected=3)
        self.assertEqual(self.run_check(item)["status"], "pass")

    def test_wrong_solution_is_rejected(self):
        result = self.run_check(check("arithmetic", expression="2 + 2", expected=5))
        self.assertEqual(result["status"], "fail")

    def test_tolerance_boundary_is_exact(self):
        self.assertEqual(self.run_check(check("arithmetic", expression="1.1", expected=1, tolerance="0.1"))["status"], "pass")
        self.assertEqual(self.run_check(check("arithmetic", expression="1.10000000000001", expected=1, tolerance="0.1"))["status"], "fail")

    def test_calls_attributes_comprehensions_rejected(self):
        for expr in ("__import__('os').getcwd()", "(1).__class__", "[x for x in [1]]", "abs(-2)", "True", "'2'", "1//2", "1%2"):
            with self.subTest(expr=expr), self.assertRaises(ValueError):
                adapters.validate(check("arithmetic", expression=expr, expected=0))

    def test_large_or_undefined_expressions_rejected(self):
        for expr in ("10**1000000", "2**0.5", "0**0", "0**-1", "1/0", "2**12**12", "+".join(["1"] * 100)):
            with self.subTest(expr=expr), self.assertRaises(ValueError):
                adapters.validate(check("arithmetic", expression=expr, expected=0))

    def test_unbound_names_rejected(self):
        with self.assertRaises(ValueError):
            adapters.validate(check("arithmetic", expression="x + 1", expected=1))

    def test_nonfinite_bool_and_oversized_numbers_rejected(self):
        for number in (True, float("nan"), float("inf"), "NaN", "-Infinity", "1e10000", 10**200):
            with self.subTest(number=str(number)), self.assertRaises(ValueError):
                adapters.validate(check("arithmetic", expression="1", expected=number))

    def test_closed_params_reject_typo(self):
        with self.assertRaises(ValueError):
            adapters.validate(check("arithmetic", expression="1", expected=1, tolernce=1))

    def test_non_string_methods_rejected_cleanly(self):
        for method in ([], {}, None, True, 5):
            with self.subTest(method=method), self.assertRaises(ValueError):
                adapters.validate(check(method))

    def test_numeric_containment_and_unresolved(self):
        params = dict(value="5", error="0.1", regions=[dict(id="a", lower=4, upper=6), dict(id="b", lower=8, upper=10)], expected="a")
        self.assertEqual(self.run_check(check("numeric_interval", **params))["status"], "pass")
        params.update(value="6", expected=None)
        result = self.run_check(check("numeric_interval", **params))
        self.assertEqual(result["status"], "pass")
        self.assertIsNone(result["details"]["accepted_region"])

    def test_numeric_wrong_region_fails(self):
        item = check("numeric_interval", value=5, error=0, regions=[dict(id="a", lower=4, upper=6), dict(id="b", lower=8, upper=10)], expected="b")
        self.assertEqual(self.run_check(item)["status"], "fail")

    def test_touching_regions_and_duplicate_ids_rejected(self):
        for regions in ([dict(id="a", lower=0, upper=1), dict(id="b", lower=1, upper=2)], [dict(id="a", lower=0, upper=1), dict(id="a", lower=2, upper=3)]):
            with self.assertRaises(ValueError):
                adapters.validate(check("numeric_interval", value=1, error=0, regions=regions, expected=None))

    def test_numeric_bool_expected_and_negative_error_rejected(self):
        for overrides in (dict(expected=True), dict(error=-1)):
            params = dict(value=1, error=0, regions=[dict(id="a", lower=0, upper=2)], expected="a")
            params.update(overrides)
            with self.assertRaises(ValueError):
                adapters.validate(check("numeric_interval", **params))

    def test_csv_paired_mae_both_thresholds(self):
        self.write("data/paired.csv", "id,truth,baseline,candidate\na,0,2,1\nb,4,6,4\n")
        result = self.run_check(self.csv_spec())
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["details"]["count"], 2)
        self.assertEqual(result["details"]["absolute_improvement"]["exact"], "3/2")
        self.assertEqual(result["details"]["relative_improvement"]["exact"], "3/4")
        self.assertEqual(self.run_check(self.csv_spec(min_absolute_improvement=2))["status"], "fail")
        self.assertEqual(self.run_check(self.csv_spec(min_relative_improvement="0.8"))["status"], "fail")

    def test_csv_adverse_result_preserved(self):
        self.write("data/paired.csv", "id,truth,baseline,candidate\na,0,1,2\n")
        result = self.run_check(self.csv_spec())
        self.assertEqual(result["status"], "fail")
        self.assertEqual(result["details"]["absolute_improvement"]["exact"], "-1")

    def test_csv_zero_baseline_is_inconclusive(self):
        self.write("data/paired.csv", "id,truth,baseline,candidate\na,0,0,0\n")
        result = self.run_check(self.csv_spec())
        self.assertEqual(result["status"], "inconclusive")
        self.assertIsNone(result["details"]["relative_improvement"])

    def test_csv_impossible_absolute_threshold_preserves_metrics(self):
        self.write("data/paired.csv", "id,truth,baseline,candidate\na,0,0.4,0.1\n")
        result = self.run_check(self.csv_spec(min_absolute_improvement="0.5", min_relative_improvement="0.2"))
        self.assertEqual(result["status"], "inconclusive")
        self.assertEqual(result["details"]["design_status"], "threshold_above_comparator_ceiling")
        for key, exact in (("baseline_mae", "2/5"), ("candidate_mae", "1/10"),
                           ("absolute_improvement", "3/10"), ("relative_improvement", "3/4"),
                           ("min_absolute_improvement", "1/2"), ("max_possible_absolute_improvement", "2/5")):
            self.assertEqual(result["details"][key]["exact"], exact)

    def test_csv_ceiling_equality_can_pass_with_perfect_candidate(self):
        self.write("data/paired.csv", "id,truth,baseline,candidate\na,0,0.4,0\n")
        result = self.run_check(self.csv_spec(min_absolute_improvement="0.4", min_relative_improvement=1))
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["details"]["design_status"], "feasible_on_supplied_rows")

    def test_csv_relative_threshold_above_one_rejected(self):
        for value in ("1.0000000000000000000001", 2):
            with self.subTest(value=value), self.assertRaises(ValueError):
                adapters.validate(self.csv_spec(min_relative_improvement=value))

    def test_csv_zero_baseline_relative_only_remains_undefined(self):
        self.write("data/paired.csv", "id,truth,baseline,candidate\na,0,0,1\n")
        result = self.run_check(self.csv_spec(min_absolute_improvement=0))
        self.assertEqual(result["status"], "inconclusive")
        self.assertEqual(result["details"]["design_status"], "relative_improvement_undefined")
        self.assertEqual(result["details"]["absolute_improvement"]["exact"], "-1")
        self.assertIsNone(result["details"]["relative_improvement"])

    def test_csv_ceiling_does_not_hide_adverse_candidate(self):
        self.write("data/paired.csv", "id,truth,baseline,candidate\na,0,0.4,2\n")
        result = self.run_check(self.csv_spec(min_absolute_improvement="0.5"))
        self.assertEqual(result["status"], "inconclusive")
        self.assertEqual(result["details"]["absolute_improvement"]["exact"], "-8/5")
        self.assertEqual(result["details"]["relative_improvement"]["exact"], "-4")

    def test_csv_duplicate_cohort_ids_rejected(self):
        self.write("data/paired.csv", "id,truth,baseline,candidate\na,0,2,1\na,1,3,2\n")
        with self.assertRaises(ValueError):
            self.run_check(self.csv_spec())

    def test_csv_missing_malformed_nonfinite_rejected(self):
        contents = ["id,truth,baseline,candidate\n", "id,truth,baseline,candidate\na,0,2\n", "id,truth,baseline,candidate\na,0,2,NaN\n", "id,truth,baseline,baseline,candidate\na,0,2,3,1\n", "id,truth,baseline,candidate\n a,0,2,1\n"]
        for text in contents:
            self.write("data/paired.csv", text)
            with self.subTest(text=text), self.assertRaises(ValueError):
                self.run_check(self.csv_spec())

    def test_csv_unsupported_metric_rejected(self):
        with self.assertRaises(ValueError):
            adapters.validate(self.csv_spec(metric="p_value"))

    def test_csv_zero_thresholds_cannot_call_equality_advantage(self):
        with self.assertRaises(ValueError):
            adapters.validate(self.csv_spec(min_absolute_improvement=0, min_relative_improvement=0))
        self.write("data/paired.csv", "id,truth,baseline,candidate\na,0,2,2\n")
        self.assertEqual(self.run_check(self.csv_spec())["status"], "fail")

    def test_literal_quote_hash_is_documentary(self):
        path = self.write("source.txt", "Árbol y río.\nUna observación.")
        item = check("text_evidence", path="source.txt", quote="Una observación.", locator="línea 2", sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        result = self.run_check(item)
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["kind"], "documentary")

    def test_literal_false_quote_and_bad_hash_fail(self):
        self.write("source.txt", "La fuente dice A.")
        for params in (dict(path="source.txt", quote="dice B", locator="p1"), dict(path="source.txt", quote="dice A", locator="p1", sha256="0" * 64)):
            with self.subTest(params=params):
                self.assertEqual(self.run_check(check("text_evidence", **params))["status"], "fail")

    def test_manual_review_never_becomes_computed(self):
        result = self.run_check(self.manual_spec())
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["kind"], "declared")
        self.assertIn("identidad", result["details"]["limitation"])

    def test_manual_adverse_and_inconclusive_preserved(self):
        for verdict in ("fail", "inconclusive"):
            with self.subTest(verdict=verdict):
                result = self.run_check(self.manual_spec(verdict=verdict))
                self.assertEqual(result["status"], verdict)
                self.assertEqual(result["kind"], "declared")

    def test_manual_without_support_rejected(self):
        for changes in (dict(evidence_paths=[]), dict(evidence_paths=["elsewhere.txt"]), dict(limitations=[]), dict(reviewer="")):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.run_check(self.manual_spec(**changes))

    def test_manual_nonexistent_quote_forces_fail(self):
        item = self.manual_spec()
        item["params"]["evidence"][0]["quote"] = "Cita inexistente"
        self.assertEqual(self.run_check(item)["status"], "fail")

    def test_manual_duplicate_json_keys_rejected(self):
        item = self.manual_spec()
        self.write("review.json", '{"verdict":"fail","verdict":"pass"}')
        with self.assertRaises(ValueError):
            self.run_check(item)

    def test_manual_non_string_verdict_rejected_cleanly(self):
        for verdict in ([], {}, True):
            with self.subTest(verdict=verdict), self.assertRaises(ValueError):
                self.run_check(self.manual_spec(verdict=verdict))

    def test_sources_cover_manual_record_and_evidence(self):
        item = self.manual_spec()
        self.assertEqual(adapters.source_paths(item), ["review.json", "source.txt"])
        self.assertEqual(adapters.source_paths(check("arithmetic", expression="1", expected=1)), [])

    def test_paths_reject_escape_and_windows_aliases(self):
        for path in ("../secret", "/tmp/a", "C:\\secret", "a:stream", "a//b", "./a", "NUL.txt", "a/COM1", "a/filename.", "a/filename ", "a/../b"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                adapters.validate(check("text_evidence", path=path, quote="x", locator="p1"))

    def test_missing_files_are_errors(self):
        with self.assertRaises(FileNotFoundError):
            self.run_check(check("text_evidence", path="absent.txt", quote="x", locator="p1"))

    def test_binary_and_oversized_sources_rejected(self):
        path = self.root / "source.txt"
        for content in (b"\xff\xfe\x00", b"a" * (adapters.MAX_FILE_BYTES + 1)):
            path.write_bytes(content)
            with self.assertRaises(ValueError):
                self.run_check(check("text_evidence", path="source.txt", quote="a", locator="p1"))

    def test_symlink_source_rejected_when_supported(self):
        self.write("source.txt", "evidence")
        link = self.root / "link.txt"
        try:
            link.symlink_to(self.root / "source.txt")
        except (OSError, NotImplementedError):
            self.skipTest("La cuenta no puede crear symlinks; validación de rutas restante ejecutada")
        with self.assertRaises(ValueError):
            self.run_check(check("text_evidence", path="link.txt", quote="evidence", locator="p1"))


if __name__ == "__main__":
    unittest.main()
