
import pandas
from typing import Sequence
from sklearn.base import RegressorMixin, BaseEstimator, clone
from sklearn.model_selection import cross_val_predict
from .frameable import FrameableMixin
from .model_selection import CrossValMixin
from .multioutput import MultiOutputRegressor
from sklearn.utils.metaestimators import _BaseComposition
from sklearn.utils import Bunch

class BoostedRegressor(_BaseComposition, RegressorMixin, FrameableMixin, CrossValMixin):
	"""
	A stack of regressors.

	Each regressor is fit sequentially, and the remaining residual
	is the target of the next model in the chain.
	"""
	_required_parameters = ['estimators']

	def __init__(
			self,
			estimators,
			use_cv_predict=False,
			prediction_tier=9999,
	):
		super().__init__()
		self.estimators = estimators
		self.use_cv_predict = use_cv_predict
		self.prediction_tier = prediction_tier

	@property
	def named_estimators(self):
		return Bunch(**dict(self.estimators))

	def set_params(self, **params):
		"""
		Setting the parameters for the boosted estimator

		Valid parameter keys can be listed with get_params().

		Parameters
		----------
		**params : keyword arguments
			Specific parameters using e.g. set_params(parameter_name=new_value)
			In addition, to setting the parameters of the boosted estimator,
			the individual estimators of the boosted estimator can also be
			set or replaced by setting them to None.

		"""
		return self._set_params('estimators', **params)

	def get_params(self, deep=True):
		"""
		Get the parameters of the boosted estimator

		Parameters
		----------
		deep : bool
			Setting it to True gets the various estimators and the parameters
			of the estimators as well
		"""
		return self._get_params('estimators', deep=deep)

	@property
	def estimator_names(self):
		return [i[0] for i in self.estimators]

	def __getattr__(self, attr_name):
		# if attr_name in self.named_estimators:
		# 	return self.named_estimators[attr_name]
		# raise AttributeError(attr_name)
		position = None
		for n, name in enumerate(self.estimator_names):
			if name == attr_name:
				position = n
				break
		if position is None:
			raise AttributeError(attr_name)
		if hasattr(self, 'estimators_'):
			return self.estimators_[position]
		else:
			return self.estimators[position]

	def _use_cv_predict_n(self, n):
		if isinstance(self.use_cv_predict, Sequence):
			return self.use_cv_predict[n]
		return self.use_cv_predict

	def fit(self, X, Y, sample_weight=None):

		if sample_weight is not None:
			raise NotImplementedError
		self._pre_fit(X, Y)
		self.estimators_ = []
		Y_ = Y
		for n,(_,e) in enumerate(self.estimators):
			e_ = clone(e)
			e_.fit(X, Y_)
			self.estimators_.append(e_)
			if n+1 < len(self.estimators):
				if self._use_cv_predict_n(n):
					Y_ = Y_ - self._post_predict(X,cross_val_predict(e_,X))
				else:
					Y_ = Y_ - self._post_predict(X,e_.predict(X))
		return self

	def _set_prediction_tier(self, tier):
		tier_ = tier
		if tier is not None:
			import numbers
			if not isinstance(tier, numbers.Integral):
				raise ValueError('tier must be integer')
			if tier == 0:
				tier = 9999
			if tier < 0:
				tier = len(self.estimators) + tier
			if tier <= 0:
				raise IndexError(f'invalid tier {tier_}')
			self.prediction_tier = tier

	def predict(self, X, tier=None):
		"""
		Generate predictions from a set of exogenous data.

		Parameters
		----------
		X : array-like, prefer pandas.DataFrame
			Exogenous data.
		tier : int, optional
			Limit the prediction to using only the first `tier`
			levels of stacking. For example, setting to 1 results
			in only using the very first level of the stack.  If not
			given, the existing value of `prediction_tier` is used.

		"""
		if tier is None:
			tier = self.prediction_tier
		Yhat = self.estimators_[0].predict(X)
		for n_, e_ in enumerate(self.estimators_[1:]):
			if n_+1 < tier:
				Yhat += e_.predict(X)
		Yhat = self._post_predict(X, Yhat)
		return Yhat

	def cross_val_scores(self, X, Y, cv=5, S=None, random_state=None, n_repeats=None, tier=None, n_jobs=-1):
		"""
		Calculate the cross validation scores for this model.

		Unlike other scikit-learn scores, this method returns
		a separate score value for each output when the estimator
		is for a multi-output process.

		If the estimator includes a `sample_stratification`
		attribute, it is used along with

		Args:
			X, Y : array-like
				The independent and dependent data to use for
				cross-validation.
			cv : int, default 5
				The number of folds to use in cross-validation.
			S : array-like
				The stratification data to use for stratified
				cross-validation.  This data must be categorical
				(or convertible into such), and should be a
				vector of length equal to the first dimension
				(i.e. number of observations) in the `X` and `Y`
				arrays.
			n_repeats : int, optional
				Repeat the cross validation exercise this many
				times, with different random seeds, and return
				the average result.

		Returns:
			pandas.Series: The cross-validation scores, by output.

		"""
		self._set_prediction_tier(tier)
		p = self._cross_validate(
			X, Y, cv=cv, S=S, random_state=random_state,
			cache_metadata=self.prediction_tier, n_repeats=n_repeats,
			n_jobs=n_jobs,
		)
		try:
			return pandas.Series({j: p[f"test_{j}"].mean() for j in self.Y_columns})
		except:
			print("p=", p)
			print(len(self.Y_columns))
			print("self.Y_columns=", self.Y_columns)
			raise


def LinearAndGaussian(
		fit_intercept=True,
		n_jobs=None,
		stats_on_fit=True,
		kernel_generator=None,
		alpha=1e-10,
		optimizer="fmin_l_bfgs_b",
		n_restarts_optimizer=250,
		normalize_y=False,
		standardize_before_fit=True,
		copy_X_train=True,
		random_state=None,
		use_cv_predict=False,
		single_target=False
):
	from .linear_model import LinearRegression
	from .anisotropic import AnisotropicGaussianProcessRegressor

	if single_target:
		regressor2 = lambda x: x
	else:
		regressor2 = lambda x: MultiOutputRegressor(x)

	return BoostedRegressor(
		[
			(
				'lr',
				LinearRegression(
					fit_intercept=fit_intercept,
					copy_X=True,
					n_jobs=n_jobs,
					stats_on_fit=stats_on_fit,
				)
			),
			(
				'gpr',
				regressor2(AnisotropicGaussianProcessRegressor(
					kernel_generator=kernel_generator,
					alpha=alpha,
					optimizer=optimizer,
					n_restarts_optimizer=n_restarts_optimizer,
					normalize_y=normalize_y,
					standardize_before_fit=standardize_before_fit,
					copy_X_train=copy_X_train,
					random_state=random_state,
				))
			),
		],
		use_cv_predict=use_cv_predict,
	)


def LinearInteractAndGaussian(
		k=None,
		degree=2,
		fit_intercept=True,
		n_jobs=None,
		stats_on_fit=True,
		kernel_generator=None,
		alpha=1e-10,
		optimizer="fmin_l_bfgs_b",
		n_restarts_optimizer=250,
		normalize_y=False,
		standardize_before_fit=True,
		copy_X_train=True,
		random_state=None,
		use_cv_predict=False,
		single_target=False
):
	from .linear_model import LinearRegression_KBestPoly
	from .anisotropic import AnisotropicGaussianProcessRegressor
	if single_target:
		regressor2 = lambda x: x
	else:
		regressor2 = lambda x: MultiOutputRegressor(x)
	return regressor2(BoostedRegressor(
		[
			(
				'lr',
				LinearRegression_KBestPoly(
					k=k,
					degree=degree,
					fit_intercept=fit_intercept,
					copy_X=True,
					n_jobs=n_jobs,
					stats_on_fit=stats_on_fit,
					single_target=True,
				)
			),
			(
				'gpr',
				AnisotropicGaussianProcessRegressor(
					kernel_generator=kernel_generator,
					alpha=alpha,
					optimizer=optimizer,
					n_restarts_optimizer=n_restarts_optimizer,
					normalize_y=normalize_y,
					standardize_before_fit=standardize_before_fit,
					copy_X_train=copy_X_train,
					random_state=random_state,
				)
			),
		],
		use_cv_predict=use_cv_predict,
	))


def LinearInteractRangeAndGaussian(
		k_max=5,
		degree=2,
		fit_intercept=True,
		n_jobs=None,
		stats_on_fit=True,
		kernel_generator=None,
		alpha=1e-10,
		optimizer="fmin_l_bfgs_b",
		n_restarts_optimizer=250,
		normalize_y=False,
		standardize_before_fit=True,
		copy_X_train=True,
		random_state=None,
		use_cv_predict=False,
		single_target=False
):
	from .linear_model import LinearRegression_KRangeBestPoly
	from .anisotropic import AnisotropicGaussianProcessRegressor
	if single_target:
		regressor2 = lambda x: x
	else:
		regressor2 = lambda x: MultiOutputRegressor(x)
	return BoostedRegressor(
		[
			(
				'lr',
				LinearRegression_KRangeBestPoly(
					k_max=k_max,
					degree=degree,
					fit_intercept=fit_intercept,
					copy_X=True,
					n_jobs=n_jobs,
					stats_on_fit=stats_on_fit,
				),
			),
			(
				'gpr',
				regressor2(AnisotropicGaussianProcessRegressor(
					kernel_generator=kernel_generator,
					alpha=alpha,
					optimizer=optimizer,
					n_restarts_optimizer=n_restarts_optimizer,
					normalize_y=normalize_y,
					standardize_before_fit=standardize_before_fit,
					copy_X_train=copy_X_train,
					random_state=random_state,
				)),
			),
		],
		use_cv_predict=use_cv_predict,
	)


def LinearPossibleInteractAndGaussian(
		cv=5,
		n_jobs=-1,
		**kwargs,
):

	from .multioutput import MultiOutputRegressor
	from sklearn.model_selection import GridSearchCV

	return MultiOutputRegressor(
		GridSearchCV(
			LinearInteractAndGaussian(single_target=True,**kwargs),
			cv=cv,
			param_grid={'lr__KBestPoly__k': [0,None]},
			iid=False,
		),
		n_jobs=n_jobs,
	)

