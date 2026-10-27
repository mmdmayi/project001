"""External Python only: weighted bounded linear inverse with temporal prior."""
import argparse
import json
import time
import numpy as np
from scipy.optimize import lsq_linear


def solve(calibration, targets, weights=None, ridge=1e-8, temporal=0.0):
    a = np.asarray(calibration['matrix'], dtype=float)
    neutral = np.asarray(calibration['neutral'], dtype=float)
    controls = calibration['controls']
    c0 = np.asarray([c['neutral'] for c in controls])
    lo = np.asarray([c['min'] for c in controls]) - c0
    hi = np.asarray([c['max'] for c in controls]) - c0
    y = np.asarray(targets['features'], dtype=float)
    if a.ndim != 2 or a.shape != (neutral.size, len(controls)):
        raise ValueError('Invalid response matrix dimensions')
    if y.ndim != 2 or y.shape[1] != neutral.size or len(targets['frames']) != len(y):
        raise ValueError('Target dimensions / frame count mismatch')
    if not len(y) or np.any(np.diff(targets['frames']) <= 0):
        raise ValueError('Frames must be nonempty and strictly increasing')
    if ridge < 0 or temporal < 0 or np.any(lo >= hi):
        raise ValueError('Invalid regularization or bounds')
    w = np.ones(neutral.size) if weights is None else np.asarray(weights, dtype=float)
    if w.shape != neutral.shape or np.any(w < 0):
        raise ValueError('Weights must be nonnegative feature weights')
    if not all(np.all(np.isfinite(v)) for v in (a, neutral, y, w, lo, hi, c0)):
        raise ValueError('Nonfinite data')
    scales = hi - lo
    # Solve in normalized controller units to avoid bias toward large-range channels.
    design = a * scales[None, :]
    eye = np.eye(len(controls))
    mat = np.vstack((design * np.sqrt(w)[:, None], np.sqrt(ridge)*eye,
                     np.sqrt(temporal)*eye))
    previous = np.zeros(len(controls))
    values, errors, statuses = [], [], []
    started = time.perf_counter()
    for row in y:
        rhs = np.concatenate(((row-neutral)*np.sqrt(w), np.zeros(len(controls)),
                              np.sqrt(temporal)*previous))
        result = lsq_linear(mat, rhs, bounds=(lo/scales, hi/scales), tol=1e-10)
        if not result.success:
            raise RuntimeError('Bounded solve failed: '+result.message)
        previous = result.x
        delta = result.x * scales
        values.append((c0+delta).tolist())
        errors.append(float(np.sqrt(np.mean((a@delta+neutral-row)**2))))
        statuses.append(int(result.status))
    return dict(schema=1, plugs=[c['plug'] for c in controls], frames=targets['frames'],
                values=values, feature_rmse=errors, statuses=statuses,
                seconds=time.perf_counter()-started,
                rank=int(np.linalg.matrix_rank(design)), channels=len(controls))


def main():
    p = argparse.ArgumentParser()
    p.add_argument('calibration'); p.add_argument('targets'); p.add_argument('output')
    p.add_argument('--temporal', type=float, default=0.0)
    args = p.parse_args()
    with open(args.calibration, encoding='utf8') as f: cal = json.load(f)
    with open(args.targets, encoding='utf8') as f: targets = json.load(f)
    result = solve(cal, targets, temporal=args.temporal)
    with open(args.output, 'w', encoding='utf8') as f: json.dump(result, f, indent=2, allow_nan=False)


if __name__ == '__main__':
    main()
