"""Bounded deterministic checks for PSE General.

No network, subprocess, eval, arbitrary imports or model calls. A successful
documentary or declared check does not authenticate the underlying claim.
Exact decimal comparisons follow the Fraction principle used by PSE-R.
"""

from __future__ import annotations

import ast
import csv
import hashlib
import io
import json
import math
import re
import stat
from decimal import Decimal, InvalidOperation, localcontext
from fractions import Fraction
from pathlib import Path


METHODS = frozenset({"arithmetic", "numeric_interval", "csv_compare", "text_evidence", "manual_review"})
MAX_FILE_BYTES = 2_000_000
MAX_ROWS = 10_000
MAX_EXPR_LENGTH = 2048
MAX_AST_NODES = 160
MAX_RATIONAL_BITS = 4096
_NUMBER = re.compile(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?\Z")
_NAME = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,31}\Z")
_HEX = re.compile(r"[0-9a-fA-F]{64}\Z")
_DEVICES = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}


def _text(value, name, maximum=4096):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError(f"{name}: texto no vacío de hasta {maximum} caracteres requerido")
    return value


def _keys(value, required, optional=()):
    if not isinstance(value, dict):
        raise ValueError("Se requiere un objeto JSON")
    if any(not isinstance(key, str) for key in value):
        raise ValueError("Las claves del objeto deben ser cadenas")
    missing = set(required) - value.keys()
    unknown = value.keys() - set(required) - set(optional)
    if missing or unknown:
        raise ValueError(f"Campos ausentes={sorted(missing)}; desconocidos={sorted(unknown)}")


def _bounded(value: Fraction):
    if max(abs(value.numerator).bit_length(), value.denominator.bit_length()) > MAX_RATIONAL_BITS:
        raise ValueError("El cálculo excede el límite de tamaño racional")
    return value


def _number(value, name="número"):
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise ValueError(f"{name}: número decimal finito requerido, sin booleanos")
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"{name}: valor no finito")
    if isinstance(value, int) and value.bit_length() > 420:
        raise ValueError(f"{name}: valor demasiado grande")
    raw = str(value).strip()
    if len(raw) > 128 or not _NUMBER.fullmatch(raw):
        raise ValueError(f"{name}: representación decimal inválida")
    try:
        dec = Decimal(raw)
    except InvalidOperation as exc:
        raise ValueError(f"{name}: decimal inválido") from exc
    if not dec.is_finite() or abs(dec.as_tuple().exponent) > 200:
        raise ValueError(f"{name}: fuera de límites decimales")
    return _bounded(Fraction(dec))


def _nonnegative(value, name):
    result = _number(value, name)
    if result < 0:
        raise ValueError(f"{name}: debe ser no negativo")
    return result


def _display(value: Fraction):
    with localcontext() as context:
        context.prec = 28
        approximate = str(Decimal(value.numerator) / Decimal(value.denominator))
    return {"exact": str(value), "decimal_approximation": approximate}


def _relative(value):
    raw = _text(value, "path", 240).replace("\\", "/")
    if raw.startswith("/") or ":" in raw or "\x00" in raw:
        raise ValueError("La ruta debe ser relativa, sin unidad ni flujos alternativos")
    parts = raw.split("/")
    for part in parts:
        if part in {"", ".", ".."} or part != part.rstrip(" ."):
            raise ValueError("Ruta con componente vacío, padre o terminación ambigua")
        if part.split(".", 1)[0].upper() in _DEVICES or any(c in part for c in '<>"|?*'):
            raise ValueError("Componente de ruta reservado o inválido")
        if any(ord(c) < 32 for c in part):
            raise ValueError("Caracteres de control en ruta")
    return "/".join(parts)


def _file(root: Path, relative: str):
    base = Path(root).absolute()
    path = base
    # Explicitly reject links/junctions in every supplied path component.
    for part in [None, *_relative(relative).split("/")]:
        if part is not None:
            path = path / part
        info = path.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError("No se permiten enlaces simbólicos ni puntos de reanálisis")
    if not path.is_file():
        raise ValueError("La fuente debe ser un archivo regular")
    resolved_base = base.resolve()
    if not path.resolve().is_relative_to(resolved_base):
        raise ValueError("La fuente escapa de la raíz del caso")
    with path.open("rb") as stream:
        data = stream.read(MAX_FILE_BYTES + 1)
    if len(data) > MAX_FILE_BYTES:
        raise ValueError(f"Fuente mayor que {MAX_FILE_BYTES} bytes")
    return data


def _utf8(data):
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("Fuente de texto no válida como UTF-8") from exc


def _unique_object(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError(f"Clave JSON repetida: {key}")
        out[key] = value
    return out


def _load_json(data):
    def invalid_constant(value):
        raise ValueError(f"Constante JSON no finita: {value}")
    return json.loads(_utf8(data), object_pairs_hook=_unique_object, parse_constant=invalid_constant)


def _expression(expression, variables):
    _text(expression, "expression", MAX_EXPR_LENGTH)
    try:
        tree = ast.parse(expression, mode="eval")
    except (SyntaxError, RecursionError) as exc:
        raise ValueError("Expresión aritmética inválida") from exc
    nodes = list(ast.walk(tree))
    if len(nodes) > MAX_AST_NODES:
        raise ValueError("Demasiados nodos aritméticos")
    allowed = (ast.Expression, ast.Constant, ast.Name, ast.Load, ast.BinOp, ast.UnaryOp,
               ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.UAdd, ast.USub)
    if any(not isinstance(node, allowed) for node in nodes):
        raise ValueError("Operación no admitida: solo números, variables y + - * / **")

    def visit(node, depth=0):
        if depth > 32:
            raise ValueError("Expresión demasiado anidada")
        if isinstance(node, ast.Expression):
            return visit(node.body, depth + 1)
        if isinstance(node, ast.Constant):
            if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
                raise ValueError("Constante no numérica")
            segment = ast.get_source_segment(expression, node)
            return _number(segment, "literal")
        if isinstance(node, ast.Name):
            if node.id not in variables:
                raise ValueError(f"Variable no declarada: {node.id}")
            return variables[node.id]
        if isinstance(node, ast.UnaryOp):
            item = visit(node.operand, depth + 1)
            return item if isinstance(node.op, ast.UAdd) else -item
        left, right = visit(node.left, depth + 1), visit(node.right, depth + 1)
        if isinstance(node.op, ast.Add):
            result = left + right
        elif isinstance(node.op, ast.Sub):
            result = left - right
        elif isinstance(node.op, ast.Mult):
            result = left * right
        elif isinstance(node.op, ast.Div):
            if right == 0:
                raise ValueError("División por cero")
            result = left / right
        else:
            if right.denominator != 1 or abs(right) > 12:
                raise ValueError("Exponente debe ser entero entre -12 y 12")
            if left == 0 and right <= 0:
                raise ValueError("Potencia de cero no definida para este exponente")
            # Bound estimated output before the allocation; then check actual size.
            if max(abs(left.numerator).bit_length(), left.denominator.bit_length()) * abs(int(right)) > MAX_RATIONAL_BITS:
                raise ValueError("Potencia excede el límite de tamaño")
            result = left ** int(right)
        return _bounded(result)
    return visit(tree)


def _evidence_spec(value):
    _keys(value, {"path", "quote", "locator"}, {"sha256"})
    _relative(value["path"])
    _text(value["quote"], "quote", 20_000)
    _text(value["locator"], "locator", 1024)
    if "sha256" in value and (not isinstance(value["sha256"], str) or not _HEX.fullmatch(value["sha256"])):
        raise ValueError("sha256 requiere 64 caracteres hexadecimales")


def validate(check):
    """Validate the adapter contract. Core owns all non-adapter check fields."""
    if not isinstance(check, dict) or not isinstance(check.get("method"), str) or check["method"] not in METHODS:
        raise ValueError("Adaptador desconocido")
    params = check.get("params")
    method = check["method"]
    if method == "arithmetic":
        _keys(params, {"expression", "expected"}, {"tolerance", "variables"})
        _number(params["expected"], "expected")
        _nonnegative(params.get("tolerance", 0), "tolerance")
        variables = params.get("variables", {})
        if not isinstance(variables, dict) or len(variables) > 32:
            raise ValueError("variables debe ser un objeto de hasta 32 elementos")
        if any(not isinstance(name, str) or not _NAME.fullmatch(name) for name in variables):
            raise ValueError("Nombre de variable inválido")
        _expression(params["expression"], {k: _number(v, k) for k, v in variables.items()})
    elif method == "numeric_interval":
        _keys(params, {"value", "error", "regions", "expected"})
        _number(params["value"], "value")
        _nonnegative(params["error"], "error")
        regions = params["regions"]
        if not isinstance(regions, list) or not 1 <= len(regions) <= 32:
            raise ValueError("regions debe contener entre 1 y 32 regiones")
        identifiers, ordered = set(), []
        for region in regions:
            _keys(region, {"id", "lower", "upper"})
            identifier = _text(region["id"], "region.id", 128)
            if identifier in identifiers:
                raise ValueError("Identificador de región repetido")
            identifiers.add(identifier)
            lower, upper = _number(region["lower"]), _number(region["upper"])
            if lower > upper:
                raise ValueError("Intervalo invertido")
            ordered.append((lower, upper))
        ordered.sort()
        if any(ordered[i][1] >= ordered[i + 1][0] for i in range(len(ordered) - 1)):
            raise ValueError("Regiones solapadas o con fronteras compartidas")
        expected = params["expected"]
        if expected is not None and (not isinstance(expected, str) or expected not in identifiers):
            raise ValueError("expected debe ser una región conocida o null")
    elif method == "csv_compare":
        _keys(params, {"path", "id_column", "truth_column", "baseline_column", "candidate_column", "min_absolute_improvement", "min_relative_improvement"}, {"metric"})
        _relative(params["path"])
        columns = [_text(params[key], key, 128) for key in ("id_column", "truth_column", "baseline_column", "candidate_column")]
        if len(set(columns)) != 4:
            raise ValueError("Las cuatro columnas deben ser distintas")
        absolute_min = _nonnegative(params["min_absolute_improvement"], "min_absolute_improvement")
        relative_min = _nonnegative(params["min_relative_improvement"], "min_relative_improvement")
        if relative_min > 1:
            raise ValueError("min_relative_improvement no puede superar 1 (100%)")
        if absolute_min == 0 and relative_min == 0:
            raise ValueError("Al menos un umbral de mejora debe ser positivo")
        if params.get("metric", "mae") != "mae":
            raise ValueError("Solo está implementada la métrica mae")
    elif method == "text_evidence":
        _evidence_spec(params)
    else:
        _keys(params, {"path", "evidence"})
        review_path = _relative(params["path"])
        if not isinstance(params["evidence"], list) or not 1 <= len(params["evidence"]) <= 32:
            raise ValueError("manual_review exige entre 1 y 32 respaldos documentales")
        for evidence in params["evidence"]:
            _evidence_spec(evidence)
            if _relative(evidence["path"]) == review_path:
                raise ValueError("La revisión no puede ser su propia fuente")


def source_paths(check):
    """List every consumed source, normalized and independent of filesystem state."""
    validate(check)
    params = check["params"]
    if check["method"] in {"arithmetic", "numeric_interval"}:
        return []
    paths = [_relative(params["path"])]
    if check["method"] == "manual_review":
        paths.extend(_relative(e["path"]) for e in params["evidence"])
    return list(dict.fromkeys(paths))


def _result(status, kind, summary, **details):
    return {"status": status, "kind": kind, "summary": summary, "details": details}


def _evidence(params, root):
    data = _file(root, params["path"])
    digest = hashlib.sha256(data).hexdigest()
    found = params["quote"] in _utf8(data)
    hash_matches = "sha256" not in params or digest == params["sha256"].lower()
    return {
        "path": _relative(params["path"]), "locator_declared": params["locator"],
        "quote_found": found, "sha256": digest, "expected_hash_matches": hash_matches,
        "passed": found and hash_matches,
    }


def execute(check, root):
    """Execute a closed, bounded adapter. Input/read errors raise exceptions.

    Core must record failures and charge budget even when an exception is raised.
    This function never mutates a file.
    """
    validate(check)
    params, method = check["params"], check["method"]
    root = Path(root)
    if method == "arithmetic":
        observed = _expression(params["expression"], {k: _number(v, k) for k, v in params.get("variables", {}).items()})
        expected = _number(params["expected"])
        tolerance = _nonnegative(params.get("tolerance", 0), "tolerance")
        difference = abs(observed - expected)
        passed = difference <= tolerance
        return _result("pass" if passed else "fail", "computed", "Comparación aritmética exacta satisfecha" if passed else "La expresión no satisface el valor esperado", observed=_display(observed), expected=_display(expected), absolute_difference=_display(difference), tolerance=_display(tolerance), limitation="Verifica la expresión suministrada, no su pertinencia científica.")
    if method == "numeric_interval":
        value, error = _number(params["value"]), _number(params["error"])
        lo, hi = value - error, value + error
        accepted = [r["id"] for r in params["regions"] if _number(r["lower"]) <= lo and hi <= _number(r["upper"])]
        actual = accepted[0] if len(accepted) == 1 else None
        passed = actual == params["expected"]
        return _result("pass" if passed else "fail", "computed", "Clasificación de intervalo coincide con el criterio" if passed else "Clasificación de intervalo distinta del criterio", observation_interval=[_display(lo), _display(hi)], accepted_region=actual, expected_region=params["expected"], limitation="El error acotado y la procedencia son entradas; no se estiman ni autentican.")
    if method == "text_evidence":
        outcome = _evidence(params, root)
        return _result("pass" if outcome["passed"] else "fail", "documentary", "Cita literal y huella declarada comprobadas" if outcome["passed"] else "La cita o la huella declarada no coincide", **outcome, limitation="No comprueba verdad, autoría, fecha, interpretación ni exactitud del localizador declarado.")
    if method == "csv_compare":
        data = _file(root, params["path"])
        reader = csv.DictReader(io.StringIO(_utf8(data), newline=""), strict=True)
        fieldnames = reader.fieldnames
        columns = [params[k] for k in ("id_column", "truth_column", "baseline_column", "candidate_column")]
        if not fieldnames or len(set(fieldnames)) != len(fieldnames) or any(c not in fieldnames for c in columns):
            raise ValueError("Cabecera CSV ausente, repetida o sin columnas requeridas")
        ids, baseline_sum, candidate_sum = set(), Fraction(0), Fraction(0)
        for row in reader:
            if len(ids) >= MAX_ROWS:
                raise ValueError(f"CSV supera {MAX_ROWS} filas")
            if None in row or any(v is None for v in row.values()):
                raise ValueError("Fila CSV irregular")
            identifier = _text(row[params["id_column"]], "id CSV", 128)
            if identifier != identifier.strip() or identifier in ids:
                raise ValueError("ID CSV repetido o con espacios laterales")
            ids.add(identifier)
            truth = _number(row[params["truth_column"]], "truth")
            baseline = _number(row[params["baseline_column"]], "baseline")
            candidate = _number(row[params["candidate_column"]], "candidate")
            baseline_sum = _bounded(baseline_sum + abs(baseline - truth))
            candidate_sum = _bounded(candidate_sum + abs(candidate - truth))
        if not ids:
            raise ValueError("CSV sin observaciones")
        baseline_mae, candidate_mae = baseline_sum / len(ids), candidate_sum / len(ids)
        absolute = baseline_mae - candidate_mae
        absolute_min = _number(params["min_absolute_improvement"])
        relative_min = _number(params["min_relative_improvement"])
        relative = absolute / baseline_mae if baseline_mae else None
        metrics = dict(count=len(ids), baseline_mae=_display(baseline_mae),
                       candidate_mae=_display(candidate_mae), absolute_improvement=_display(absolute),
                       relative_improvement=_display(relative) if relative is not None else None,
                       min_absolute_improvement=_display(absolute_min),
                       min_relative_improvement=_display(relative_min),
                       max_possible_absolute_improvement=_display(baseline_mae))
        if absolute_min > baseline_mae:
            return _result("inconclusive", "computed", "Umbral absoluto superior al máximo posible de mejora",
                           **metrics, design_status="threshold_above_comparator_ceiling",
                           limitation="En estas filas, ni un candidato con MAE cero alcanzaría el mínimo absoluto fijado; se conservan criterios y métricas.")
        if baseline_mae == 0:
            return _result("inconclusive", "computed", "Referencia sin error: no hay mejora relativa definida", **metrics,
                           design_status="relative_improvement_undefined", limitation="Techo del comparador; no se declara ventaja del candidato.")
        passed = absolute >= absolute_min and relative >= relative_min
        return _result("pass" if passed else "fail", "computed", "Mejora MAE alcanza ambos umbrales fijados" if passed else "Mejora MAE no alcanza ambos umbrales fijados", **metrics,
                       design_status="feasible_on_supplied_rows", limitation="Comparación descriptiva pareada sobre la cohorte suministrada; no prueba independencia, causalidad o significación estadística.")
    record = _load_json(_file(root, params["path"]))
    _keys(record, {"reviewer", "method", "verdict", "finding", "limitations", "evidence_paths"})
    for name in ("reviewer", "method", "finding"):
        _text(record[name], name, 8000)
    if not isinstance(record["verdict"], str) or record["verdict"] not in {"pass", "fail", "inconclusive"}:
        raise ValueError("Veredicto de revisión desconocido")
    if not isinstance(record["limitations"], list) or not 1 <= len(record["limitations"]) <= 32:
        raise ValueError("La revisión debe declarar límites")
    for item in record["limitations"]:
        _text(item, "limitación", 4000)
    paths = record["evidence_paths"]
    if not isinstance(paths, list) or not paths or len(paths) > 32:
        raise ValueError("La revisión debe identificar sus fuentes")
    declared_paths = [_relative(p) for p in paths]
    expected_paths = set(_relative(e["path"]) for e in params["evidence"])
    if len(set(declared_paths)) != len(declared_paths) or set(declared_paths) != expected_paths:
        raise ValueError("Las fuentes de la revisión no coinciden con el plan")
    evidence = [_evidence(spec, root) for spec in params["evidence"]]
    supported = all(item["passed"] for item in evidence)
    verdict = record["verdict"] if supported else "fail"
    return _result(verdict, "declared", "Revisión declarada registrada con respaldos documentales" if supported else "La revisión declarada contiene respaldos no localizados", reviewer_declared=record["reviewer"], method_declared=record["method"], finding_declared=record["finding"], verdict_declared=record["verdict"], evidence=evidence, limitations=record["limitations"], limitation="Verifica presencia y correspondencia del registro, no la identidad del revisor ni la corrección de su juicio.")
