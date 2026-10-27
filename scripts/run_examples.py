"""Run six known development examples into a new local directory.

The reviewed example uses a labelled synthetic review fixture, not a real
independent reviewer. Never use this fixture to approve research cases.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pse import engine  # noqa: E402

EXPECTED = {"calculo": "CLOSED_RESULTS", "datos": "CLOSED_RESULTS",
            "datos_sin_mejora": "CLOSED_UNRESOLVED", "documentos": "CLOSED_RESULTS",
            "techo": "CLOSED_RESULTS", "revision_declarada": "CLOSED_REVIEWED_DECLARED"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path, help="New output directory; never overwritten")
    args = parser.parse_args(argv)
    out = args.out.resolve()
    if out.exists():
        parser.error("The output directory already exists; choose a new one")
    out.mkdir(parents=True, exist_ok=False)
    summaries = []
    for name, expected in EXPECTED.items():
        source = ROOT / "examples" / name
        case = out / name
        engine.init_case(source / "plan.json", case)
        engine.run_case(case)
        decision = json.loads((source / "decision.json").read_text(encoding="utf-8"))
        if name == "revision_declarada":
            proposal = engine.propose_case(case, json.loads((source / "draft.json").read_text(encoding="utf-8")))
            packet = engine.review_packet(case, proposal["proposal_id"])
            (case / "PAQUETE_REVISION_EJEMPLO.json").write_text(json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            # Fixture completion is confined to this known synthetic example.
            review = json.loads((source / "review.template.json").read_text(encoding="utf-8"))
            review["proposal_id"] = proposal["proposal_id"]
            review["proposal_sha256"] = proposal["proposal_sha256"]
            (case / "REVISION_SINTETICA_EJEMPLO.json").write_text(json.dumps(review, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            engine.review_case(case, review)
            decision["proposal_id"] = proposal["proposal_id"]
        engine.close_case(case, decision)
        verification = engine.verify_case(case)
        state = engine.status(case)
        if state["state"] != expected or not verification["verified"]:
            raise AssertionError(f"Unexpected development example result: {name}")
        (case / "INFORME.md").write_text(engine.render_report(case), encoding="utf-8")
        summaries.append({"case": name, "mode": decision["mode"], "expected_state": expected,
                          "state": state, "verification": verification})
    result = {"scope": "Known synthetic development examples; no independent efficacy evaluation. The review fixture is not an authenticated reviewer.",
              "examples": summaries}
    (out / "RESULTADOS_EJEMPLOS.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # Keep terminal output short; the complete record remains in the JSON file.
    print(json.dumps({"output": str(out), "examples": [
        {"case": item["case"], "state": item["state"]["state"],
         "verified": item["verification"]["verified"]}
        for item in summaries]}, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
