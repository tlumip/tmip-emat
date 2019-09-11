
from ..database.database import Database
from .scatter import scatter_graph_row, ScatterMass
from ..util import xmle
from plotly.colors import DEFAULT_PLOTLY_COLORS
import itertools

def scatter_graphs(
		column,
		data,
		scope,
		db=None,
		contrast='infer',
		marker_opacity=None,
		render=None,
		use_gl=True,
):
	"""Generate a row of scatter plots comparing one column against others.

	Args:
		column (str): The name of the principal parameter or measure to analyze.
		data (pandas.DataFrame or str): The experimental results to plot. Can be given
			as a DataFrame or as the name of a design (in which case the results are
			loaded from the provided Database `db`).
		scope (Scope, optional): The exploratory scope.
		db (Database, optional): The database containing the results.  Ignore unless
			`data` is a string.
		contrast (str or list): The contrast columns to plot the principal parameter or
			measure against.  Can be given as a list of columns that appear in the
			data, or one of {'uncertainties', 'levers', 'parameters', 'measures', 'infer'}.
			If set to 'infer', the contrast will be 'measures' if `column` is a parameter,
			and 'parameters' if `columns` is a measure.
		marker_opacity (float, optional): The opacity to use for markers.  If the number
			of markers is large, the figure may appear as a solid blob; by setting opacity
			to less than 1.0, the figure can more readily show relative density in various
			regions.  If not specified, marker_opacity is set to 100/len(data), bounded by
			0.01 and 1.0.
		render (str or dict, optional): If given, the graph[s] will be rendered to a
			static image using `plotly.io.to_image`.  For default settings, pass
			'png', or give a dictionary that specifies keyword arguments to that function.

	Returns:
		FigureWidget or xmle.Elem

	Raises:
		ValueError: If `contrast` is 'infer' but `column` is neither a parameter
			nor a measure.
	"""

	if contrast == 'infer':
		if column in scope.get_uncertainty_names():
			contrast = 'measures'
		elif column in scope.get_lever_names():
			contrast = 'measures'
		elif column in scope.get_measure_names():
			contrast = 'parameters'
		else:
			raise ValueError('cannot infer what to contrast against')

	if contrast == 'uncertainties':
		contrast = scope.get_uncertainty_names()
	elif contrast == 'levers':
		contrast = scope.get_lever_names()
	elif contrast == 'parameters':
		contrast = scope.get_uncertainty_names() + scope.get_lever_names()
	elif contrast == 'measures':
		contrast = scope.get_measure_names()

	if isinstance(data, str):
		if db is None:
			raise ValueError('db cannot be None if data is a design name')
		data = db.read_experiment_all(data)

	if marker_opacity is None:
		if len(data) > 10000:
			marker_opacity = 0.01
		elif len(data) > 100:
			marker_opacity = 100/len(data)
		else:
			marker_opacity = 1.0

	y_title = column
	try:
		y_title = scope[column].shortname
	except AttributeError:
		pass

	fig = scatter_graph_row(
		[c for c in contrast if c in data.columns],
		column,
		df = data,
		marker_opacity=marker_opacity,
		y_title=y_title,
		layout=dict(
			margin=dict(l=50, r=2, t=5, b=40)
		),
		short_name_func=scope.shortname if scope is not None else None,
		use_gl=use_gl,
	)

	if render:
		if render == 'png':
			render = dict(format='png', width=1400, height=270, scale=2)

		import plotly.io as pio
		img_bytes = pio.to_image(fig, **render)
		return xmle.Elem.from_any(img_bytes)

	return fig


def scatter_graphs_2(
		column,
		datas,
		scope,
		db=None,
		contrast='infer',
		render=None,
		colors=None,
		use_gl=True,
):
	"""Generate a row of scatter plots comparing one column against others.

	Args:
		column (str): The name of the principal parameter or measure to analyze.
		datas (Collection[pandas.DataFrame or str]): The experimental results to plot. Can be given
			as a DataFrame or as the name of a design (in which case the results are
			loaded from the provided Database `db`).
		scope (Scope, optional): The exploratory scope.
		db (Database, optional): The database containing the results.  Ignore unless
			`data` is a string.
		contrast (str or list): The contrast columns to plot the principal parameter or
			measure against.  Can be given as a list of columns that appear in the
			data, or one of {'uncertainties', 'levers', 'parameters', 'measures', 'infer'}.
			If set to 'infer', the contrast will be 'measures' if `column` is a parameter,
			and 'parameters' if `columns` is a measure.
		render (str or dict, optional): If given, the graph[s] will be rendered to a
			static image using `plotly.io.to_image`.  For default settings, pass
			'png', or give a dictionary that specifies keyword arguments to that function.

	Returns:
		FigureWidget or xmle.Elem

	Raises:
		ValueError: If `contrast` is 'infer' but `column` is neither a parameter
			nor a measure.
	"""

	if contrast == 'infer':
		if column in scope.get_uncertainty_names():
			contrast = 'measures'
		elif column in scope.get_lever_names():
			contrast = 'measures'
		elif column in scope.get_measure_names():
			contrast = 'parameters'
		else:
			raise ValueError('cannot infer what to contrast against')

	if contrast == 'uncertainties':
		contrast = scope.get_uncertainty_names()
	elif contrast == 'levers':
		contrast = scope.get_lever_names()
	elif contrast == 'parameters':
		contrast = scope.get_uncertainty_names() + scope.get_lever_names()
	elif contrast == 'measures':
		contrast = scope.get_measure_names()

	data_ = []
	marker_opacity_ = []
	fig = 'widget'
	if colors is None:
		colorcycle = itertools.cycle(DEFAULT_PLOTLY_COLORS)
	else:
		colorcycle = itertools.cycle(colors)

	for data in datas:
		if isinstance(data, str):
			if db is None:
				raise ValueError('db cannot be None if data is a design name')
			data = db.read_experiment_all(data)
		data_.append(data)

	for data in data_:
		marker_opacity = 1.0
		if len(data) > 1000:
			marker_opacity = 1000 / len(data)
		if marker_opacity < 0.1:
			marker_opacity = 0.1
		marker_opacity_.append(marker_opacity)

		y_title = column
		try:
			y_title = scope[column].shortname
		except AttributeError:
			pass

		fig = scatter_graph_row(
			[(c if c in data.columns else None) for c in contrast],
			column,
			df = data,
			marker_opacity=marker_opacity,
			y_title=y_title,
			layout=dict(
				margin=dict(l=50, r=2, t=5, b=40)
			),
			output=fig,
			C=colorcycle.__next__(),
			short_name_func=scope.shortname if scope is not None else None,
			use_gl=use_gl,
		)

	if render:
		if render == 'png':
			render = dict(format='png', width=1400, height=270, scale=2)

		import plotly.io as pio
		img_bytes = pio.to_image(fig, **render)
		return xmle.Elem.from_any(img_bytes)

	return fig


def heatmap_table(
		data, cmap='viridis', fmt='.3f', linewidths=0.7, figsize=(12,3),
		xlabel=None, ylabel=None, title=None,
		attach_metadata=True,
		**kwargs
):
	"""Generate a SVG heatmap from data.

	Args:
		data (pandas.DataFrame): source data for the heatmap table.
		cmap (str): A colormap for the resulting heatmap.
		fmt (str): how to format values
		linewidths (float): Line widths for the table.
		figsize (tuple): The size of the resulting figure.
		xlabel, ylabel, title (str, optional): Captions for each.
		attach_metadata (bool, default True): Attach `data` to the
			resulting figure as metadata.

	Returns:
		xmle.Elem: The xml data for a svg rendering.
	"""
	import seaborn as sns
	from matplotlib import pyplot as plt
	fig, ax = plt.subplots(figsize=figsize)
	axes = sns.heatmap(data, ax=ax, cmap=cmap, annot=True, fmt=fmt, linewidths=linewidths, **kwargs)
	if xlabel:
		ax.set_xlabel(xlabel, fontweight='bold')
	if ylabel is not None:
		ax.set_ylabel(ylabel, fontweight='bold')
	if title is not None:
		ax.set_title(title, fontweight='bold')
	result= xmle.Elem.from_figure(axes.get_figure())
	if attach_metadata:
		result.metadata = data
	return result
