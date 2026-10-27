import copy,json,tempfile,unittest
from pathlib import Path
import numpy as np
from faceinverse import session
from faceinverse.pose_solver import solve_samples,smooth_residual

class PoseSampleTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'work');self.root=Path(self.tmp.name)
        self.plugs=['|gui|CTRL_C_jaw.translateY','|gui|CTRL_L_eye_blink.translateY']
        self.cal=dict(physical_controls=[dict(plug=p,min=0.,max=1.,neutral=0.) for p in self.plugs],
            variables=[dict(physical_index=i,sign=1,amplitude=1.) for i in range(2)],matrix=[[1,0],[0,1]],neutral=[0,0],observation_names=['jaw','blink'])
        self.tracking=dict(source='test.mp4',fps=24,width=100,height=100,frames=[dict(time_seconds=i/24,detected=True,scores={'x':v}) for i,v in enumerate([.5,.1,.9,.5,.2,.5])])
        self.base=dict(plugs=self.plugs,frames=list(range(1,7)),values=[[.1,.2]]*6,predicted_observations=[[.1,.2]]*6,semantic_targets=[[.1,.2]]*6)
        for name,value in [('cal.json',self.cal),('track.json',self.tracking),('base.json',self.base)]:session.save(self.root/name,value,False)
        self.path=self.root/'session.json';session.create(self.path,self.root/'cal.json',self.root/'track.json',self.root/'base.json',{})
        s=session.load(self.path);s['settings']['smoothing']=0;session.save(self.path,s)
    def tearDown(self):self.tmp.cleanup()
    def solve(self):return solve_samples(*session.inputs(self.path))
    def capture(self,frame=0,value=.8,**kw):return session.capture(self.path,frame,{self.plugs[0]:value},**kw)
    def test_repeated_expression_not_timeline_interpolation(self):
        self.capture();r=self.solve()
        self.assertEqual(r['values'][0][0],.8)
        self.assertAlmostEqual(r['values'][5][0],.8,places=5)
    def test_channel_mask_preserves_other_channels(self):
        self.capture();r=self.solve();np.testing.assert_array_equal(np.array(r['values'])[:,1],np.full(6,.2))
    def test_local_sample_does_not_change_distant_repeated_expression(self):
        self.capture(mode='local',time_radius=.06);r=self.solve();self.assertEqual(r['values'][5][0],.1)
        self.assertEqual(r['values'][0][0],.8)
    def test_conflicting_same_expression_rejected(self):
        self.capture(0,.8);self.capture(3,.4)
        with self.assertRaisesRegex(ValueError,'矛盾'):self.solve()
    def test_conflicting_same_frame_hard_constraints_rejected(self):
        self.capture(0,.8,mode='local');self.capture(0,.5,mode='local')
        with self.assertRaisesRegex(ValueError,'冲突'):self.solve()
    def test_disable_and_delete_are_persistent(self):
        a=self.capture();session.set_enabled(self.path,a['id'],False);self.assertEqual(self.solve()['values'],self.base['values'])
        session.delete_sample(self.path,a['id']);self.assertEqual(session.load(self.path)['samples'],[])
        self.assertTrue(list((self.root/'history').glob('*.json')))
    def test_update_selected_sample(self):
        a=self.capture();self.capture(value=.7,sample_id=a['id']);self.assertEqual(len(session.load(self.path)['samples']),1)
        self.assertEqual(self.solve()['values'][0][0],.7)
    def test_bounds_and_nonfinite_rejected(self):
        for value in (2.,float('nan')):
            with self.assertRaises(ValueError):self.capture(value=value)
    def test_missing_frame_not_sampled(self):
        tracking=session.load(self.root/'track.json');tracking['frames'][0]['detected']=False;session.save(self.root/'track.json',tracking,False)
        with self.assertRaises(ValueError):self.capture()
    def test_baseline_and_rig_changes_rejected(self):
        base=copy.deepcopy(self.base);base['values'][0]=[.3,.2];session.save(self.root/'base.json',base,False)
        with self.assertRaisesRegex(ValueError,'基线'):session.inputs(self.path)
        session.save(self.root/'base.json',self.base,False);cal=copy.deepcopy(self.cal);cal['physical_controls'][0]['max']=2.;session.save(self.root/'cal.json',cal,False)
        with self.assertRaisesRegex(ValueError,'角色'):session.inputs(self.path)
    def test_library_roundtrip_and_mismatch(self):
        self.capture();session.export_library(self.path,self.root/'library.json');session.import_library(self.path,self.root/'library.json')
        self.assertEqual(len(session.load(self.path)['samples']),1)
        library=session.load(self.root/'library.json');library['rig_signature']='invalid';session.save(self.root/'library.json',library,False)
        with self.assertRaises(ValueError):session.import_library(self.path,self.root/'library.json')
    def test_hard_constraints_survive_smoothing(self):
        r=smooth_residual(np.arange(9,dtype=float),{2:12.,6:-3.},2.)
        self.assertEqual(r[2],12.);self.assertEqual(r[6],-3.)
        self.capture();s=session.load(self.path);s['settings']['smoothing']=2.;session.save(self.path,s)
        self.assertEqual(self.solve()['values'][0][0],.8)
    def test_no_samples_exactly_preserves_baseline(self):self.assertEqual(self.solve()['values'],self.base['values'])
    def test_save_load_relocation_and_unicode(self):
        moved=self.root/'移动 项目';moved.mkdir()
        for name in ('cal.json','track.json','base.json','session.json'):(moved/name).write_bytes((self.root/name).read_bytes())
        self.assertEqual(session.inputs(moved/'session.json')[3],self.base)

if __name__=='__main__':unittest.main()
