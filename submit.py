"""Submit alphas to the pending directory for the worker daemon to process."""

import argparse
import sys

from alpha import Alpha, AlphaStage, init_db
from alpha_list import AlphaList
from scorer import SharpeScorer
from research_process import GeneticAlgorithmProcess, GridSearchProcess


def submit_single(name: str, expression: str, settings: dict):
    """Submit a single alpha expression."""
    init_db()
    payload = {
        'type': 'REGULAR',
        'settings': settings,
        'regular': expression,
    }
    alpha = Alpha(name=name, payload=payload)
    alpha.dump()
    print(f'[submit] {alpha.filename} -> {alpha.filepath}')


def submit_ga(process_name: str, template: str, alpha_space: dict,
              settings: dict, ga_config: dict):
    """Submit alphas via genetic algorithm process."""
    init_db()
    ga = GeneticAlgorithmProcess(
        name=process_name,
        scorer=SharpeScorer(),
        alpha_template=template,
        alpha_space=alpha_space,
        alpha_settings=settings,
        ga_config=ga_config,
    )
    ga.run()

    print(f'\n=== GA finished: {len(ga._score_lists)} generations ===')
    for gen_i, scores in enumerate(ga._score_lists):
        print(f'\n--- Generation {gen_i} ---')
        for name, score in scores.items():
            print(f'  {name}: sharpe={score:.4f}')


def submit_grid(process_name: str, template: str, alpha_space: dict, settings: dict):
    """Submit alphas via exhaustive grid search."""
    init_db()
    grid = GridSearchProcess(
        name=process_name,
        scorer=SharpeScorer(),
        alpha_template=template,
        alpha_space=alpha_space,
        alpha_settings=settings,
    )
    grid.run()

    print(f'\n=== Grid search finished ===')
    for name, score in grid._score_lists[-1].items():
        print(f'  {name}: sharpe={score:.4f}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Submit alphas to worker')
    sub = parser.add_subparsers(dest='command')

    # submit single alpha
    single = sub.add_parser('single', help='Submit a single alpha')
    single.add_argument('--name', required=True, help='Alpha name')
    single.add_argument('--expr', required=True, help='Alpha expression')

    # submit GA batch
    ga = sub.add_parser('ga', help='Run genetic algorithm')
    ga.add_argument('--name', default='ga_run', help='Process name')
    ga.add_argument('--generations', type=int, default=3)
    ga.add_argument('--population', type=int, default=5)

    # submit grid search batch
    grid = sub.add_parser('grid', help='Run exhaustive grid search')
    grid.add_argument('--name', default='grid_run', help='Process name')

    args = parser.parse_args()

    default_settings = {
        'instrumentType': 'EQUITY',
        'region': 'USA',
        'universe': 'TOP3000',
        'delay': 1,
        'decay': 15,
        'neutralization': 'SUBINDUSTRY',
        'truncation': 0.08,
        'pasteurization': 'ON',
        'testPeriod': 'P1Y6M',
        'unitHandling': 'VERIFY',
        'nanHandling': 'OFF',
        'language': 'FASTEXPR',
        'visualization': False,
    }

    if args.command == 'single':
        submit_single(args.name, args.expr, default_settings)

    elif args.command == 'ga':
        submit_ga(
            process_name=args.name,
            template='ts_mean({OP}(close, {W1}), {W2})',
            alpha_space={
                '{OP}': ['ts_mean', 'ts_std', 'ts_sum', 'ts_rank'],
                '{W1}': ['5', '10', '20', '50'],
                '{W2}': ['5', '10', '20'],
            },
            settings=default_settings,
            ga_config={
                'generation': args.generations,
                'population': args.population,
                'select_rate': 0.5,
                'mutation_prob': 0.05,
            },
        )

    elif args.command == 'grid':
        template = (
            'data_1 = ts_backfill(<DEBT_DATA>, <BACKFILL_DAYS>);\n'
            'data_2 = ts_backfill(<ASSETS_DATA>, <BACKFILL_DAYS>);\n'
            '<GROUP_OP>(data_1/data_2, <GROUP>)'
        )
        submit_grid(
            process_name=args.name,
            template=template,
            alpha_space={
                '<DEBT_DATA>': ['debt', 'debt_lt', 'debt_st', 'anl4_netdebt_mean'],
                '<ASSETS_DATA>': ['assets', 'assets_curr', 'total_assets_amount', 'fnd6_cptnewqv1300_atq'],
                '<BACKFILL_DAYS>': ['5', '10', '21', '63'],
                '<GROUP_OP>': ['group_rank', 'group_zscore'],
                '<GROUP>': ['market', 'sector', 'industry', 'subindustry', 'pv13_h2_sector'],
            },
            settings=default_settings,
        )

    else:
        parser.print_help()
        sys.exit(1)
