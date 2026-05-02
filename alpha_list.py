import os
import time
from typing import Dict, List, Tuple

from tqdm import tqdm

from alpha import Alpha, AlphaStage


class AlphaList:
    def __init__(self, alphas: List[Alpha], names: List[str]):
        self._alphas = alphas
        self._names = [alpha.filename for alpha in alphas]

    @staticmethod
    def check_alpha_stage(filename: str) -> AlphaStage:
        for stage in [AlphaStage.PENDING, AlphaStage.COMPLETE, AlphaStage.ERROR]:
            if os.path.exists(os.path.join(stage.value, filename)):
                return stage
        return AlphaStage.NONE

    def update_and_check_status(self) -> Tuple[int, int, int, int]:
        none_count = 0
        pending_count = 0
        complete_count = 0
        error_count = 0

        for idx, alpha in enumerate(self._alphas):
            disk_stage = self.check_alpha_stage(alpha.filename)

            if disk_stage != alpha.stage and disk_stage != AlphaStage.NONE:
                filepath = os.path.join(disk_stage.value, alpha.filename)
                self._alphas[idx] = Alpha.load(filepath)

            current_stage = self._alphas[idx].stage
            if current_stage == AlphaStage.NONE:
                none_count += 1
            elif current_stage == AlphaStage.PENDING:
                pending_count += 1
            elif current_stage == AlphaStage.COMPLETE:
                complete_count += 1
            elif current_stage == AlphaStage.ERROR:
                error_count += 1

        return none_count, pending_count, complete_count, error_count

    def sim_and_wait(self):
        for alpha in self._alphas:
            if self.check_alpha_stage(alpha.filename) == AlphaStage.NONE:
                alpha.dump()

        total = len(self._alphas)
        prev_done = 0
        with tqdm(total=total, desc='Simulating') as pbar:
            while True:
                none_c, pending_c, complete_c, error_c = self.update_and_check_status()
                done = complete_c + error_c
                delta = done - prev_done
                if delta > 0:
                    pbar.update(delta)
                prev_done = done
                if done == total:
                    break
                time.sleep(1)

    def get_alphas(self) -> Dict[str, Alpha]:
        self.update_and_check_status()
        return dict(zip(self._names, self._alphas))
