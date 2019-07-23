# -*- coding: utf-8 -*-
""" core_model.py - define coure model API"""
import abc
import yaml
import pandas as pd
import numpy as np
from typing import Union, Mapping
from ema_workbench.em_framework.model import AbstractModel as AbstractWorkbenchModel
from typing import Collection

from ..database.database import Database
from ..scope.scope import Scope
from .._pkg_constants import *

from ..util.loggers import get_module_logger
_logger = get_module_logger(__name__)

class AbstractCoreModel(abc.ABC, AbstractWorkbenchModel):
    """
    An interface for using a model with EMAT.

    Individual models should be instantiated using derived
    subclasses of this abstract base class, and not using
    this class directly.

    Args:
        configuration: The configuration for this
            core model. This can be passed as a dict, or as a str
            which gives the filename of a YAML file that will be
            loaded. If there is no configuration, giving None is
            also acceptable.
        scope (Scope or str): The exploration scope, as a Scope object or as
            a str which gives the filename of a YAML file that will be
            loaded.
        safe: Load the configuration YAML file in 'safe' mode.
            This can be disabled if the configuration requires
            custom Python types or is otherwise not compatible with
            safe mode. Loading configuration files with safe mode
            off is not secure and should not be done with files from
            untrusted sources.
        db: An optional Database to store experiments and results.
        name: A name for this model, given as an alphanumeric string.
            The name is required by ema_workbench operations.
            If not given, "EMAT" is used.
        metamodel_id: An identifier for this model, if it is a meta-model.
            Defaults to 0 (i.e., not a meta-model).
    """

    def __init__(self,
                 configuration:Union[str,Mapping,None],
                 scope:Union[Scope,str],
                 safe:bool=True,
                 db:Database=None,
                 name:str='EMAT',
                 metamodel_id:int=0,
                 ):
        if isinstance(configuration, str):
            with open(configuration, 'r') as stream:
                if safe:
                    configuration = yaml.safe_load(stream)
                else:
                    configuration = yaml.load(stream, Loader=yaml.FullLoader)
            if configuration is None:
                configuration = {}

        self.config = configuration if configuration is not None else {}
        self.db = db
        if isinstance(scope, Scope):
            self.scope = scope
        else:
            self.scope = Scope(scope)

        AbstractWorkbenchModel.__init__(self, name=name.replace('_','').replace(' ',''))
        self.uncertainties = self.scope._x_list
        self.levers = self.scope._l_list
        self.constants = self.scope._c_list
        self.outcomes = self.scope._m_list

        self.metamodel_id = metamodel_id

    def __getstate__(self):
        # don't pickle the db connection
        return dict((k, v) for (k, v) in self.__dict__.items() if (k != 'db'))

    @abc.abstractmethod
    def setup(self, params):
        """
        Configure the core model with the experiment variable values
        
        
        Args:
            params (dict): experiment variables including both exogenous 
                uncertainty and policy levers
                
        Raises:
            KeyError: if experiment variable defined is not supported
                by the core model        
        """     
 
    @abc.abstractmethod
    def get_experiment_archive_path(self, experiment_id: int) -> str:
        """
        Returns path to store model run outputs
        
        Can be useful for long model runs if additional measures will be
        defined at a later time (e.g. link volumes). 
        
        Both the scope name and experiment id can be used to create the 
        folder path. 
        
        Args:
            experiment_id (int):
                experiment id integer (row id of experiment in database)
                
        Returns:
            str: model result path (no trailing backslashes)
        """     
    
    @abc.abstractmethod
    def run(self):
        """
        Initiates the core model run
        
        Model should be 'setup' first
                
        Raises:
            UserWarning: If model is not properly setup
        """     
    
    @abc.abstractmethod
    def post_process(self, params, measure_names, output_path=None):
        """
        Runs post processors associated with measures.

        The model should have previously been prepared using
        the `setup` method.

        Args:
            params (dict):
                Dictionary of experiment variables - indices
                are variable names, values are the experiment settings
            measure_names (List[str]):
                List of measures to be processed
            output_path (str):
                Path to model outputs - if set to none
                will use local values

        Raises:
            KeyError:
                If post process is not available for specified
                measure
        """
    
    @abc.abstractmethod
    def load_measures(
            self,
            measure_names: Collection[str],
            *,
            rel_output_path=None,
            abs_output_path=None,
	) -> dict:
        """
        Import selected measures from the core model.
        
        Imports measures from active scenario
        
        Args:
            measure_names (Collection[str]):
                Collection of measures to be processed
            rel_output_path, abs_output_path (str, optional):
                Path to model output locations, either relative
                to the `model_path` directory (when a subclass
                is a type that has a model path) or as an absolute
                directory.  If neither is given, the default
                value is equivalent to setting `rel_output_path` to
                'Outputs'.

        Returns:
            dict of measure name and values from active scenario
        
        Raises:
            KeyError: If load_measures is not available for specified
                measure
        """           
        

    @abc.abstractmethod
    def archive(self, params, model_results_path, experiment_id:int=0):
        """
        Copies model outputs to archive location
        
        Args:
            params (dict): Dictionary of experiment variables
            model_results_path (str): archive path
            experiment_id (int, optional): The id number for this experiment.
        
        """

    def read_experiments(
            self,
            design_name,
            db=None,
            only_pending=False,
    ):
        """
        Reads results from a design of experiments from the database.

        Args:
            design_name (str): The name of the design to load.
            db (Database, optional): The Database from which to read experiments.
                If no db is given, the default `db` for this model is used.
            only_pending (bool, default False): If True, only pending
                experiments (which have no performance measure results
                stored in the database) are returned.

        Returns:
            pandas.DataFrame:
                A DataFrame that contains all uncertainties, levers, and measures
                for the experiments.

        Raises:
            ValueError:
                If there is no Database connection `db` set.
        """
        db = db if db is not None else self.db
        if db is None:
            raise ValueError('no database to read from')

        return self.ensure_dtypes(
            db.read_experiment_all(self.scope.name, design_name, only_pending=only_pending)
        )

    def read_experiment_parameters(
            self,
            design_name,
            db=None,
            only_pending=False,
    ):
        """
        Reads uncertainties and levers from a design of experiments from the database.

        Args:
            design_name (str): The name of the design to load.
            db (Database, optional): The Database from which to read experiments.
                If no db is given, the default `db` for this model is used.
            only_pending (bool, default False): If True, only pending
                experiments (which have no performance measure results
                stored in the database) are returned.

        Returns:
            pandas.DataFrame:
                A DataFrame that contains all uncertainties, levers, and measures
                for the experiments.

        Raises:
            ValueError:
                If `db` is not given and there is no default
                Database connection set.
        """
        db = db if db is not None else self.db

        if db is None:
            raise ValueError('no database to read from')

        return self.ensure_dtypes(
            db.read_experiment_parameters(self.scope.name, design_name, only_pending=only_pending)
        )

    def read_experiment_measures(
            self,
            design_name,
            experiment_id=None,
            db=None,
    ):
        """
        Reads performace measures from a design of experiments from the database.

        Args:
            design_name (str): The name of the design to load.
            experiment_id (int, optional): The id of the experiment to load.
            db (Database, optional): The Database from which to read experiment(s).
                If no db is given, the default `db` for this model is used.

        Returns:
            pandas.DataFrame:
                A DataFrame that contains all uncertainties, levers, and measures
                for the experiments.

        Raises:
            ValueError:
                If `db` is not given and there is no default
                Database connection set.
        """
        db = db if db is not None else self.db

        if db is None:
            raise ValueError('no database to read from')

        measures =  self.ensure_dtypes(
            db.read_experiment_measures(self.scope.name, design_name, experiment_id)
        )
        
        # only return measures within scope
        measures = measures[[i for i in self.scope.get_measure_names()
                             if i in measures.columns]]
        
        return measures
        

    def ensure_dtypes(self, df:pd.DataFrame):
        """
        Convert columns of dataframe to correct dtype as needed.

        Args:
            df (pandas.DataFrame): A dataframe with column names
                that are uncertainties, levers, or measures.

        Returns:
            pandas.DataFrame:
                The same data as input, but with dtypes as appropriate.
        """
        return self.scope.ensure_dtypes(df)

    def design_experiments(self, *args, **kwargs):
        """
        Create a design of experiments based on this model.

        Args:
            n_samples_per_factor (int, default 10): The number of samples in the
                design per random factor.
            n_samples (int or tuple, optional): The total number of samples in the
                design.  If `jointly` is False, this is the number of samples in each
                of the uncertainties and the levers, the total number of samples will
                be the square of this value.  Give a 2-tuple to set values for
                uncertainties and levers respectively, to set them independently.
                If this argument is given, it overrides `n_samples_per_factor`.
            random_seed (int or None, default 1234): A random seed for reproducibility.
            db (Database, optional): If provided, this design will be stored in the
                database indicated.  If not provided, the `db` for this model will
                be used, if one is set.
            design_name (str, optional): A name for this design, to identify it in the
                database. If not given, a unique name will be generated based on the
                selected sampler.  Has no effect if no `db` is given.
            sampler (str or AbstractSampler, default 'lhs'): The sampler to use for this
                design.  Available pre-defined samplers include:
                    - 'lhs': Latin Hypercube sampling
                    - 'ulhs': Uniform Latin Hypercube sampling, which ignores defined
                        distribution shapes from the scope and samples everything
                        as if it was from a uniform distribution
                    - 'mc': Monte carlo sampling
                    - 'uni': Univariate sensitivity testing, whereby experiments are
                        generated setting each parameter individually to minimum and
                        maximum values (for numeric dtypes) or all possible values
                        (for boolean and categorical dtypes).  Note that designs for
                        univariate sensitivity testing are deterministic and the number
                        of samples given is ignored.
            sample_from ('all', 'uncertainties', or 'levers'): Which scope components
                from which to sample.  Components not sampled are set at their default
                values in the design.
            jointly (bool, default True): Whether to sample jointly all uncertainties
                and levers in a single design, or, if False, to generate separate samples
                for levers and uncertainties, and then combine the two in a full-factorial
                manner.  This argument has no effect unless `sample_from` is 'all'.
                Note that jointly may produce a very large design;

        Returns:
            pandas.DataFrame: The resulting design.
        """
        if 'scope' in kwargs:
            kwargs.pop('scope')

        if 'db' not in kwargs:
            kwargs['db'] = self.db

        from ..experiment import experimental_design
        return experimental_design.design_experiments(self.scope, *args, **kwargs)

    def run_experiments(
            self,
            design:pd.DataFrame=None,
            evaluator=None,
            *,
            design_name=None,
            db=None,
    ):
        """
        Runs a design of combined experiments using this model.

        A combined experiment includes a complete set of input values for
        all exogenous uncertainties (a Scenario) and all policy levers
        (a Policy). Unlike the perform_experiments function in the EMA Workbench,
        this method pairs each Scenario and Policy in sequence, instead
        of running all possible combinations of Scenario and Policy.
        This change ensures compatibility with the EMAT database modules, which
        preserve the complete set of input information (both uncertainties
        and levers) for each experiment.  To conduct a full cross-factorial set
        of experiments similar to the default settings for EMA Workbench,
        use a factorial design, by setting the `jointly` argument for the
        `design_experiments` to False, or by designing experiments outside
        of EMAT with your own approach.

        Args:
            design (pandas.DataFrame, optional): experiment definitions
                given as a DataFrame, where each exogenous uncertainties and
                policy levers is given as a column, and each row is an experiment.
            evaluator (ema_workbench.Evaluator, optional): Optionally give an
                evaluator instance.  If not given, a default SequentialEvaluator
                will be instantiated.
            design_name (str, optional): The name of a design of experiments to
                load from the database.  This design is only used if
                `design` is None.
            db (Database, optional): The database to use for loading and saving experiments.
                If none is given, the default database for this model is used.
                If there is no default db, and none is given here,
                the results are not stored in a database. Set to False to explicitly
                not use the default database, even if it exists.

        Returns:
            pandas.DataFrame:
                A DataFrame that contains all uncertainties, levers, and measures
                for the experiments.

        Raises:
            ValueError:
                If there are no experiments defined.  This includes
                the situation where `design` is given but no database is
                available.

        """

        from ema_workbench import Scenario, Policy, perform_experiments

        # catch user gives only a design, not experiment_parameters
        if isinstance(design, str) and design_name is None:
            design_name, design = design, None

        if design_name is None and design is None:
            raise ValueError(f"must give design_name or design")

        if db is None:
            db = self.db

        if design_name is not None and design is None:
            if not db:
                raise ValueError(f'cannot load design "{design_name}", there is no db')
            design = db.read_experiment_parameters(self.scope.name, design_name)

        if design.empty:
            raise ValueError(f"no experiments available")

        scenarios = [
            Scenario(**dict(zip(self.scope.get_uncertainty_names(), i)))
            for i in design[self.scope.get_uncertainty_names()].itertuples(index=False,
                                                                           name='ExperimentX')
        ]

        policies = [
            Policy(f"Incognito{n}", **dict(zip(self.scope.get_lever_names(), i)))
            for n,i in enumerate(design[self.scope.get_lever_names()].itertuples(index=False,
                                                                                 name='ExperimentL'))
        ]

        if not evaluator:
            from ema_workbench import SequentialEvaluator
            evaluator = SequentialEvaluator(self)

        experiments, outcomes = perform_experiments(self, scenarios=scenarios, policies=policies,
                                                    zip_over={'scenarios', 'policies'}, evaluator=evaluator)
        experiments.index = design.index



        outcomes = pd.DataFrame.from_dict(outcomes)
        outcomes.index = design.index

        if db:
            db.write_experiment_measures(self.scope.name, self.metamodel_id, outcomes)

        return self.ensure_dtypes(pd.concat([
            experiments.drop(columns=['scenario','policy','model']),
            outcomes
        ], axis=1, sort=False))



    def create_metamodel_from_data(
            self,
            experiment_inputs:pd.DataFrame,
            experiment_outputs:pd.DataFrame,
            output_transforms: dict = None,
            metamodel_id:int = None,
            include_measures = None,
            exclude_measures = None,
            db = None,
            random_state = None,
    ):
        """
        Create a MetaModel from a set of input and output observations.

        Args:
            experiment_inputs (pandas.DataFrame): This dataframe
                should contain all of the experimental inputs, including
                values for each uncertainty, level, and constant.
            experiment_outputs (pandas.DataFrame): This dataframe
                should contain all of the experimental outputs, including
                a column for each performance measure. The index
                for the outputs should match the index for the
                `experiment_inputs`, so that the I-O matches row-by-row.
            output_transforms (dict): A mapping of performance measure
                transforms to use in meta-model estimation and application.
            metamodel_id (int, optional): An identifier for this meta-model.
                If not given, a unique id number will be created randomly.
            include_measures (Collection[str], optional): If provided, only
                output performance measures with names in this set will be included.
            exclude_measures (Collection[str], optional): If provided, only
                output performance measures with names not in this set will be included.
            db (Database, optional): The database to use for loading and saving metamodels.
                If none is given, the default database for this model is used.
                If there is no default db, and none is given here,
                the metamodel is not stored in a database.
            random_state (int, optional): A random state to use in the metamodel
                regression fitting.

        Returns:
            MetaModel:
                a callable object that, when called as if a
                function, accepts keyword arguments as inputs and
                returns a dictionary of (measure name: value) pairs.
        """
        from .core_python import PythonCoreModel
        from .meta_model import MetaModel

        db = db if db is not None else self.db

        experiment_inputs = self.ensure_dtypes(experiment_inputs)

        if metamodel_id is None:
            if db is not None:
                scope_name = self.scope.name
                metamodel_id = db.get_new_metamodel_id(scope_name)
            else:
                metamodel_id = np.random.randint(1,2**63,dtype='int64')

        if include_measures is not None:
            experiment_outputs = experiment_outputs[[i for i in include_measures
                                                     if i in experiment_outputs.columns]]
            output_transforms = {i: output_transforms[i] for i in include_measures}
            
        if exclude_measures is not None:
            experiment_outputs = experiment_outputs.drop(exclude_measures, axis=1)
            for i in exclude_measures:
                del output_transforms[i]

        disabled_outputs = [i for i in self.scope.get_measure_names()
                            if i not in experiment_outputs.columns]

        func = MetaModel(experiment_inputs, experiment_outputs,
                         output_transforms, disabled_outputs, random_state)

        scope_ = self.scope.duplicate(strip_measure_transforms=True, 
                                      include_measures=include_measures,
                                      exclude_measures=exclude_measures)

        return PythonCoreModel(
            func,
            configuration = None,
            scope=scope_,
            safe=True,
            db = db,
            name=self.name+"Meta",
            metamodel_id=metamodel_id,
        )

    def create_metamodel_from_design(
            self,
            design_name:str,
            metamodel_id:int = None,
            include_measures=None,
            exclude_measures=None,
            db=None,
            random_state=None,
    ):
        """
        Create a MetaModel from a set of input and output observations.

        Args:
            design_name (str): The name of the design to use.
            metamodel_id (int, optional): An identifier for this meta-model.
                If not given, a unique id number will be created randomly.
            include_measures (Collection[str], optional): If provided, only
                output performance measures with names in this set will be included.
            exclude_measures (Collection[str], optional): If provided, only
                output performance measures with names not in this set will be included.
            random_state (int, optional): A random state to use in the metamodel
                regression fitting.

        Returns:
            MetaModel:
                a callable object that, when called as if a
                function, accepts keyword arguments as inputs and
                returns a dictionary of (measure name: value) pairs.

        Raises:
            ValueError: If the named design still has pending experiments.
        """
        db = db if db is not None else self.db

        if db is not None:
            check_df = db.read_experiment_parameters(self.scope.name, design_name, only_pending=True)
            if not check_df.empty:
                from ..exceptions import PendingExperimentsError
                raise PendingExperimentsError(f'design "{design_name}" has pending experiments')

        experiment_inputs = db.read_experiment_parameters(self.scope.name, design_name)
        experiment_outputs = db.read_experiment_measures(self.scope.name, design_name)

        transforms = {
            i.name: i.metamodeltype
            for i in self.scope.get_measures()
        }

        return self.create_metamodel_from_data(
            experiment_inputs,
            experiment_outputs,
            transforms,
            metamodel_id=metamodel_id,
            include_measures=include_measures,
            exclude_measures=exclude_measures,
            db=db,
            random_state=random_state,
        )

    def create_metamodel_from_designs(
            self,
            design_names:str,
            metamodel_id:int = None,
            include_measures=None,
            exclude_measures=None,
            db=None,
            random_state=None,
    ):
        """
        Create a MetaModel from multiple sets of input and output observations.

        Args:
            design_names (Collection[str]): The names of the designs to use.
            metamodel_id (int, optional): An identifier for this meta-model.
                If not given, a unique id number will be created randomly.
            include_measures (Collection[str], optional): If provided, only
                output performance measures with names in this set will be included.
            exclude_measures (Collection[str], optional): If provided, only
                output performance measures with names not in this set will be included.
            random_state (int, optional): A random state to use in the metamodel
                regression fitting.

        Returns:
            MetaModel:
                a callable object that, when called as if a
                function, accepts keyword arguments as inputs and
                returns a dictionary of (measure name: value) pairs.

        Raises:
            ValueError: If the named design still has pending experiments.
        """
        db = db if db is not None else self.db

        if db is not None:
            for design_name in design_names:
                check_df = db.read_experiment_parameters(self.scope.name, design_name, only_pending=True)
                if not check_df.empty:
                    from ..exceptions import PendingExperimentsError
                    raise PendingExperimentsError(f'design "{design_name}" has pending experiments')

        experiment_inputs = pd.concat([
            db.read_experiment_parameters(self.scope.name, design_name) for design_name in design_names
        ])
        experiment_outputs = pd.concat([
            db.read_experiment_measures(self.scope.name, design_name) for design_name in design_names
        ])

        transforms = {
            i.name: i.metamodeltype
            for i in self.scope.get_measures()
        }

        return self.create_metamodel_from_data(
            experiment_inputs,
            experiment_outputs,
            transforms,
            metamodel_id=metamodel_id,
            include_measures=include_measures,
            exclude_measures=exclude_measures,
            db=db,
            random_state=random_state,
        )


    def get_feature_scores(
            self,
            design,
            return_raw=False,
            random_state=None,
    ):
        """
        Calculate feature scores based on a design of experiments.

        Args:
            design (str or pandas.DataFrame): The name of the design of experiments
                to use for feature scoring, or a pandas.DataFrame containing the
                experimental design and results.
            return_raw (bool, default False): Whether to return a raw pandas.DataFrame
                containing the computed feature scores, instead of a formatted heatmap
                table.

        Returns:
            xmle.Elem or pandas.DataFrame:
                Returns a rendered SVG as xml, or a DataFrame,
                depending on the `return_raw` argument.

        This function internally uses feature_scoring from the EMA Workbench, which in turn
        scores features using the "extra trees" regression approach.
        """
        from ema_workbench.analysis import feature_scoring
        from ..viz import heatmap_table
        import pandas

        if isinstance(design, str):
            inputs = self.read_experiment_parameters(design)
            outcomes = self.read_experiment_measures(design)
        elif isinstance(design, pandas.DataFrame):
            inputs = design[[c for c in design.columns if c in self.scope.get_parameter_names()]]
            outcomes = design[[c for c in design.columns if c in self.scope.get_measure_names()]]
        else:
            raise TypeError('must name design or give DataFrame')

        fs = feature_scoring.get_feature_scores_all(inputs, outcomes, random_state=random_state)
        if return_raw:
            return fs
        return heatmap_table(
            fs.T,
            xlabel='Model Parameters', ylabel='Performance Measures',
            title='Feature Scoring' + (f' [{design}]' if design else ''),
        )

    def robust_optimize(
            self,
            robustness_functions,
            scenarios,
            evaluator=None,
            nfe=10000,
            convergence=None,
            constraints=None,
            **kwargs,
    ):
        """
        Perform robust optimization.

        The robust optimization generally a multi-objective optimization task.
        It is undertaken using statistical measures of outcomes evaluated across
        a number of scenarios, instead of using the individual outcomes themselves.
        For each candidate policy, the model is evaluated against all of the considered
        scenarios, and then the robustness measures are evaluated using the
        set of outcomes from the original runs.  The robustness measures
        are aggregate measures that are computed from a set of outcomes.
        For example, this may be expected value, median, n-th percentile,
        minimum, or maximum value of any individual outcome.  It is also
        possible to have joint measures, e.g. expected value of the larger
        of outcome 1 or outcome 2.

        Each robustness function is indicated as a maximization or minimization
        target, where higher or lower values are better, respectively.
        The optimization process then tries to identify one or more
        non-dominated solutions for the possible policy levers.

        Args:
            robustness_functions (Collection[Measure]): A collection of
                aggregate statistical performance measures.
            scenarios (int or Collection): A collection of scenarios to
                use in the evaluation(s), or give an integer to generate
                that number of random scenarios.
            evaluator (Evaluator, optional): The evaluator to use to
                run the model. If not given, a SequentialEvaluator will
                be created.
            algorithm (platypus.Algorithm, optional): Select an
                algorithm for multi-objective optimization.  See
                `platypus` documentation for details.
            nfe (int, default 10_000): Number of function evaluations.
                This generally needs to be fairly large to achieve stable
                results in all but the most trivial applications.
            convergence (emat.optimization.ConvergenceMetrics, optional)
            constraints (Collection[Constraint], optional)
            kwargs: any additional arguments will be passed on to the
                platypus algorithm.

        Returns:
            pandas.DataFrame: The set of non-dominated solutions found.

            When `convergence` is given, the convergence measures are
            also returned, as a second pandas.DataFrame.
        """


        if evaluator is None:
            from ema_workbench.em_framework import SequentialEvaluator
            evaluator = SequentialEvaluator(self)

        from ema_workbench.em_framework.samplers import sample_uncertainties, sample_levers

        if isinstance(scenarios, int):
            n_scenarios = scenarios
            scenarios = sample_uncertainties(self, n_scenarios)

        # if epsilons is None:
        #     epsilons = [0.05, ] * len(robustness_functions)
        #
        with evaluator:
            robust_results = evaluator.robust_optimize(
                robustness_functions,
                scenarios,
                nfe=nfe,
                constraints=constraints,
                # epsilons=epsilons,
                convergence=convergence,
                **kwargs,
            )

        if isinstance(robust_results, tuple) and len(robust_results) == 2:
            robust_results, result_convergence = robust_results
        else:
            result_convergence = None

        robust_results = self.ensure_dtypes(robust_results)

        if result_convergence is None:
            return robust_results
        else:
            return robust_results, result_convergence

    def robust_evaluate(
            self,
            robustness_functions,
            scenarios,
            policies,
            evaluator=None,
    ):
        """
        Perform robust evaluation(s).

        The robust evaluation is used to generate statistical measures
        of outcomes, instead of generating the individual outcomes themselves.
        For each policy, the model is evaluated against all of the considered
        scenarios, and then the robustness measures are evaluated using the
        set of outcomes from the original runs.  The robustness measures
        are aggregate measures that are computed from a set of outcomes.
        For example, this may be expected value, median, n-th percentile,
        minimum, or maximum value of any individual outcome.  It is also
        possible to have joint measures, e.g. expected value of the larger
        of outcome 1 or outcome 2.

        Args:
            robustness_functions (Collection[Measure]): A collection of
                aggregate statistical performance measures.
            scenarios (int or Collection): A collection of scenarios to
                use in the evaluation(s), or give an integer to generate
                that number of random scenarios.
            policies (int, or collection): A collection of policies to
                use in the evaluation(s), or give an integer to generate
                that number of random policies.
            evaluator (Evaluator, optional): The evaluator to use to
                run the model. If not given, a SequentialEvaluator will
                be created.

        Returns:
            pandas.DataFrame: The computed value of each item
            in `robustness_functions`, for each policy in `policies`.
        """

        if evaluator is None:
            from ema_workbench.em_framework import SequentialEvaluator
            evaluator = SequentialEvaluator(self)

        from ema_workbench.em_framework.samplers import sample_uncertainties, sample_levers

        if isinstance(scenarios, int):
            n_scenarios = scenarios
            scenarios = sample_uncertainties(self, n_scenarios)

        with evaluator:
            robust_results = evaluator.robust_evaluate(
                robustness_functions,
                scenarios,
                policies,
            )

        robust_results = self.ensure_dtypes(robust_results)
        return robust_results
