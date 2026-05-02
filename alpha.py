import os
import json
import shutil
from enum import Enum

DB_PATH = '/Users/tsengch/wq_test/db'


class AlphaStage(Enum):
    NONE = 'non_exist'
    PENDING = os.path.join(DB_PATH, 'pending')
    COMPLETE = os.path.join(DB_PATH, 'complete')
    ERROR = os.path.join(DB_PATH, 'error')


def init_db():
    for stage in [AlphaStage.PENDING, AlphaStage.COMPLETE, AlphaStage.ERROR]:
        os.makedirs(stage.value, exist_ok=True)


class Alpha:
    def __init__(self, name: str, payload: dict, alpha_stage: AlphaStage = AlphaStage.PENDING, result: dict = {}):
        self._json = {
            'name': name,
            'payload': payload,
            'stage': alpha_stage.value,
            'result': result,
        }

    @property
    def name(self) -> str:
        return self._json['name']

    @property
    def payload(self) -> dict:
        return self._json['payload']

    @property
    def stage(self) -> AlphaStage:
        return AlphaStage(self._json['stage'])

    @property
    def result(self) -> dict:
        return self._json['result']

    @property
    def filename(self) -> str:
        return f'{self.name}.json'

    @property
    def filepath(self) -> str:
        return os.path.join(self.stage.value, self.filename)

    @property
    def _tmp_filepath(self) -> str:
        return os.path.join(self.stage.value, f'tmp_{self.filename}')

    def dump(self):
        with open(self._tmp_filepath, 'w') as f:
            json.dump(self._json, f)
        shutil.move(self._tmp_filepath, self.filepath)

    @classmethod
    def load(cls, filepath: str) -> 'Alpha':
        with open(filepath, 'r') as f:
            _json = json.load(f)
        return cls(
            name=_json['name'],
            payload=_json['payload'],
            alpha_stage=AlphaStage(_json['stage']),
            result=_json['result'],
        )

    def update_stage(self, new_stage: AlphaStage):
        if os.path.exists(self.filepath):
            os.remove(self.filepath)
        self._json['stage'] = new_stage.value
        self.dump()
