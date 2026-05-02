"""
Test run: submit a GA batch.
Make sure worker.py is already running in another terminal:

    Terminal 1:  python3 worker.py --fake
    Terminal 2:  python3 test_run.py
"""

from alpha import init_db
from scorer import SharpeScorer
from research_process import GeneticAlgorithmProcess

init_db()

ga = GeneticAlgorithmProcess(
    name='test_ga',
    scorer=SharpeScorer(),
    alpha_template='ts_mean({OP}(close, {W1}), {W2})',
    alpha_space={
        '{OP}': ['ts_mean', 'ts_std', 'ts_sum', 'ts_rank'],
        '{W1}': ['5', '10', '20', '50'],
        '{W2}': ['5', '10', '20'],
    },
    alpha_settings={
        'type': 'REGULAR',
        'region': 'USA',
        'universe': 'TOP3000',
        'delay': 1,
        'decay': 0,
        'neutralization': 'SUBINDUSTRY',
        'truncation': 0.08,
    },
    ga_config={
        'generation': 3,
        'population': 5,
        'select_rate': 0.5,
        'mutation_prob': 0.05,
    },
)

print('=== Starting GA test run ===')
print('(Make sure worker.py --fake is running in another terminal)')
ga.run()

for gen_i, scores in enumerate(ga._score_lists):
    print(f'\n--- Generation {gen_i} ---')
    for name, score in scores.items():
        print(f'  {name}: sharpe={score:.4f}')

print(f'\nTotal generations: {len(ga._score_lists)}')
