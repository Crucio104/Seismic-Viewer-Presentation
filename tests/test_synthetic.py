"""
test_synthetic.py - Unit and regression tests validating synthetic plane extraction and algorithms.
"""

import os
import sys
import unittest
import numpy as np

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from tests.benchmark_synthetic import generate_synthetic_fault_plane
from core.engine.analysis import fit_plane_ransac, get_strike_dip
from core.loader import pack_seismic_binary


class TestSyntheticBenchmarks(unittest.TestCase):

    def test_strike_dip_conversion(self):
        """Verify normal vector inversion to strike and dip."""
        test_cases = [
            (0.0, 45.0),
            (90.0, 30.0),
            (180.0, 60.0),
            (270.0, 75.0),
            (315.0, 15.0),
        ]
        for strike_true, dip_true in test_cases:
            dip_dir = (strike_true + 90.0) % 360.0
            dip_rad = np.radians(dip_true)
            dd_rad = np.radians(dip_dir)
            normal = np.array([
                np.sin(dip_rad) * np.sin(dd_rad),
                np.sin(dip_rad) * np.cos(dd_rad),
                np.cos(dip_rad)
            ])
            s_est, d_est, _ = get_strike_dip(normal)
            self.assertAlmostEqual(d_est, dip_true, places=4)
            strike_diff = abs(s_est - strike_true) % 360.0
            if strike_diff > 180.0:
                strike_diff = 360.0 - strike_diff
            self.assertAlmostEqual(strike_diff, 0.0, places=4)

    def test_clean_plane_fitting(self):
        """Verify RANSAC + SVD with near-zero noise achieves near-zero error."""
        rng = np.random.default_rng(123)
        points, true_normal = generate_synthetic_fault_plane(
            n_points=500,
            strike_deg=45.0,
            dip_deg=60.0,
            noise_m=1.0,
            outlier_ratio=0.0,
            rng=rng,
            patch_size_km=2.0
        )
        normal, centroid, planarity = fit_plane_ransac(points, threshold=0.01)
        self.assertIsNotNone(normal)
        self.assertGreater(planarity, 0.95)

        s_est, d_est, _ = get_strike_dip(normal)
        self.assertAlmostEqual(d_est, 60.0, delta=0.1)
        s_diff = abs(s_est - 45.0) % 360.0
        if s_diff > 180.0:
            s_diff = 360.0 - s_diff
        self.assertAlmostEqual(s_diff, 0.0, delta=0.2)

    def test_noisy_plane_fitting_within_thesis_bounds(self):
        """Verify 50m noise and 20% outliers remains within thesis geophysical bound (< 1.0 deg error)."""
        rng = np.random.default_rng(42)
        dip_errs = []
        strike_errs = []
        for _ in range(20):
            strike = float(rng.uniform(0.0, 360.0))
            dip = float(rng.uniform(10.0, 80.0))
            pts, _ = generate_synthetic_fault_plane(
                n_points=1000,
                strike_deg=strike,
                dip_deg=dip,
                noise_m=50.0,
                outlier_ratio=0.20,
                rng=rng
            )
            normal, _, planarity = fit_plane_ransac(pts, threshold=0.10)
            self.assertIsNotNone(normal)
            self.assertGreater(planarity, 0.80)
            s_est, d_est, _ = get_strike_dip(normal)
            dip_errs.append(abs(d_est - dip))
            s_diff = abs(s_est - strike) % 360.0
            if s_diff > 180.0:
                s_diff = 360.0 - s_diff
            strike_errs.append(s_diff)

        self.assertLess(np.mean(dip_errs), 0.5)
        self.assertLess(np.mean(strike_errs), 0.8)

    def test_binary_serialization_packing(self):
        """Verify Float32 binary buffer pack length and payload validity."""
        n = 1000
        data = {
            'lon': np.linspace(14.0, 14.2, n, dtype=np.float32),
            'lat': np.linspace(40.8, 40.9, n, dtype=np.float32),
            'dep': np.linspace(1.0, 5.0, n, dtype=np.float32),
            'mag': np.ones(n, dtype=np.float32),
            'dates_num': np.arange(n, dtype=np.float32)
        }
        buf = pack_seismic_binary(data)
        # Header (2 f32 = 8 bytes) + 5 arrays * 1000 f32 * 4 bytes = 8 + 20000 = 20008 bytes
        self.assertEqual(len(buf), 20008)


if __name__ == "__main__":
    unittest.main()
