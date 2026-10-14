| Condition | Tool acc % | Param acc % (given tool) | AST acc % | In tok/task | Out tok/task | Calls/task | Latency s/task | Tok per correct |
|---|---|---|---|---|---|---|---|---|
| 5 tools | 26.6 | 91.2 | 24.2 | 505 | 8 | 1.00 | 13.83 | 2115 |
| 20 tools | 26.8 | 97.1 | 26.0 | 1228 | 8 | 1.00 | 13.96 | 4757 |
| 50 tools | 26.8 | 100.0 | 26.8 | 2707 | 8 | 1.00 | 14.11 | 10143 |
| 50, gold first | 28.3 | 100.0 | 28.3 | 2855 | 8 | 1.00 | 14.08 | 10103 |
| 50, gold last | 27.6 | 100.0 | 27.6 | 2761 | 8 | 1.00 | 13.94 | 10049 |
| 5 tools + padding | 26.8 | 97.1 | 26.0 | 1990 | 8 | 1.00 | 13.95 | 7690 |
| 5 tools, self-consistency | 37.8 | 91.7 | 34.6 | 4039 | 62 | 8.00 | 112.15 | 11838 |

Mean ± SD over 1 runs of the 128-task subset.

| Paired comparison (task level) | metric | mean diff (pp) | 95% bootstrap CI (pp) | CI excludes 0 |
|---|---|---|---|---|
| c05->c20 | tool_ok | +0.0 | [-5.5, +5.5] | no |
| c05->c20 | ast_ok | +1.6 | [-4.7, +7.9] | no |
| c20->c50 | tool_ok | +0.0 | [-3.9, +4.7] | no |
| c20->c50 | ast_ok | +0.8 | [-3.9, +5.5] | no |
| c05->c50 | tool_ok | +0.0 | [-7.1, +7.1] | no |
| c05->c50 | ast_ok | +2.4 | [-4.7, +10.2] | no |
| c50->c50_goldfirst | tool_ok | +1.6 | [-3.9, +7.1] | no |
| c50->c50_goldfirst | ast_ok | +1.6 | [-3.9, +7.1] | no |
| c50->c50_goldlast | tool_ok | +0.8 | [-5.5, +7.1] | no |
| c50->c50_goldlast | ast_ok | +0.8 | [-5.5, +7.1] | no |
| c05->c05_padded | tool_ok | +0.0 | [-8.7, +7.9] | no |
| c05->c05_padded | ast_ok | +1.6 | [-6.3, +9.4] | no |
| c05_sc->c50 | tool_ok | -11.0 | [-16.5, -6.3] | yes |
| c05_sc->c50 | ast_ok | -7.9 | [-14.2, -1.6] | yes |
| c05->c05_sc | tool_ok | +11.0 | [+6.3, +16.5] | yes |
| c05->c05_sc | ast_ok | +10.2 | [+4.7, +16.5] | yes |

| Condition | failed attempts | api error | no tool call | invalid tool name | malformed arguments | wrong tool same domain | wrong tool cross domain | missing required param | schema violation | wrong param value |
|---|---|---|---|---|---|---|---|---|---|---|
| 5 tools | 97/128 | 93 | 0 | 1 | 0 | 0 | 0 | 3 | 0 | 0 |
| 20 tools | 94/127 | 92 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 |
| 50 tools | 93/127 | 92 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 |
| 50, gold first | 91/127 | 90 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| 50, gold last | 92/127 | 91 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 |
| 5 tools + padding | 94/127 | 93 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 |
| 5 tools, self-consistency | 83/127 | 79 | 0 | 0 | 0 | 0 | 0 | 4 | 0 | 0 |

| Gold-tool position | 0-16 | 17-33 | 34-49 |
|---|---|---|---|
| 50 tools | 30.0% (n=40) | 28.1% (n=57) | 20.0% (n=30) |
| 50, gold first | 28.3% (n=127) | n/a | n/a |
| 50, gold last | n/a | n/a | 27.6% (n=127) |
