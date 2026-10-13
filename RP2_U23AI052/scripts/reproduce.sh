#!/usr/bin/env bash
# Regenerate every table, figure, the report and the slides from a clean checkout.
#
#   export LLM_API_KEY=...            # key for the provider named in configs/config.yaml
#   bash scripts/reproduce.sh         # real run, tiers 1-3 (about 8,400 calls)
#   bash scripts/reproduce.sh mock    # offline pipeline test, NOT a result
#
# Edit model.provider / model.name / model.base_url in configs/config.yaml first.
set -euo pipefail
cd "$(dirname "$0")/.."

MODE="${1:-real}"
python -m pytest -q tests

if [ "$MODE" = "mock" ]; then
  python scripts/run_experiment.py --provider mock --tiers 1 2 3 --workers 8 --rps 0
  RUN=results/mock_smoke
else
  python scripts/run_experiment.py --tiers 1 2 3
  # newest real run directory
  RUN=$(ls -dt results/*/ | grep -v -E 'mock_smoke|demo' | head -1)
fi

python scripts/aggregate.py --run-dir "$RUN"
python scripts/make_report.py --run-dir "$RUN" --out "report/RP2_report$([ "$MODE" = mock ] && echo _MOCK_PREVIEW).pdf"
python scripts/make_slides.py --run-dir "$RUN" --out "slides/RP2_slides$([ "$MODE" = mock ] && echo _MOCK_PREVIEW).pptx"
echo "done: $RUN"
