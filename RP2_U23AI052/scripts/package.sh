#!/usr/bin/env bash
# Build the submission zip RP2_U23AI052.zip (report, slides, code, traces).
#   bash scripts/package.sh
# Refuses to build the final zip while only the mock run exists; in that case it writes
# RP2_U23AI052_PENDING.zip (code + setup) so you can see what is missing.
set -euo pipefail
cd "$(dirname "$0")/.."
ROLL=U23AI052
RUN=$(ls -dt results/*/ 2>/dev/null | grep -v -E 'mock_smoke|demo' | head -1 || true)
STAGE=$(mktemp -d)/RP2_${ROLL}
mkdir -p "$STAGE"

cp -r README.md TALK_AND_VIVA.md requirements.txt .env.example .gitignore configs prompts data rp2 scripts tests "$STAGE"/
mkdir -p "$STAGE/report" "$STAGE/slides" "$STAGE/results"

if [ -z "$RUN" ]; then
  OUT="RP2_${ROLL}_PENDING.zip"
  cp report/RP2_report.pdf "$STAGE/report/" ; cp slides/RP2_slides.pptx "$STAGE/slides/"
  echo "No real run found: building $OUT (NOT submittable)."
else
  OUT="RP2_${ROLL}.zip"
  if grep -q '"mock_run": true' "${RUN}manifest.json"; then echo "latest run is a mock run, refusing"; exit 1; fi
  for f in report/RP2_report.pdf slides/RP2_slides.pptx; do
    [ -f "$f" ] || { echo "missing $f"; exit 1; }
  done
  # the report and slides must have been built from this run
  python scripts/make_report.py --run-dir "$RUN" --out "$STAGE/report/RP2_report.pdf"
  python scripts/make_slides.py --run-dir "$RUN" --out "$STAGE/slides/RP2_slides.pptx"
  cp -r "$RUN" "$STAGE/results/"
fi
find "$STAGE" -name __pycache__ -prune -exec rm -rf {} + ; rm -rf "$STAGE/.pytest_cache"
( cd "$(dirname "$STAGE")" && zip -qr "$OLDPWD/$OUT" "RP2_${ROLL}" )
echo "wrote $OUT ($(du -h "$OUT" | cut -f1))"
