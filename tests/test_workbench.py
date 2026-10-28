import copy,unittest
import numpy as np
from faceinverse import timing,groups,expressions
from tests import test_retarget
from faceinverse.retarget import retarget

class TimingTests(unittest.TestCase):
    def test_60_video_one_frame_per_maya_frame(self):
        np.testing.assert_allclose(timing.frames_from_times([0,1/60,2/60],60),[1,2,3])
    def test_output_rate_preserves_elapsed_time(self):
        times=[0,.016,.033,.1,10.1]
        for fps in (24,29.97,60):
            np.testing.assert_allclose((np.array(timing.frames_from_times(times,fps,1001))-1001)/fps,times,atol=1e-12)
    def test_invalid_rate_and_timestamps_rejected(self):
        for fps in (0,-1,float('nan'),1000):
            with self.assertRaises(ValueError):timing.valid_fps(fps)
        with self.assertRaises(ValueError):timing.frames_from_times([0,0],60)
    def test_rotation_inverse(self):
        for angle in (0,90,180,270):
            x,y=timing.rotate_xy(.2,.7,angle)
            np.testing.assert_allclose(timing.rotate_xy(x,y,-angle),(.2,.7))
        with self.assertRaises(ValueError):timing.rotation(45)
    def test_ntsc_uses_maya_actual_rational_rate(self):
        self.assertAlmostEqual(timing.scene_rate(29.97),30000/1001.)
        self.assertEqual(timing.maya_unit(60000/1001.),'59.94fps')
        with self.assertRaises(ValueError):timing.scene_rate(57.5)
    def test_changing_output_time_does_not_change_inverse_values(self):
        cal=test_retarget.RetargetTests().calibration()
        tracking=dict(fps=60,frames=[dict(time_seconds=i/60,detected=True,scores={'positive':v,'negative':0}) for i,v in enumerate([0,.2,.8,.3])])
        a=retarget(cal,tracking,scene_fps=24);b=retarget(cal,tracking,scene_fps=60,start_frame=1001)
        np.testing.assert_array_equal(a['values'],b['values'])
        np.testing.assert_array_equal(a['predicted_observations'],b['predicted_observations'])

class GroupTests(unittest.TestCase):
    def setUp(self):
        self.plugs=['CTRL_brow.ty','CTRL_eye.ty','CTRL_mouth.ty','CTRL_jaw.ty']
        self.info=dict(samples=[dict(values={'CTRL_eye.ty':.2})],groups={'my':dict(name='眼和嘴',plugs=self.plugs[1:3])})
    def test_recording_mask_is_explicit(self):
        self.assertEqual(groups.channels(self.info,self.plugs,'group:my'),self.plugs[1:3])
    def test_editing_group_does_not_rewrite_existing_sample(self):
        original=copy.deepcopy(self.info);view=groups.available(self.info,self.plugs);view['my']['plugs'].append(self.plugs[0])
        self.assertEqual(self.info,original)
    def test_unregistered_channel_is_rejected(self):
        with self.assertRaises(ValueError):groups.validate(self.info['groups'],dict(physical_controls=[dict(plug='other')]))
    def test_empty_explicit_groups_remain_empty(self):self.assertEqual(groups.available({'groups':{}},self.plugs),{})

class CandidateTests(unittest.TestCase):
    def points(self,lift=0.):
        p=[[.5,.5,0.] for _ in range(478)];p[33]=[.2,.3,0];p[263]=[.8,.3,0]
        p[13]=p[14]=[.5,.6,0];p[61]=[.35,.6-lift,0];p[291]=[.65,.6-lift,0];return p
    def tracking(self,scores,lifts):
        return dict(fps=24,width=100,height=100,frames=[dict(time_seconds=i/24,detected=True,scores={'mouthSmileLeft':v,'mouthSmileRight':v},landmarks=self.points(l)) for i,(v,l) in enumerate(zip(scores,lifts))])
    def test_weak_clip_maximum_is_not_smile(self):
        result=expressions.candidates(self.tracking([.01,.1,.08,.05],[0]*4))
        self.assertFalse(any(r['action']=='mouthSmile' for r in result))
    def test_single_false_spike_is_not_smile(self):
        result=expressions.candidates(self.tracking([.01,.9,.01],[0,.05,0]))
        self.assertFalse(any(r['action']=='mouthSmile' for r in result))
    def test_sustained_score_without_geometry_is_not_smile(self):
        result=expressions.candidates(self.tracking([.01,.01,.8,.9,.8],[0]*5))
        self.assertFalse(any(r['action']=='mouthSmile' for r in result))
    def test_supported_corner_raise_is_only_a_candidate(self):
        result=expressions.candidates(self.tracking([.01,.01,.8,.9,.8],[0,0,.04,.05,.04]))
        row=next(r for r in result if r['action']=='mouthSmile')
        self.assertIn('待确认',row['label']);self.assertIn('proxy',row['facs_status'])
    def test_no_neutral_anchor_abstains_on_smile(self):
        result=expressions.candidates(self.tracking([.8,.9,.8],[.04,.05,.04]))
        self.assertFalse(any(r['action']=='mouthSmile' for r in result))
