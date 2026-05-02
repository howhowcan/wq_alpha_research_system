import itertools
import random
from abc import ABC, abstractmethod
from typing import Dict, List

import numpy as np

from alpha import Alpha
from alpha_list import AlphaList


class ResearchProcessBase(ABC):
    def __init__(self, process_name: str, scorer, additional_scorers=None):
        if additional_scorers is None:
            additional_scorers = []
        self.process_name = process_name
        self.scorer = scorer
        self.additional_scorers = additional_scorers
        self._alpha_lists: List[AlphaList] = []
        self._score_lists: List[Dict[str, float]] = []

    def generate_alpha_name(self, gen: int, i: int) -> str:
        return f'{self.process_name}_{gen}_{i}'

    def sim_alphas(self, alphas: List[Alpha]):
        alpha_list = AlphaList(alphas, [a.name for a in alphas])
        self._alpha_lists.append(alpha_list)
        alpha_list.sim_and_wait()
        alphas_dict = alpha_list.get_alphas()
        scores = {name: self.scorer.score(alpha) for name, alpha in alphas_dict.items()}
        self._score_lists.append(scores)

    @abstractmethod
    def run(self):
        pass


class GeneticAlgorithmProcess(ResearchProcessBase):
    def __init__(self, name: str, scorer, alpha_template: str, alpha_space: dict,
                 alpha_settings: dict, ga_config: dict = None):
        super().__init__(name, scorer)
        self.template = alpha_template
        self.alpha_space = alpha_space
        self.alpha_settings = alpha_settings
        if ga_config is None:
            ga_config = {
                'generation': 15,
                'population': 50,
                'select_rate': 0.5,
                'mutation_prob': 0.05,
            }
        self.ga_config = ga_config
        self._generation_genes: List[Dict[str, Dict[str, str]]] = []

    def _generate_expr(self, gene: dict) -> str:
        expr = self.template
        for placeholder, value in gene.items():
            expr = expr.replace(placeholder, value)
        return expr

    def _init_population(self):
        self._generation_iter(gen_i=0, genes=[])

    def _generation_iter(self, gen_i: int, genes: List[dict]):
        population = self.ga_config['population']
        if not genes:
            genes = []
            for _ in range(population):
                gene = {k: random.choice(v) for k, v in self.alpha_space.items()}
                genes.append(gene)

        gen_gene_map: Dict[str, Dict[str, str]] = {}
        alphas = []
        for i, gene in enumerate(genes):
            name = self.generate_alpha_name(gen_i, i)
            expr = self._generate_expr(gene)
            payload = {
                'type': 'REGULAR',
                'settings': self.alpha_settings,
                'regular': expr,
            }
            alpha = Alpha(name=name, payload=payload)
            alphas.append(alpha)
            gen_gene_map[name] = gene

        self._generation_genes.append(gen_gene_map)
        self.sim_alphas(alphas)

    def _select(self, scores: Dict[str, float]) -> List[str]:
        threshold = np.quantile(list(scores.values()), self.ga_config['select_rate'])
        return [name for name, s in scores.items() if s >= threshold]

    def _crossover(self, parent_genes: List[dict]) -> dict:
        child = {}
        for placeholder in self.alpha_space:
            parent = random.choice(parent_genes)
            child[placeholder] = parent[placeholder]
        return child

    def _mutate(self, gene: dict) -> dict:
        mutated = {}
        for placeholder, value in gene.items():
            if random.random() < self.ga_config['mutation_prob']:
                mutated[placeholder] = random.choice(self.alpha_space[placeholder])
            else:
                mutated[placeholder] = value
        return mutated

    def run(self):
        self._init_population()
        generations = self.ga_config['generation']
        population = self.ga_config['population']

        for gen_i in range(1, generations):
            prev_scores = self._score_lists[-1]
            survivors = self._select(prev_scores)

            parent_genes = [
                self._generation_genes[gen_i - 1][name[:-5] if name.endswith('.json') else name]
                for name in survivors
            ]

            new_genes = []
            for _ in range(population):
                child = self._crossover(parent_genes)
                child = self._mutate(child)
                new_genes.append(child)

            self._generation_iter(gen_i, new_genes)


class GridSearchProcess(ResearchProcessBase):
    """Exhaustive search: try every combination of values in alpha_space."""

    def __init__(self, name: str, scorer, alpha_template: str, alpha_space: dict,
                 alpha_settings: dict):
        super().__init__(name, scorer)
        self.template = alpha_template
        self.alpha_space = alpha_space
        self.alpha_settings = alpha_settings

    def _generate_expr(self, gene: dict) -> str:
        expr = self.template
        for placeholder, value in gene.items():
            expr = expr.replace(placeholder, value)
        return expr

    def run(self):
        placeholders = list(self.alpha_space.keys())
        value_lists = [self.alpha_space[p] for p in placeholders]

        alphas = []
        for i, combo in enumerate(itertools.product(*value_lists)):
            gene = dict(zip(placeholders, combo))
            name = self.generate_alpha_name(0, i)
            expr = self._generate_expr(gene)
            payload = {
                'type': 'REGULAR',
                'settings': self.alpha_settings,
                'regular': expr,
            }
            alphas.append(Alpha(name=name, payload=payload))

        print(f'[grid] Generated {len(alphas)} combinations')
        self.sim_alphas(alphas)
