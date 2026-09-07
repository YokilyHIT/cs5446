# Preliminary Experiment Results

## Environment
- AdaMEM commit: 4ea93e239f8dbec2fa6013a28bc8555419037e12
- ALFWorld version: (not installed / see requirements_lock.txt)
- Qwen model: Qwen/Qwen3-4B-Instruct-2507
- GPU: npu-smi 25.5.1                   Version: 25.5.1
- seeds: [13, 37, 73]

# Experiment A

## Data
- train episodes: 50
- failures: 20
- evaluated failures: 20
- evaluation episodes: 360 pairwise + 360 topk-vs-all

## Main numbers
- P(delta < 0): 0.600
- P(delta = 0): 0.250
- P(delta > 0): 0.150
- Var(delta): 0.034
- Spearman U vs delta: -0.196 [-0.600, 0.218]
- luck-baseline p-value for P(delta<=0) (chance-level heterogeneity check, n_sim=1000): 0.015
- NoMemory SR: 0.344 [0.244, 0.433]
- AllLessons SR: 0.333 [0.233, 0.433]
- RandomK SR: 0.233 [0.144, 0.322]
- TopK SR: 0.300 [0.211, 0.400]

## Decision
WEAK-GO

## Interpretation
Result pattern does not cleanly match the GO or NO-GO thresholds; weakly supported is the closest fit given P(delta<=0)=0.85, rho_U=-0.20, SR_TopK-SR_All=-0.03 (luck-baseline p=0.01 < 0.1, i.e. distinguishable from pure chance).

# Experiment B

## Data
- decision points: 148
- changed-action points: 54
- calibration points: 50
- evaluation points: 98

## Main numbers
- mismatch rate: 0.086
- rho(self-confidence, planning gain): -0.108 [-0.313, 0.074]
- rho(semantic-correctness, planning gain): -0.403 [-0.618, -0.120]
- oracle upper-bound gain: 0.031 [0.000, 0.071]
- helpful foresight rate: 0.086
- harmful foresight rate: 0.086

## Decision
WEAK-GO

## Interpretation
Only 1/3 go/no-go criteria hold (mismatch_rate=0.086, oracle_gain=0.031, rho_self=-0.108); weakly supported by preliminary evidence and any follow-up should proceed cautiously.

# Recommendation
neither (neither direction cleared its preliminary go/no-go bar under the current setup)
