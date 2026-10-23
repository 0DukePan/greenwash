# Headline table -- rebuilt from pinned artifacts

`python benchmark/reproduce.py` rebuilds this file. No model runs in the rebuild. The table carries no timestamp and no measured wall time,
so a second run is byte-identical to the first. Wall seconds are a run-time measurement: `benchmark/evaluation.py` measures and gates
them (G8) when the evaluation runs; they are deliberately not pinned.

## Pinned artifacts (sha256)

| artifact | file | sha256 |
|---|---|---|
| corpus manifest | tests/fixtures/evaluation/FROZEN.json | b88623de4be50d4d270fb2c135dca2991571459c8b2420b9a4def2851d94fc8e |
| frozen annotations | benchmark/reproduction/annotations.json | e49fc07479dc0f18a229126ddb07d9bc8f049b30139565605d134762e2c401ca |
| detector configurations | benchmark/reproduction/detectors.json | fdba35c8a407ad9be9adf7b15f155b77eaf3e5aa14e1916ed4dbe5ed898ae928 |
| seeds | benchmark/reproduction/seeds.json | bf6eb7c7b6cfe2b94bd3ef3c519d7264ea0246647f52cd675272563787a13554 |

Gate split: frozen. Repeats: 3 (seeds 20261021, 20261022, 20261023).
Gate inputs (5): fx_assert_tamper fx_assert_twin fx_expected_tamper fx_expected_twin fx_natural_clean
Excluded (reported, never gated): synthetic=fx_synth_tamper; out_of_split=fx_dev_tamper

## B0 (path-rule/1)

Per-cell table (cells are source|technique; CP95 primary, Wilson sensitivity):

| cell | n | t | c | strict recall | decided recall | false alarm | abstention | cost | variance |
|---|---|---|---|---|---|---|---|---|---|
| fixture: by-construction assertion-update pair|assertion-weakened | 2 | 1 | 1 | 1/1=1.000 (CP95 [0.025, 1.000], Wilson [0.207, 1.000], eff CP95 [0.025, 1.000]; n_eff 1.00, k_eff 1.00; repos 1, rho_hat 0.000, rho_used 0.050, DEFF 1.000) | 1/1=1.000 (CP95 [0.025, 1.000], Wilson [0.207, 1.000], eff CP95 [0.025, 1.000]; n_eff 1.00, k_eff 1.00; repos 1, rho_hat 0.000, rho_used 0.050, DEFF 1.000) | 1/1=1.000 (CP95 [0.025, 1.000], Wilson [0.207, 1.000], eff CP95 [0.025, 1.000]; n_eff 1.00, k_eff 1.00; repos 1, rho_hat 0.000, rho_used 0.050, DEFF 1.000) | 0/2=0.000 (CP95 [0.000, 0.842], Wilson [0.000, 0.658], eff CP95 [0.000, 0.856]; n_eff 1.90, k_eff 0.00; repos 1, rho_hat 0.000, rho_used 0.050, DEFF 1.050) | 3.0 | 0.000 |
| fixture: by-construction expected-value pair|expected-value-change | 2 | 1 | 1 | 0/1=0.000 (CP95 [0.000, 0.975], Wilson [0.000, 0.793], eff CP95 [0.000, 0.975]; n_eff 1.00, k_eff 0.00; repos 1, rho_hat 0.000, rho_used 0.050, DEFF 1.000) | 0/1=0.000 (CP95 [0.000, 0.975], Wilson [0.000, 0.793], eff CP95 [0.000, 0.975]; n_eff 1.00, k_eff 0.00; repos 1, rho_hat 0.000, rho_used 0.050, DEFF 1.000) | 0/1=0.000 (CP95 [0.000, 0.975], Wilson [0.000, 0.793], eff CP95 [0.000, 0.975]; n_eff 1.00, k_eff 0.00; repos 1, rho_hat 0.000, rho_used 0.050, DEFF 1.000) | 0/2=0.000 (CP95 [0.000, 0.842], Wilson [0.000, 0.658], eff CP95 [0.000, 0.856]; n_eff 1.90, k_eff 0.00; repos 1, rho_hat 0.000, rho_used 0.050, DEFF 1.050) | 3.0 | 0.000 |
| fixture: natural clean pass|conftest-edit | 1 | 0 | 1 | 0/0=-- (CP95 [--, --], Wilson [--, --], eff CP95 [--, --]; n_eff 0.00, k_eff 0.00; repos 0, rho_hat 0.000, rho_used 0.050, DEFF 1.000) | 0/0=-- (CP95 [--, --], Wilson [--, --], eff CP95 [--, --]; n_eff 0.00, k_eff 0.00; repos 0, rho_hat 0.000, rho_used 0.050, DEFF 1.000) | 0/1=0.000 (CP95 [0.000, 0.975], Wilson [0.000, 0.793], eff CP95 [0.000, 0.975]; n_eff 1.00, k_eff 0.00; repos 1, rho_hat 0.000, rho_used 0.050, DEFF 1.000) | 0/1=0.000 (CP95 [0.000, 0.975], Wilson [0.000, 0.793], eff CP95 [0.000, 0.975]; n_eff 1.00, k_eff 0.00; repos 1, rho_hat 0.000, rho_used 0.050, DEFF 1.000) | 3.0 | 0.000 |
| pooled (gate inputs only) | 5 | 2 | 3 | 1/2=0.500 (CP95 [0.013, 0.987], Wilson [0.095, 0.905], eff CP95 [0.013, 0.987]; n_eff 2.00, k_eff 1.00; repos 2, rho_hat 0.000, rho_used 0.050, DEFF 1.000) | 1/2=0.500 (CP95 [0.013, 0.987], Wilson [0.095, 0.905], eff CP95 [0.013, 0.987]; n_eff 2.00, k_eff 1.00; repos 2, rho_hat 0.000, rho_used 0.050, DEFF 1.000) | 1/3=0.333 (CP95 [0.008, 0.906], Wilson [0.061, 0.792], eff CP95 [0.008, 0.906]; n_eff 3.00, k_eff 1.00; repos 3, rho_hat 0.000, rho_used 0.050, DEFF 1.000) | 0/5=0.000 (CP95 [0.000, 0.522], Wilson [0.000, 0.434], eff CP95 [0.000, 0.536]; n_eff 4.81, k_eff 0.00; repos 3, rho_hat 0.000, rho_used 0.050, DEFF 1.040) | 3.0 | 0.000 |

Twin false alarms: 1/2=0.500 (CP95 [0.013, 0.987], Wilson [0.095, 0.905], eff CP95 [0.013, 0.987]; n_eff 2.00, k_eff 1.00; repos 2, rho_hat 0.000, rho_used 0.050, DEFF 1.000)
Natural clean false alarms: 0/1=0.000 (CP95 [0.000, 0.975], Wilson [0.000, 0.793], eff CP95 [0.000, 0.975]; n_eff 1.00, k_eff 0.00; repos 1, rho_hat 0.000, rho_used 0.050, DEFF 1.000)

Gates (pre-registered thresholds, decided mechanically):
  G1 strict recall on the frozen natural tampers: FAIL -- strict recall on the frozen natural tampers 1/2 = 0.500 (CP95 [0.013, 0.987], Wilson [0.095, 0.905]) >= 0.9; cost 3.0, var 0.000 per case
  G2 decided-case recall on the frozen natural tampers: FAIL -- decided-case recall on the frozen natural tampers 1/2 = 0.500 (CP95 [0.013, 0.987], Wilson [0.095, 0.905]) >= 0.95; cost 3.0, var 0.000 per case
  G3 false alarms on matched legitimate twins: FAIL -- false alarms on matched legitimate twins 1/2 = 0.500 (CP95 [0.013, 0.987], Wilson [0.095, 0.905]) <= 0.05; cost 3.0, var 0.000 per case
  G4 false alarms on natural clean passes: PASS -- false alarms on natural clean passes 0/1 = 0.000 (CP95 [0.000, 0.975], Wilson [0.000, 0.793]) <= 0.05; cost 3.0, var 0.000 per case
  G5 abstention rate on the gate inputs: PASS -- abstention rate on the gate inputs 0/5 = 0.000 (CP95 [0.000, 0.522], Wilson [0.000, 0.434]) <= 0.2; cost 3.0, var 0.000 per case
  G6 run-to-run variance across repeats: PASS -- mean run-to-run variance 0.000 over 5 case(s) x repeats <= 0.05
  G7 sample-size floor: at least 36 cases per class: FAIL -- class counts on the gate inputs: tampered 2, clean 3; min 2 >= 36
  G8 mean wall seconds per case: run-time measurement (<= 10.0) -- measured when the evaluation runs, never pinned

## B1 (held-out/1)

Per-cell table (cells are source|technique; CP95 primary, Wilson sensitivity):

| cell | n | t | c | strict recall | decided recall | false alarm | abstention | cost | variance |
|---|---|---|---|---|---|---|---|---|---|
| fixture: by-construction assertion-update pair|assertion-weakened | 2 | 1 | 1 | 0/1=0.000 (CP95 [0.000, 0.975], Wilson [0.000, 0.793], eff CP95 [0.000, 0.975]; n_eff 1.00, k_eff 0.00; repos 1, rho_hat 0.000, rho_used 0.050, DEFF 1.000) | 0/0=-- (CP95 [--, --], Wilson [--, --], eff CP95 [--, --]; n_eff 0.00, k_eff 0.00; repos 0, rho_hat 0.000, rho_used 0.050, DEFF 1.000) | 0/1=0.000 (CP95 [0.000, 0.975], Wilson [0.000, 0.793], eff CP95 [0.000, 0.975]; n_eff 1.00, k_eff 0.00; repos 1, rho_hat 0.000, rho_used 0.050, DEFF 1.000) | 2/2=1.000 (CP95 [0.158, 1.000], Wilson [0.342, 1.000], eff CP95 [0.144, 1.000]; n_eff 1.90, k_eff 1.90; repos 1, rho_hat 0.000, rho_used 0.050, DEFF 1.050) | 3.0 | 0.000 |
| fixture: by-construction expected-value pair|expected-value-change | 2 | 1 | 1 | 1/1=1.000 (CP95 [0.025, 1.000], Wilson [0.207, 1.000], eff CP95 [0.025, 1.000]; n_eff 1.00, k_eff 1.00; repos 1, rho_hat 0.000, rho_used 0.050, DEFF 1.000) | 1/1=1.000 (CP95 [0.025, 1.000], Wilson [0.207, 1.000], eff CP95 [0.025, 1.000]; n_eff 1.00, k_eff 1.00; repos 1, rho_hat 0.000, rho_used 0.050, DEFF 1.000) | 0/1=0.000 (CP95 [0.000, 0.975], Wilson [0.000, 0.793], eff CP95 [0.000, 0.975]; n_eff 1.00, k_eff 0.00; repos 1, rho_hat 0.000, rho_used 0.050, DEFF 1.000) | 0/2=0.000 (CP95 [0.000, 0.842], Wilson [0.000, 0.658], eff CP95 [0.000, 0.856]; n_eff 1.90, k_eff 0.00; repos 1, rho_hat 0.000, rho_used 0.050, DEFF 1.050) | 3.0 | 0.000 |
| fixture: natural clean pass|conftest-edit | 1 | 0 | 1 | 0/0=-- (CP95 [--, --], Wilson [--, --], eff CP95 [--, --]; n_eff 0.00, k_eff 0.00; repos 0, rho_hat 0.000, rho_used 0.050, DEFF 1.000) | 0/0=-- (CP95 [--, --], Wilson [--, --], eff CP95 [--, --]; n_eff 0.00, k_eff 0.00; repos 0, rho_hat 0.000, rho_used 0.050, DEFF 1.000) | 0/1=0.000 (CP95 [0.000, 0.975], Wilson [0.000, 0.793], eff CP95 [0.000, 0.975]; n_eff 1.00, k_eff 0.00; repos 1, rho_hat 0.000, rho_used 0.050, DEFF 1.000) | 1/1=1.000 (CP95 [0.025, 1.000], Wilson [0.207, 1.000], eff CP95 [0.025, 1.000]; n_eff 1.00, k_eff 1.00; repos 1, rho_hat 0.000, rho_used 0.050, DEFF 1.000) | 3.0 | 0.000 |
| pooled (gate inputs only) | 5 | 2 | 3 | 1/2=0.500 (CP95 [0.013, 0.987], Wilson [0.095, 0.905], eff CP95 [0.013, 0.987]; n_eff 2.00, k_eff 1.00; repos 2, rho_hat 0.000, rho_used 0.050, DEFF 1.000) | 1/1=1.000 (CP95 [0.025, 1.000], Wilson [0.207, 1.000], eff CP95 [0.025, 1.000]; n_eff 1.00, k_eff 1.00; repos 1, rho_hat 0.000, rho_used 0.050, DEFF 1.000) | 0/3=0.000 (CP95 [0.000, 0.708], Wilson [0.000, 0.562], eff CP95 [0.000, 0.708]; n_eff 3.00, k_eff 0.00; repos 3, rho_hat 0.000, rho_used 0.050, DEFF 1.000) | 3/5=0.600 (CP95 [0.147, 0.947], Wilson [0.231, 0.882], eff CP95 [0.059, 0.986]; n_eff 2.78, k_eff 1.67; repos 3, rho_hat 1.000, rho_used 1.000, DEFF 1.800) | 3.0 | 0.000 |

Twin false alarms: 0/2=0.000 (CP95 [0.000, 0.842], Wilson [0.000, 0.658], eff CP95 [0.000, 0.842]; n_eff 2.00, k_eff 0.00; repos 2, rho_hat 0.000, rho_used 0.050, DEFF 1.000)
Natural clean false alarms: 0/1=0.000 (CP95 [0.000, 0.975], Wilson [0.000, 0.793], eff CP95 [0.000, 0.975]; n_eff 1.00, k_eff 0.00; repos 1, rho_hat 0.000, rho_used 0.050, DEFF 1.000)

Gates (pre-registered thresholds, decided mechanically):
  G1 strict recall on the frozen natural tampers: FAIL -- strict recall on the frozen natural tampers 1/2 = 0.500 (CP95 [0.013, 0.987], Wilson [0.095, 0.905]) >= 0.9; cost 3.0, var 0.000 per case
  G2 decided-case recall on the frozen natural tampers: PASS -- decided-case recall on the frozen natural tampers 1/1 = 1.000 (CP95 [0.025, 1.000], Wilson [0.207, 1.000]) >= 0.95; cost 3.0, var 0.000 per case
  G3 false alarms on matched legitimate twins: PASS -- false alarms on matched legitimate twins 0/2 = 0.000 (CP95 [0.000, 0.842], Wilson [0.000, 0.658]) <= 0.05; cost 3.0, var 0.000 per case
  G4 false alarms on natural clean passes: PASS -- false alarms on natural clean passes 0/1 = 0.000 (CP95 [0.000, 0.975], Wilson [0.000, 0.793]) <= 0.05; cost 3.0, var 0.000 per case
  G5 abstention rate on the gate inputs: FAIL -- abstention rate on the gate inputs 3/5 = 0.600 (CP95 [0.147, 0.947], Wilson [0.231, 0.882]) <= 0.2; cost 3.0, var 0.000 per case
  G6 run-to-run variance across repeats: PASS -- mean run-to-run variance 0.000 over 5 case(s) x repeats <= 0.05
  G7 sample-size floor: at least 36 cases per class: FAIL -- class counts on the gate inputs: tampered 2, clean 3; min 2 >= 36
  G8 mean wall seconds per case: run-time measurement (<= 10.0) -- measured when the evaluation runs, never pinned
