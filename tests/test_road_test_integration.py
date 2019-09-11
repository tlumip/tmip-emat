

import platform
if 'Darwin' in platform.platform():
	import matplotlib
	matplotlib.use("TkAgg")


import unittest
import pytest
from pytest import approx
import emat

import ema_workbench
import os, numpy, pandas, functools, random
from emat.experiment.experimental_design import design_experiments
from emat.model.core_python import PythonCoreModel
from emat.model.core_python import Road_Capacity_Investment
from ema_workbench import SequentialEvaluator

class TestRoadTest(unittest.TestCase):

	#
	# Tests
	#
	def test_road_test(self):
		road_test_scope_file = emat.package_file('model', 'tests', 'road_test.yaml')

		road_scope = emat.Scope(road_test_scope_file)

		# <emat.Scope with 2 constants, 7 uncertainties, 4 levers, 7 measures>
		assert len(road_scope.get_measures()) == 7
		assert len(road_scope.get_levers()) == 4
		assert len(road_scope.get_uncertainties()) == 7
		assert len(road_scope.get_constants()) == 2

		emat_db = emat.SQLiteDB()

		road_scope.store_scope(emat_db)

		with pytest.raises(KeyError):
			road_scope.store_scope(emat_db)

		assert emat_db.read_scope_names() == ['EMAT Road Test']

		design = design_experiments(road_scope, db=emat_db, n_samples_per_factor=10, sampler='lhs')
		design.head()

		large_design = design_experiments(road_scope, db=emat_db, n_samples=5000, sampler='lhs',
										  design_name='lhs_large')
		large_design.head()

		assert list(large_design.columns) == [
			'alpha',
			'amortization_period',
			'beta',
			'debt_type',
			'expand_capacity',
			'input_flow',
			'interest_rate',
			'interest_rate_lock',
			'unit_cost_expansion',
			'value_of_time',
			'yield_curve',
			'free_flow_time',
			'initial_capacity',
		]

		assert list(large_design.head().index) == [111, 112, 113, 114, 115]

		assert emat_db.read_design_names('EMAT Road Test') == ['lhs', 'lhs_large']

		m = PythonCoreModel(Road_Capacity_Investment, scope=road_scope, db=emat_db)

		with SequentialEvaluator(m) as eval_seq:
			lhs_results = m.run_experiments(design_name='lhs', evaluator=eval_seq)

		lhs_results.head()

		assert lhs_results.head()['present_cost_expansion'].values == approx(
			[2154.41598475, 12369.38053473, 4468.50683924, 6526.32517089, 2460.91070514])

		assert lhs_results.head()['net_benefits'].values == approx(
			[-79.51551505, -205.32148044, -151.94431822, -167.62487134, -3.97293985])

		with SequentialEvaluator(m) as eval_seq:
			lhs_large_results = m.run_experiments(design_name='lhs_large', evaluator=eval_seq)
		lhs_large_results.head()

		assert lhs_large_results.head()['net_benefits'].values == approx(
			[-584.36098322, -541.5458395, -185.16661464, -135.85689709, -357.36106457])

		lhs_outcomes = m.read_experiment_measures(design_name='lhs')
		assert lhs_outcomes.head()['time_savings'].values == approx(
			[13.4519273, 26.34172999, 12.48385198, 15.10165981, 15.48056139])

		correct_scores = numpy.array(
			[[0.06603461, 0.04858595, 0.06458574, 0.03298163, 0.05018515, 0., 0., 0.53156587, 0.05060416, 0.02558088,
			  0.04676956, 0.04131266, 0.04179378],
			 [0.06003223, 0.04836434, 0.06059554, 0.03593644, 0.27734396, 0., 0., 0.28235419, 0.05303979, 0.03985181,
			  0.04303371, 0.05004349, 0.04940448],
			 [0.08760605, 0.04630414, 0.0795043, 0.03892201, 0.10182534, 0., 0., 0.42508457, 0.04634321, 0.03216387,
			  0.0497183, 0.04953772, 0.0429905],
			 [0.08365598, 0.04118732, 0.06716887, 0.03789444, 0.06509519, 0., 0., 0.31494171, 0.06517462, 0.02895742,
			  0.04731707, 0.17515158, 0.07345581],
			 [0.06789382, 0.07852257, 0.05066944, 0.04807088, 0.32054735, 0., 0., 0.15953055, 0.05320201, 0.02890069,
			  0.07033928, 0.06372418, 0.05859923],
			 [0.05105435, 0.09460353, 0.04614178, 0.04296901, 0.45179611, 0., 0., 0.04909801, 0.05478798, 0.023099,
			  0.08160785, 0.05642169, 0.04842069],
			 [0.04685703, 0.03490931, 0.03214081, 0.03191602, 0.56130318, 0., 0., 0.04011044, 0.04812986, 0.02228924,
			  0.09753361, 0.04273004, 0.04208045], ])

		scores = m.get_feature_scores('lhs', random_state=123)

		for _i in range(scores.metadata.values.shape[0]):
			for _j in range(scores.metadata.values.shape[1]):
				assert scores.metadata.values[_i,_j] == approx(correct_scores[_i,_j], rel=.1)

		from ema_workbench.analysis import prim

		x = m.read_experiment_parameters(design_name='lhs_large')

		prim_alg = prim.Prim(
			m.read_experiment_parameters(design_name='lhs_large'),
			m.read_experiment_measures(design_name='lhs_large')['net_benefits'] > 0,
			threshold=0.4,
		)

		box1 = prim_alg.find_box()

		assert dict(box1.peeling_trajectory.iloc[45]) == approx({
			'coverage': 0.8014705882352942,
			'density': 0.582109479305741,
			'id': 45,
			'mass': 0.1498,
			'mean': 0.582109479305741,
			'res_dim': 4,
		})

		from emat.util.xmle import Show
		from emat.util.xmle.elem import Elem

		assert isinstance(Show(box1.show_tradeoff()), Elem)

		from ema_workbench.analysis import cart

		cart_alg = cart.CART(
			m.read_experiment_parameters(design_name='lhs_large'),
			m.read_experiment_measures(design_name='lhs_large')['net_benefits'] > 0,
		)
		cart_alg.build_tree()

		cart_dict = dict(cart_alg.boxes[0].iloc[0])
		assert cart_dict['debt_type'] == {'GO Bond', 'Paygo', 'Rev Bond'}
		assert cart_dict['interest_rate_lock'] == {False, True}
		del cart_dict['debt_type']
		del cart_dict['interest_rate_lock']
		assert cart_dict == approx({
			'free_flow_time': 60,
			'initial_capacity': 100,
			'alpha': 0.10001988547129116,
			'beta': 3.500215589924521,
			'input_flow': 80.0,
			'value_of_time': 0.00100690634109406,
			'unit_cost_expansion': 95.00570832093116,
			'interest_rate': 0.0250022738169142,
			'yield_curve': -0.0024960505548531774,
			'expand_capacity': 0.0006718732232418368,
			'amortization_period': 15,
		})

		assert isinstance(Show(cart_alg.show_tree(format='svg')), Elem)

		from emat import Measure

		MAXIMIZE = Measure.MAXIMIZE
		MINIMIZE = Measure.MINIMIZE

		robustness_functions = [
			Measure(
				'Expected Net Benefit',
				kind=Measure.INFO,
				variable_name='net_benefits',
				function=numpy.mean,
				#         min=-150,
				#         max=50,
			),

			Measure(
				'Probability of Net Loss',
				kind=MINIMIZE,
				variable_name='net_benefits',
				function=lambda x: numpy.mean(x < 0),
				min=0,
				max=1,
			),

			Measure(
				'95%ile Travel Time',
				kind=MINIMIZE,
				variable_name='build_travel_time',
				function=functools.partial(numpy.percentile, q=95),
				min=60,
				max=150,
			),

			Measure(
				'99%ile Present Cost',
				kind=Measure.INFO,
				variable_name='present_cost_expansion',
				function=functools.partial(numpy.percentile, q=99),
				#         min=0,
				#         max=10,
			),

			Measure(
				'Expected Present Cost',
				kind=Measure.INFO,
				variable_name='present_cost_expansion',
				function=numpy.mean,
				#         min=0,
				#         max=10,
			),

		]

		from emat import Constraint

		constraint_1 = Constraint(
			"Maximum Log Expected Present Cost",
			outcome_names="Expected Present Cost",
			function=Constraint.must_be_less_than(4000),
		)

		constraint_2 = Constraint(
			"Minimum Capacity Expansion",
			parameter_names="expand_capacity",
			function=Constraint.must_be_greater_than(10),
		)

		constraint_3 = Constraint(
			"Maximum Paygo",
			parameter_names='debt_type',
			outcome_names='99%ile Present Cost',
			function=lambda i, j: max(0, j - 1500) if i == 'Paygo' else 0,
		)

		from emat.optimization import HyperVolume, EpsilonProgress, SolutionViewer, ConvergenceMetrics

		convergence_metrics = ConvergenceMetrics(
			HyperVolume.from_outcomes(robustness_functions),
			EpsilonProgress(),
			SolutionViewer.from_model_and_outcomes(m, robustness_functions),
		)

		with SequentialEvaluator(m) as eval_seq:
			robust = m.robust_optimize(
				robustness_functions,
				scenarios=20,
				nfe=5,
				constraints=[
					constraint_1,
					constraint_2,
					constraint_3,
				],
				epsilons=[0.05, ] * len(robustness_functions),
				convergence=convergence_metrics,
				evaluator=eval_seq,
			)
		robust_results, convergence = robust.result, robust.convergence

		assert isinstance(robust_results, pandas.DataFrame)

		mm = m.create_metamodel_from_design('lhs')

		design2 = design_experiments(road_scope, db=emat_db, n_samples_per_factor=10, sampler='lhs', random_seed=2)

		design2_results = mm.run_experiments(design2)


	def test_robust_evaluation(self):
		# %%

		import os
		test_dir = os.path.dirname(__file__)

		from ema_workbench import ema_logging, MultiprocessingEvaluator, SequentialEvaluator
		from emat.examples import road_test
		import numpy, pandas, functools
		from emat import Measure
		s, db, m = road_test()

		MAXIMIZE = Measure.MAXIMIZE
		MINIMIZE = Measure.MINIMIZE

		robustness_functions = [
			Measure(
				'Expected Net Benefit',
				kind=Measure.INFO,
				variable_name='net_benefits',
				function=numpy.mean,
			),

			Measure(
				'Probability of Net Loss',
				kind=MINIMIZE,
				variable_name='net_benefits',
				function=lambda x: numpy.mean(x < 0),
				min=0,
				max=1,
			),

			Measure(
				'95%ile Travel Time',
				kind=MINIMIZE,
				variable_name='build_travel_time',
				function=functools.partial(numpy.percentile, q=95),
				min=60,
				max=150,
			),

			Measure(
				'99%ile Present Cost',
				kind=Measure.INFO,
				variable_name='present_cost_expansion',
				function=functools.partial(numpy.percentile, q=99),
			),

			Measure(
				'Expected Present Cost',
				kind=Measure.INFO,
				variable_name='present_cost_expansion',
				function=numpy.mean,
			),

		]
		# %%

		numpy.random.seed(42)

		with MultiprocessingEvaluator(m) as evaluator:
			r1 = m.robust_evaluate(
				robustness_functions,
				scenarios=20,
				policies=5,
				evaluator=evaluator,
			)

		import pandas
		correct = pandas.read_json(
			'{"amortization_period":{"0":19,"1":23,"2":50,"3":43,"4":35},"debt_type":{"0":"Rev Bond","1":"Paygo"'
			',"2":"GO Bond","3":"Paygo","4":"Rev Bond"},"expand_capacity":{"0":26.3384401031,"1":63.3898549337,"2'
			'":51.1360252492,"3":18.7230954832,"4":93.9205959335},"interest_rate_lock":{"0":false,"1":true,"2":fal'
			'se,"3":true,"4":false},"Expected Net Benefit":{"0":-157.486494925,"1":-244.2423401934,"2":-189.633908'
			'4553,"3":-4.2656265778,"4":-481.1208898635},"Probability of Net Loss":{"0":0.95,"1":1.0,"2":0.95,"3":'
			'0.7,"4":1.0},"95%ile Travel Time":{"0":74.6904209781,"1":65.8492894317,"2":67.6932507947,"3":79.09851'
			'23853,"4":63.203313888},"99%ile Present Cost":{"0":3789.8036648358,"1":9121.0832380586,"2":7357.89572'
			'71441,"3":2694.0416972887,"4":13514.111590462},"Expected Present Cost":{"0":3158.4461451444,"1":7601.'
			'5679809722,"2":6132.1164500957,"3":2245.2312484183,"4":11262.7453643551}}')
		correct['debt_type'] = correct['debt_type'].astype(
			pandas.CategoricalDtype(categories=['GO Bond', 'Rev Bond', 'Paygo'], ordered=True))

		pandas.testing.assert_frame_equal(r1, correct)

		numpy.random.seed(7)

		from ema_workbench.em_framework.samplers import sample_uncertainties
		scenes = sample_uncertainties(m, 20)

		scenes0 = pandas.DataFrame(scenes)
		cachefile = os.path.join(test_dir,'test_robust_results.csv')
		if not os.path.exists(cachefile):
			scenes0.to_csv(os.path.join(test_dir,'test_robust_evaluation_scenarios.csv'), index=None)
		scenes1 = pandas.read_csv(os.path.join(test_dir,'test_robust_evaluation_scenarios.csv'))
		pandas.testing.assert_frame_equal(scenes0, scenes1)

		from emat import Constraint

		constraint_1 = Constraint(
			"Maximum Log Expected Present Cost",
			outcome_names="Expected Present Cost",
			function=Constraint.must_be_less_than(4000),
		)

		constraint_2 = Constraint(
			"Minimum Capacity Expansion",
			parameter_names="expand_capacity",
			function=Constraint.must_be_greater_than(10),
		)

		constraint_3 = Constraint(
			"Maximum Paygo",
			parameter_names='debt_type',
			outcome_names='99%ile Present Cost',
			function=lambda i, j: max(0, j - 1500) if i == 'Paygo' else 0,
		)

		from emat.optimization import HyperVolume, EpsilonProgress, SolutionViewer, ConvergenceMetrics

		convergence_metrics = ConvergenceMetrics(
			HyperVolume.from_outcomes(robustness_functions),
			EpsilonProgress(),
			SolutionViewer.from_model_and_outcomes(m, robustness_functions),
		)

		numpy.random.seed(8)
		random.seed(8)

		# Test robust optimize
		with SequentialEvaluator(m) as evaluator:
			robust = m.robust_optimize(
					robustness_functions,
					scenarios=scenes,
					nfe=25,
					constraints=[
						constraint_1,
						constraint_2,
						constraint_3,
					],
					epsilons=[0.05,]*len(robustness_functions),
					convergence=convergence_metrics,
					evaluator=evaluator,
			)
		robust_results, convergence = robust.result, robust.convergence

		cachefile = os.path.join(test_dir,'test_robust_results.csv')
		if not os.path.exists(cachefile):
			robust_results.to_csv(cachefile, index=None)
		correct2 = pandas.read_csv(cachefile)
		correct2['debt_type'] = correct2['debt_type'].astype(
			pandas.CategoricalDtype(categories=['GO Bond', 'Rev Bond', 'Paygo'], ordered=True))
		pandas.testing.assert_frame_equal(robust_results, correct2, check_less_precise=True)

