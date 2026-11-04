from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'evaluations'))
from tensor_workspace_resume import check_prompt
import lora6k_supervisor


class RestoreContext(unittest.TestCase):
    def test_changed_context_tokens_or_seed_cannot_resume(self):
        case={'id':'editor-14','rendered_prompt':'exact','input_ids':[1,2],'rng_seed':2026110324}
        check_prompt(case,'exact',[1,2],14)
        for changed in ({'rendered_prompt':'other'},{'input_ids':[1,3]},{'rng_seed':0},{'id':'editor-13'}):
            with self.assertRaises(ValueError):check_prompt({**case,**changed},'exact',[1,2],14)

    def test_idle_client_exception_keeps_game_compute_and_unknown_owner_checks(self):
        approved=lora6k_supervisor.DESKTOP_GPU_PROCESSES|{'leagueclientuxrender.exe'}
        with patch.object(lora6k_supervisor,'DESKTOP_GPU_PROCESSES',approved):
            client=[['100','LeagueClientUxRender.exe','N/A']]
            self.assertEqual(len(lora6k_supervisor.check_owners(client,{100:'LeagueClientUxRender.exe'},[])),1)
            with self.assertRaises(ValueError):
                lora6k_supervisor.check_owners(client,{100:'LeagueClientUxRender.exe'},[{'Name':'active Compute'}])
            for name in ('League of Legends.exe','python.exe'):
                with self.assertRaises(ValueError):
                    lora6k_supervisor.check_owners([['101',name,'N/A']],{101:name},[])
            with self.assertRaises(ValueError):
                lora6k_supervisor.check_owners([['100','LeagueClientUxRender.exe','128']],{100:'LeagueClientUxRender.exe'},[])


if __name__=='__main__':unittest.main()
