"""Pure contracts for declared claims and bounded, generated result statements.

No model, semantic oracle, identity authentication, filesystem or clock. The
engine owns contextual digests, persistence, budgets and transition gates.
"""

from copy import deepcopy
from decimal import Decimal, InvalidOperation, localcontext
from fractions import Fraction
import html
import re
import unicodedata


KINDS = {"arithmetic": "computed", "numeric_interval": "computed",
         "csv_compare": "computed", "text_evidence": "documentary",
         "manual_review": "declared"}
_ID = re.compile(r"[A-Za-z][A-Za-z0-9_-]{0,63}\Z")
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_RATIONAL = re.compile(r"-?(?:0|[1-9][0-9]*)(?:/[1-9][0-9]*)?\Z")
_STATUS = {"pass", "fail", "inconclusive"}


def _keys(value, required, optional=()):
    if not isinstance(value, dict) or any(not isinstance(k, str) for k in value):
        raise ValueError("Se requiere un objeto con claves de texto")
    missing = set(required) - value.keys()
    unknown = value.keys() - set(required) - set(optional)
    if missing or unknown:
        raise ValueError(f"Campos ausentes={sorted(missing)}; desconocidos={sorted(unknown)}")


def _text(value, name, maximum=8000):
    if not isinstance(value, str) or not value.strip() or value != value.strip() or len(value) > maximum:
        raise ValueError(f"{name}: texto no vacío, acotado y sin espacios laterales requerido")
    return value


def _identifier(value, name):
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise ValueError(f"{name}: identificador inválido")
    return value


def _texts(value, name, minimum=1, maximum=32):
    if not isinstance(value, list) or not minimum <= len(value) <= maximum:
        raise ValueError(f"{name}: lista de {minimum} a {maximum} textos requerida")
    for item in value:
        _text(item, name)


def _references(value, known, name):
    if not isinstance(value, list) or not 1 <= len(value) <= len(known):
        raise ValueError(f"{name}: referencias no vacías y acotadas requeridas")
    for item in value:
        _identifier(item, name)
    if len(set(value)) != len(value) or not set(value) <= set(known):
        raise ValueError(f"{name}: referencia repetida o desconocida")


def _plan(plan):
    if not isinstance(plan, dict) or not isinstance(plan.get("checks"), list) or not isinstance(plan.get("branches"), list):
        raise ValueError("Plan sin checks o ramas")
    branches, checks = {}, {}
    for collection, target in ((plan["branches"], branches), (plan["checks"], checks)):
        for item in collection:
            if not isinstance(item, dict):
                raise ValueError("Entrada de plan inválida")
            identifier = _identifier(item.get("id"), "id de plan")
            if identifier in target:
                raise ValueError("Identificador de plan repetido")
            target[identifier] = item
    if not branches or not checks:
        raise ValueError("Plan sin checks o ramas")
    for check in checks.values():
        if not isinstance(check.get("method"), str) or check["method"] not in KINDS:
            raise ValueError("Método de resultado desconocido")
    return branches, checks


def _results(results, checks):
    if not isinstance(results, dict) or any(not isinstance(cid, str) or cid not in checks for cid in results):
        raise ValueError("Resultados con referencias desconocidas")
    for cid, result in results.items():
        _keys(result, {"status", "kind", "summary", "details"})
        if not isinstance(result["status"], str) or result["status"] not in _STATUS:
            raise ValueError("Estado de resultado desconocido")
        if result["kind"] != KINDS[checks[cid]["method"]]:
            raise ValueError("Tipo de evidencia incompatible con el método")
        if not isinstance(result["summary"], str) or not isinstance(result["details"], dict):
            raise ValueError("Resultado mal formado")


def _draft(draft, branches, checks):
    _keys(draft, {"author", "selected_branch_id", "claims", "reasons_by_branch", "limitations"})
    _text(draft["author"], "author", 256)
    selected = _identifier(draft["selected_branch_id"], "selected_branch_id")
    if selected not in branches:
        raise ValueError("Rama seleccionada desconocida")
    claims = draft["claims"]
    if not isinstance(claims, list) or not 1 <= len(claims) <= 32:
        raise ValueError("Se requieren entre 1 y 32 afirmaciones")
    identifiers = set()
    for claim in claims:
        _keys(claim, {"id", "text", "check_ids", "scope", "assumptions", "limitations"})
        identifier = _identifier(claim["id"], "claim.id")
        if identifier in identifiers:
            raise ValueError("ID de afirmación repetido")
        identifiers.add(identifier)
        _text(claim["text"], "claim.text")
        _text(claim["scope"], "claim.scope")
        _references(claim["check_ids"], checks, "claim.check_ids")
        _texts(claim["assumptions"], "claim.assumptions", minimum=0)
        _texts(claim["limitations"], "claim.limitations")
    _keys(draft["reasons_by_branch"], set(branches))
    for reason in draft["reasons_by_branch"].values():
        _text(reason, "reasons_by_branch")
    _texts(draft["limitations"], "limitations")


def validate_draft(draft, plan, results):
    """Validate declarations/references, without certifying semantic relevance."""
    branches, checks = _plan(plan)
    _results(results, checks)
    _draft(draft, branches, checks)
    for claim in draft["claims"]:
        if not set(claim["check_ids"]) <= results.keys():
            raise ValueError("La afirmación cita un check todavía no ejecutado")
    return deepcopy(draft)


def _identity(value):
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def validate_review(review, proposal, plan):
    """Validate an explicitly declared review; labels do not prove identities."""
    branches, checks = _plan(plan)
    _keys(proposal, {"proposal_id", "proposal_sha256", "context_sha256", "draft"})
    _identifier(proposal["proposal_id"], "proposal_id")
    for field in ("proposal_sha256", "context_sha256"):
        if not isinstance(proposal[field], str) or not _HASH.fullmatch(proposal[field]):
            raise ValueError(f"{field}: SHA-256 normalizado requerido")
    _draft(proposal["draft"], branches, checks)
    _keys(review, {"proposal_id", "proposal_sha256", "reviewer", "verdict", "claims", "challenge", "scope_assessment", "uncertainties"})
    if review["proposal_id"] != proposal["proposal_id"] or review["proposal_sha256"] != proposal["proposal_sha256"]:
        raise ValueError("La revisión no corresponde a esta propuesta y huella")
    _text(review["reviewer"], "reviewer", 256)
    if _identity(review["reviewer"]) == _identity(proposal["draft"]["author"]):
        raise ValueError("Autor y revisor deben tener etiquetas distintas normalizadas")
    if not isinstance(review["verdict"], str) or review["verdict"] not in {"approve", "reject"}:
        raise ValueError("verdict requiere approve o reject")
    expected = {claim["id"]: claim for claim in proposal["draft"]["claims"]}
    if not isinstance(review["claims"], list) or len(review["claims"]) != len(expected):
        raise ValueError("La revisión debe cubrir exactamente todas las afirmaciones")
    seen = set()
    for claim in review["claims"]:
        _keys(claim, {"claim_id", "verdict", "reason", "check_ids"})
        cid = _identifier(claim["claim_id"], "claim_id")
        if cid not in expected or cid in seen:
            raise ValueError("Afirmación de revisión repetida o desconocida")
        seen.add(cid)
        if not isinstance(claim["verdict"], str) or claim["verdict"] not in {"supported", "unsupported", "uncertain"}:
            raise ValueError("Veredicto de afirmación desconocido")
        if review["verdict"] == "approve" and claim["verdict"] != "supported":
            raise ValueError("Una aprobación requiere todas las afirmaciones supported")
        _text(claim["reason"], "claim.reason")
        _references(claim["check_ids"], checks, "review.check_ids")
        if set(claim["check_ids"]) != set(expected[cid]["check_ids"]):
            raise ValueError("La revisión debe cubrir exactamente los checks de cada afirmación")
    challenge = review["challenge"]
    _keys(challenge, {"check_id", "finding", "alternative_explanation"})
    cid = _identifier(challenge["check_id"], "challenge.check_id")
    if cid not in checks or checks[cid].get("critical") is not True or checks[cid].get("challenge") is not True:
        raise ValueError("La objeción requiere un check marcado critical y challenge")
    _text(challenge["finding"], "challenge.finding")
    _text(challenge["alternative_explanation"], "challenge.alternative_explanation")
    _text(review["scope_assessment"], "scope_assessment")
    _texts(review["uncertainties"], "uncertainties")
    return deepcopy(review)


def escape_markdown(text):
    """Render untrusted text inline: no HTML, blocks, links or hidden controls."""
    if not isinstance(text, str):
        raise ValueError("escape_markdown requiere texto")
    visible = []
    for char in text:
        if unicodedata.category(char).startswith("C") or char in "\u2028\u2029":
            visible.append(f"\\u{ord(char):04x}")
        else:
            visible.append(char)
    escaped = re.sub(r"([\\`*_{}\[\]()#+\-.!|:~])", r"\\\1", "".join(visible))
    return html.escape(escaped, quote=True)


def _number(value):
    if not isinstance(value, dict) or set(value) != {"exact", "decimal_approximation"}:
        raise ValueError("Resultado numérico sin representación tipada")
    raw = value["exact"]
    if not isinstance(raw, str) or len(raw) > 2500 or not _RATIONAL.fullmatch(raw):
        raise ValueError("Resultado racional inválido")
    rational = Fraction(raw)
    if str(rational) != raw or max(abs(rational.numerator).bit_length(), rational.denominator.bit_length()) > 4096:
        raise ValueError("Resultado racional no canónico o demasiado grande")
    # Never copy an untrusted decimal display into generated factual prose.
    with localcontext() as context:
        context.prec = 28
        approximate = str(Decimal(rational.numerator) / Decimal(rational.denominator))
    return {"exact": str(rational), "decimal_approximation": approximate}


def _boolean(value):
    if type(value) is not bool:
        raise ValueError("Resultado booleano requerido")
    return value


def _input_number(value):
    """Parse an already planned decimal defensively, without adapter execution."""
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise ValueError("Parámetro numérico inválido")
    if isinstance(value, int) and value.bit_length() > 420:
        raise ValueError("Parámetro numérico demasiado grande")
    raw = str(value).strip()
    if len(raw) > 128:
        raise ValueError("Parámetro numérico demasiado largo")
    try:
        decimal = Decimal(raw)
    except InvalidOperation as exc:
        raise ValueError("Parámetro decimal inválido") from exc
    if not decimal.is_finite() or abs(decimal.as_tuple().exponent) > 200:
        raise ValueError("Parámetro decimal fuera de límites")
    return Fraction(decimal)


def _require_status(result, expected):
    if result["status"] != expected:
        raise ValueError("Estado de resultado incompatible con sus hechos tipados")


def _evidence_facts(detail, specification):
    if not isinstance(detail, dict):
        raise ValueError("Resultado documental inválido")
    digest = detail.get("sha256")
    if not isinstance(digest, str) or not _HASH.fullmatch(digest):
        raise ValueError("Huella documental inválida")
    facts = {key: _boolean(detail.get(key)) for key in ("quote_found", "expected_hash_matches", "passed")}
    if facts["passed"] != (facts["quote_found"] and facts["expected_hash_matches"]):
        raise ValueError("Resultado documental contradictorio")
    expected = specification.get("sha256")
    matches = expected is None or isinstance(expected, str) and digest == expected.lower()
    if facts["expected_hash_matches"] != matches:
        raise ValueError("Correspondencia de huella incompatible con el plan")
    facts["source_sha256"] = digest
    return facts


def generated_results(plan, results):
    """Return fixed statements and typed facts; every external label is declared.

    This projection cannot endorse adapter summaries, quotes, region names,
    reviewer identities or interpretations. Missing checks remain pending.
    """
    _, checks = _plan(plan)
    _results(results, checks)
    rows = []
    for cid, check in checks.items():
        method = check["method"]
        declared = {"check_id": cid, "branch_ids": deepcopy(check.get("branch_ids", [])),
                    "decision_link": deepcopy(check.get("decision_link")),
                    "params": deepcopy(check.get("params", {}))}
        row = {"method": method, "status": "pending", "kind": KINDS[method],
               "statement": "Comprobación todavía no ejecutada.", "facts": {},
               "limitations": ["Los datos y criterios fueron suministrados; su procedencia y pertinencia requieren revisión."],
               "declared_inputs": declared}
        rows.append(row)
        if cid not in results:
            continue
        result, detail = results[cid], results[cid]["details"]
        row["status"] = result["status"]
        facts = row["facts"]
        if "exception" in detail or "interrupted" in detail:
            if result["status"] != "inconclusive":
                raise ValueError("Una excepción o interrupción no puede aportar evidencia favorable")
            row["statement"] = "Intento sin resultado concluyente; no aporta evidencia favorable."
            declared["execution_diagnostic"] = {key: deepcopy(detail[key]) for key in ("exception", "message", "interrupted") if key in detail}
            continue
        try:
            if method == "arithmetic":
                facts.update({key: _number(detail[key]) for key in ("observed", "expected", "absolute_difference", "tolerance")})
                observed, expected, difference, tolerance = (Fraction(facts[key]["exact"]) for key in ("observed", "expected", "absolute_difference", "tolerance"))
                if tolerance < 0 or difference != abs(observed - expected):
                    raise ValueError("Diferencia aritmética o tolerancia incoherente")
                if expected != _input_number(check["params"]["expected"]) or tolerance != _input_number(check["params"].get("tolerance", 0)):
                    raise ValueError("Criterio aritmético distinto del plan")
                _require_status(result, "pass" if difference <= tolerance else "fail")
                row["statement"] = "Cálculo racional y comparación con el valor y la tolerancia suministrados."
                row["limitations"].append("No acredita una interpretación física ni una afirmación ajena a esta operación.")
            elif method == "numeric_interval":
                interval = detail["observation_interval"]
                if not isinstance(interval, list) or len(interval) != 2:
                    raise ValueError("Intervalo de resultado inválido")
                facts["observation_interval"] = [_number(x) for x in interval]
                lower, upper = (Fraction(x["exact"]) for x in facts["observation_interval"])
                value, error = _input_number(check["params"]["value"]), _input_number(check["params"]["error"])
                if error < 0 or (lower, upper) != (value - error, value + error):
                    raise ValueError("Intervalo incoherente con valor y error suministrados")
                labels = [r["id"] for r in check["params"]["regions"]]
                for key in ("accepted_region", "expected_region"):
                    value = detail[key]
                    if value is not None and (not isinstance(value, str) or value not in labels):
                        raise ValueError("Región de resultado desconocida")
                    facts[key + "_position"] = labels.index(value) + 1 if value is not None else None
                    declared[key] = value
                contained = [region["id"] for region in check["params"]["regions"]
                             if _input_number(region["lower"]) <= lower and upper <= _input_number(region["upper"])]
                actual = contained[0] if len(contained) == 1 else None
                if detail["accepted_region"] != actual or detail["expected_region"] != check["params"]["expected"]:
                    raise ValueError("Clasificación numérica incompatible con el plan")
                _require_status(result, "pass" if actual == check["params"]["expected"] else "fail")
                row["statement"] = "Contención numérica del intervalo; las posiciones de región se cuentan desde 1 en la entrada."
                row["limitations"].append("Los nombres de las regiones son etiquetas aportadas y no conclusiones verificadas; el error también fue aportado.")
            elif method == "csv_compare":
                count = detail["count"]
                if type(count) is not int or not 1 <= count <= 10000:
                    raise ValueError("Número de filas inválido")
                facts["count"] = count
                for key in ("baseline_mae", "candidate_mae", "absolute_improvement", "min_absolute_improvement", "min_relative_improvement", "max_possible_absolute_improvement"):
                    facts[key] = _number(detail[key])
                facts["relative_improvement"] = _number(detail["relative_improvement"]) if detail["relative_improvement"] is not None else None
                design = detail["design_status"]
                if not isinstance(design, str) or design not in {"threshold_above_comparator_ceiling", "relative_improvement_undefined", "feasible_on_supplied_rows"}:
                    raise ValueError("Estado de diseño desconocido")
                facts["design_status"] = design
                baseline, candidate, absolute, minimum_absolute, minimum_relative, ceiling = (Fraction(facts[key]["exact"]) for key in
                    ("baseline_mae", "candidate_mae", "absolute_improvement", "min_absolute_improvement", "min_relative_improvement", "max_possible_absolute_improvement"))
                relative = Fraction(facts["relative_improvement"]["exact"]) if facts["relative_improvement"] is not None else None
                if baseline < 0 or candidate < 0 or absolute != baseline - candidate or ceiling != baseline:
                    raise ValueError("Métricas MAE incoherentes")
                if minimum_absolute < 0 or not 0 <= minimum_relative <= 1 or minimum_absolute == minimum_relative == 0:
                    raise ValueError("Umbrales MAE inválidos")
                if minimum_absolute != _input_number(check["params"]["min_absolute_improvement"]) or minimum_relative != _input_number(check["params"]["min_relative_improvement"]):
                    raise ValueError("Umbrales MAE distintos del plan")
                if relative != (absolute / baseline if baseline else None):
                    raise ValueError("Mejora relativa incompatible con MAE de referencia")
                expected_design = ("threshold_above_comparator_ceiling" if minimum_absolute > baseline else
                                   "relative_improvement_undefined" if baseline == 0 else "feasible_on_supplied_rows")
                if design != expected_design:
                    raise ValueError("Estado de diseño incompatible con métricas y criterios")
                expected_status = ("inconclusive" if design != "feasible_on_supplied_rows" else
                                   "pass" if absolute >= minimum_absolute and relative >= minimum_relative else "fail")
                _require_status(result, expected_status)
                row["statement"] = "Comparación descriptiva del MAE sobre todas las filas suministradas."
                if design == "threshold_above_comparator_ceiling":
                    row["statement"] = "El mínimo absoluto fijado supera la mejora máxima posible sobre estas filas; no se declara ventaja."
                row["limitations"].append("No prueba generalización, causalidad, independencia ni significación estadística.")
            elif method == "text_evidence":
                facts.update(_evidence_facts(detail, check["params"]))
                _require_status(result, "pass" if facts["passed"] else "fail")
                row["statement"] = "Búsqueda literal de una cita y comprobación de la huella prevista, cuando fue aportada."
                row["limitations"].append("No comprueba verdad, autoría, fecha, interpretación ni exactitud del localizador declarado.")
            else:
                evidence = detail["evidence"]
                if not isinstance(evidence, list) or not 1 <= len(evidence) <= 32:
                    raise ValueError("Respaldos de revisión inválidos")
                specifications = check["params"]["evidence"]
                if len(evidence) != len(specifications):
                    raise ValueError("Número de respaldos distinto del plan")
                facts["evidence"] = [_evidence_facts(item, spec) for item, spec in zip(evidence, specifications)]
                verdict = detail["verdict_declared"]
                if not isinstance(verdict, str) or verdict not in _STATUS:
                    raise ValueError("Dictamen declarado desconocido")
                _require_status(result, verdict if all(item["passed"] for item in facts["evidence"]) else "fail")
                declared["review_record"] = {key: deepcopy(detail[key]) for key in ("reviewer_declared", "method_declared", "finding_declared", "verdict_declared", "limitations")}
                row["statement"] = "Registro de revisión aportado; comprobaciones documentales detalladas por separado."
                row["limitations"].append("El juicio, la identidad y la independencia del revisor siguen siendo declarados; este registro no aprueba una propuesta de cierre.")
        except (KeyError, TypeError, IndexError) as exc:
            raise ValueError("Resultado sin los hechos tipados requeridos para su método") from exc
    return rows
