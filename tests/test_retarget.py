import unittest
import numpy as np
from faceinverse.retarget import retarget,fill_missing,landmark_assist

class RetargetTests(unittest.TestCase):
    def calibration(self):
        return dict(matrix=[[1.,0.],[0.,1.]],neutral=[0.,0.],observation_names=['positive','negative'],
            physical_controls=[dict(plug='CTRL.x',neutral=0.,min=-1.,max=1.)],
            variables=[dict(physical_index=0,sign=1,amplitude=1.),dict(physical_index=0,sign=-1,amplitude=1.)],
            mapping={'positive':{'positive':1.},'negative':{'negative':1.}})
    def test_signed_bounds_and_folded_observations(self):
        rows=[dict(time_seconds=0,detected=True,scores={'positive':.8,'negative':.4}),
              dict(time_seconds=1/24,detected=True,scores={'positive':.1,'negative':.9})]
        result=retarget(self.calibration(),dict(fps=24,frames=rows),temporal=0,assist=False)
        for row,obs in zip(result['values'],result['predicted_observations']):
            self.assertLessEqual(abs(row[0]),1.)
            np.testing.assert_allclose(obs,[max(row[0],0),max(-row[0],0)],atol=1e-8)
    def test_default_does_not_enable_amplitude_heuristics(self):
        rows=[dict(time_seconds=i/24,detected=True,scores={'positive':.2,'negative':0}) for i in range(3)]
        tracking=dict(fps=24,frames=rows)
        default=retarget(self.calibration(),tracking)
        explicit=retarget(self.calibration(),tracking,assist=False)
        self.assertFalse(default['landmark_assistance']['applied'])
        np.testing.assert_array_equal(default['values'],explicit['values'])

    def test_fractional_frame_timebase(self):
        fps=30000/1001
        rows=[dict(time_seconds=i/fps,detected=True,scores={'positive':0,'negative':0}) for i in range(3)]
        r=retarget(self.calibration(),dict(fps=fps,frames=rows),assist=False)
        self.assertAlmostEqual(r['frames'][2],1+48/fps)
    def test_two_frame_gap(self):
        rows=[dict(detected=True,scores={'x':.2}),dict(detected=False),dict(detected=False),dict(detected=True,scores={'x':.8})]
        values,valid,quality=fill_missing(rows,['x'],24)
        np.testing.assert_allclose(values[:,0],[.2,.4,.6,.8])
        self.assertEqual(quality[1:3],['interpolated_short_gap']*2)
        self.assertEqual(valid.tolist(),[True,False,False,True])
    def test_long_gap_fades_and_never_marks_detected(self):
        rows=[dict(detected=True,scores={'x':1.})]+[dict(detected=False)]*20
        values,valid,quality=fill_missing(rows,['x'],24)
        self.assertEqual(values[1,0],1.)
        self.assertEqual(values[15,0],0.)
        self.assertFalse(valid[15])
    def test_all_missing_rejected(self):
        with self.assertRaises(ValueError):fill_missing([dict(detected=False)],['x'],24)
    def test_invalid_scores_rejected(self):
        rows=[dict(time_seconds=0,detected=True,scores={'positive':float('nan'),'negative':0})]
        with self.assertRaises(ValueError):retarget(self.calibration(),dict(fps=24,frames=rows),assist=False)
    def test_invalid_time_and_prior_rejected(self):
        rows=[dict(time_seconds=0,detected=True,scores={'positive':0,'negative':0})]
        with self.assertRaises(ValueError):retarget(self.calibration(),dict(fps=24,frames=rows),temporal=-1)
        with self.assertRaises(ValueError):retarget(self.calibration(),dict(fps=float('nan'),frames=rows))
    def test_landmark_assisted_open_mouth_and_closed_eyes(self):
        names=['jawOpen']+[prefix+side for prefix in ('eyeBlink','eyeWide','mouthSmile','mouthFrown') for side in ('Left','Right')]
        p=np.zeros((478,3));p[33,:2]=[.2,.3];p[263,:2]=[.8,.3];p[133,:2]=[.3,.3];p[362,:2]=[.7,.3]
        for up,down,x in [(159,145,.25),(386,374,.75)]:p[up,:2]=[x,.28];p[down,:2]=[x,.32]
        p[13,:2]=[.5,.6];p[14,:2]=[.5,.6];p[61,:2]=[.3,.6];p[291,:2]=[.7,.6]
        q=p.copy();q[14,1]=.85
        for up,down in [(159,145),(386,374)]:q[up,1]=.299;q[down,1]=.301
        rows=[dict(detected=True,landmarks=x.tolist()) for x in (p,q)]
        result,report=landmark_assist(np.zeros((2,len(names))),names,rows,dict(width=100,height=100,fps=24),0)
        self.assertTrue(report['applied']);self.assertGreater(result[1,names.index('jawOpen')],.9)
        self.assertGreater(result[1,names.index('eyeBlinkLeft')],.9)

if __name__=='__main__':unittest.main()
