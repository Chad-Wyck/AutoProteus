from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'evaluations'))
from weight_editor_shared_gpu import admission,classify_shared_owners
from weight_editor_runtime import Deadline
from lora6k_supervisor import check_owners


class SharedGPU(unittest.TestCase):
    def test_only_explicit_game_may_share_compute(self):
        names={12:'League of Legends.exe',13:'LeagueClientUxRender.exe',14:'python.exe'}
        row=['12','League of Legends.exe','900']
        compute=[{'Name':'pid_12_luid_0_engtype_Compute_0'}]
        self.assertEqual(classify_shared_owners([row],names,compute,check_owners)[0]['pid'],12)
        for other in ([{'Name':'pid_14_luid_0_engtype_Compute_0'}],[{'Name':'unrecognized Compute'}]):
            with self.assertRaises(ValueError):classify_shared_owners([row],names,other,check_owners)
        with self.assertRaises(ValueError):classify_shared_owners([['14','python.exe','N/A']],names,[],check_owners)
        # A name reported by nvidia alone cannot grant an exception.
        with self.assertRaises(ValueError):classify_shared_owners([row],{},compute,check_owners)

    def test_nonidle_game_still_requires_all_memory_floors(self):
        sample={'utilization':100,'free_vram_mib':8192,'free_ram_kib':8*2**20,
                'free_commit_bytes':4*2**30,'disk_bytes':20*2**30}
        calls=[]
        def observe(_):calls.append(1);return dict(sample)
        admission(observe,Deadline(20),sleep=lambda _:None)
        self.assertEqual(len(calls),3)
        for field in ('free_vram_mib','free_ram_kib','free_commit_bytes','disk_bytes'):
            with self.assertRaises(ValueError):
                admission(lambda _:dict(sample,**{field:sample[field]-1}),Deadline(20),sleep=lambda _:None)

    def test_expired_deadline_never_launches_a_readiness_sample(self):
        deadline=Deadline(end=1.,clock=lambda:2.)
        with self.assertRaises(TimeoutError):admission(lambda _:self.fail('expired sample'),deadline,sleep=lambda _:None)

    def test_idle_windows_overlays_are_not_given_compute_permission(self):
        names={20:'GameBar.exe',21:'XboxGameBarWidgets.exe'}
        rows=[['20','GameBar.exe',' [N/A]'],['21','XboxGameBarWidgets.exe','N/A']]
        self.assertEqual(len(classify_shared_owners(rows,names,[],check_owners)),2)
        with self.assertRaises(ValueError):
            classify_shared_owners(rows,names,[{'Name':'pid_20_luid_0_engtype_Compute_0','UtilizationPercentage':20}],check_owners)
        with self.assertRaises(ValueError):classify_shared_owners([['20','GameBar.exe','200']],names,[],check_owners)

    def test_small_known_desktop_bursts_do_not_authorize_other_models(self):
        names={30:'Discord.exe',31:'brave.exe',32:'python.exe'}
        rows=[['30','Discord.exe','N/A']]
        tiny=[{'Name':'pid_30_luid_0_engtype_Cuda','UtilizationPercentage':1}]
        self.assertEqual(len(classify_shared_owners(rows,names,tiny,check_owners)),1)
        for active in ([{'Name':'pid_30_luid_0_engtype_Cuda','UtilizationPercentage':6}],
                       tiny+[{'Name':'pid_32_luid_0_engtype_Cuda','UtilizationPercentage':1}],
                       [{'Name':'pid_30_luid_0_engtype_Cuda','UtilizationPercentage':3},
                        {'Name':'pid_31_luid_0_engtype_Cuda','UtilizationPercentage':3}]):
            with self.assertRaises(ValueError):classify_shared_owners(rows,names,active,check_owners)

    def test_disappearing_idle_overlay_does_not_gain_unknown_compute_permission(self):
        row=['40',r'C:\WindowsApps\GameBar.exe',' [N/A]']
        accepted=classify_shared_owners([row],{},[],check_owners)
        self.assertFalse(accepted[0]['live_name_observed'])
        with self.assertRaises(ValueError):
            classify_shared_owners([row],{},[{'Name':'pid_40_luid_0_engtype_Cuda','UtilizationPercentage':1}],check_owners)
        with self.assertRaises(ValueError):classify_shared_owners([['40','GameBar.exe','200']],{},[],check_owners)


if __name__=='__main__':unittest.main()
