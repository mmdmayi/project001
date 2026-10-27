import unittest
import numpy as np
from faceinverse.solver import solve


class SolverTests(unittest.TestCase):
    def setUp(self):
        self.cal=dict(matrix=[[1,0],[0,2],[1,1]],neutral=[0,0,0],controls=[
            dict(plug='a.x',min=-1,max=1,neutral=0),dict(plug='b.y',min=0,max=1,neutral=0)])

    def test_exact_roundtrip(self):
        r=solve(self.cal,dict(frames=[1],features=[[0.2,1.4,0.9]]))
        np.testing.assert_allclose(r['values'],[[0.2,0.7]],atol=1e-6)

    def test_bounds(self):
        r=solve(self.cal,dict(frames=[1],features=[[20,20,20]]))
        self.assertTrue(np.all(np.asarray(r['values'])<=1))

    def test_reject_nonfinite(self):
        with self.assertRaises(ValueError): solve(self.cal,dict(frames=[1],features=[[float('nan'),0,0]]))

    def test_duplicate_frames(self):
        with self.assertRaises(ValueError): solve(self.cal,dict(frames=[1,1],features=[[0,0,0]]*2))

    def test_rank_deficient(self):
        self.cal['matrix']=[[1,1],[2,2],[3,3]]
        r=solve(self.cal,dict(frames=[1],features=[[0.4,0.8,1.2]]))
        self.assertEqual(r['rank'],1)
        self.assertLess(r['feature_rmse'][0],1e-5)

    def test_temporal_reduces_jump(self):
        y=dict(frames=[1,2],features=[[0,0,0],[1,2,2]])
        raw=solve(self.cal,y); smooth=solve(self.cal,y,temporal=100)
        self.assertLess(np.linalg.norm(np.diff(smooth['values'],axis=0)),np.linalg.norm(np.diff(raw['values'],axis=0)))


if __name__=='__main__': unittest.main()
