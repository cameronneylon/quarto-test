# Reporting template
#
# Copyright 2020-21 ######
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Authors: COKI Team
import json
import os

import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from git import Repo

from observatory.reports import provndoc_utils
from precipy.analytics_function import AnalyticsFunction
from parameters import *
from report_data_processing.sql import *


# Insert applicable graphs once created
# from report_graphs import (
#     Alluvial, OverallCoverage, BarLine, ValueAddBar, ValueAddByCrossrefType, ValueAddByCrossrefTypeHorizontal,
#     PlotlyTable
# )

# Replace with applicable project name

def process_sql_templates_to_queries(af: AnalyticsFunction,
                                     rerun: bool = RERUN):
    provndoc_utils.process_sql_to_queries(af,
                                          SQL_TEMPLATE_PARAMETERS,
                                          rerun,
                                          SQL_TEMPLATES_DIRECTORY,
                                          SQL_PROCESSED_DIRECTORY)


def provenance_n_documentation(af: AnalyticsFunction,
                               rerun: bool = RERUN):
    dag = provndoc_utils.build_sql_dag(SQL_PROCESSED_DIRECTORY)
    dag.to_pickle(DAG_FILEPATH)


def run_all_queries(af: AnalyticsFunction,
                    rerun: bool = RERUN,
                    verbose: bool = VERBOSE):
    sql_files = sorted(Path(SQL_PROCESSED_DIRECTORY).glob('*.sql'))
    provdag = provndoc_utils.dag_from_pickle(DAG_FILEPATH)
    sorted_nodes = ['_'.join(nodename.split('_')[1:]) for nodename in provdag.topologicalSort()]
    filelist = [Path(node) for node in sorted_nodes if node in [str(f) for f in sql_files]]

    for sql_file in filelist:
        query = load_sql_to_string(sql_file)
        if not report_utils.bigquery_rerun(sql_file.name, rerun, verbose):
            print(query)
            continue
        edges = provdag.edges_by_from_node(f'file_{sql_file}')
        assert len(edges) == 1
        edge = edges[0]
        if edge.to_node.startswith('table_'):
            run_query_to_bq_table(query=query,
                                  query_name=sql_file.name,
                                  destination_table=DESTINATION_TABLES.get(sql_file.name),
                                  rerun=rerun,
                                  verbose=verbose
                                  )

        elif edge.to_node.startswith('file_'):
            df = pd.read_gbq(query,
                             project_id=PROJECT_ID)
            df.to_csv(DATA_FOLDER / f'{sql_file.stem}.csv')


def report_numbers(af: AnalyticsFunction,
                   quarto: bool=False):
    """
    Generate the numbers for insertion into the report

    ## Requires
    file oa_global_trend.csv
    file oa_country_trend.csv
    file zero_embargo.csv
    file parameters.py

    ## Creates
    file report_numbers.json
    """

    oa_global = pd.read_csv(DATA_FOLDER / 'oa_global_trend.csv')
    oa_global.sort_values('year', ascending=False, inplace=True)
    oa_country = pd.read_csv(DATA_FOLDER / 'oa_country_trend.csv')
    zero_embargo = pd.read_csv(DATA_FOLDER / 'zero_embargo.csv')

    for oa_type in OA_TYPES:
        for df in [oa_global, oa_country]:
            df[f'pc_{oa_type}'] = df[oa_type] / df['total'] * 100

        oa_global[f'pc_{oa_type}_increase'] = oa_global[f'pc_{oa_type}'].diff(periods=-1)

    # Testing
    census_year = dict(
        year=CENSUS_YEAR)
    census_year.update(
        {f'pc_{oa_type}': int(
            np.round(oa_global[oa_global.year == CENSUS_YEAR][f'pc_{oa_type}'].values[0], 0)) for oa_type in OA_TYPES}
    )
    census_year.update(
        {f'pc_{oa_type}_increase': int(
            np.round(oa_global[oa_global.year == CENSUS_YEAR][f'pc_{oa_type}_increase'].values[0], 0)) for oa_type in
            OA_TYPES}
    )

    zero_embargo_census_year = int(
        np.round(((zero_embargo[zero_embargo.year == CENSUS_YEAR]['count_zero_embargo'].values[0] /
                   oa_global[oa_global.year == CENSUS_YEAR]['other_platform'].values[0]) * 100), 0))
    census_year.update(dict(pc_other_platform_zero_embargo=zero_embargo_census_year))

    report_numbers_dict = dict(
        census_year=census_year,
        comparison_year=dict(year=CENSUS_YEAR - 1),
        report_year=REPORT_YEAR
    )

    if quarto:
        return report_numbers_dict
    else:
        for f in af.generate_file(REPORT_DATA_FILENAME):
            json.dump(report_numbers_dict, f)


def fig_oa_global_trend(af: AnalyticsFunction,
                        quarto: bool=False):
    # create and save locally a figure displaying global open access trends
    if not quarto:
        print('... start fig_oa_global_trend')
    df = pd.read_csv('tempdata/oa_global_trend.csv')

    fig = make_subplots(rows=2, cols=2, row_heights=(0.01, 0.99), horizontal_spacing=0.13)

    fig.add_trace(go.Scatter(
        x=df.year,
        y=df.publisher_only,
        hoverinfo='x+y',
        mode='lines',
        line=dict(width=0.5, color='#FFD700'),
        fillcolor='#FFD700',
        stackgroup='one',
        name="PUBLISHER OPEN", showlegend=False
    ), row=2, col=1)
    fig.add_trace(go.Scatter(
        x=df.year,
        y=df.both,
        hoverinfo='x+y',
        mode='lines',
        line=dict(width=0.5, color='#4fa9dc'),
        fillcolor='#4fa9dc',
        stackgroup='one',
        name="BOTH", showlegend=False
    ), row=2, col=1)
    fig.add_trace(go.Scatter(
        x=df.year,
        y=df.other_platform_only,
        hoverinfo='x+y',
        mode='lines',
        line=dict(width=0.5, color='#9FD27E'),
        fillcolor='#9FD27E',
        stackgroup='one',
        name="OTHER PLATFORM OPEN", showlegend=False
    ), row=2, col=1)
    fig.add_trace(go.Scatter(
        x=df.year,
        y=df.closed,
        hoverinfo='x+y',
        mode='lines',
        line=dict(width=0.5, color="gray"),
        fillcolor='gray',
        stackgroup='one',
        name="CLOSED", showlegend=False
    ), row=2, col=1)

    fig.add_trace(go.Scatter(
        x=df.year,
        y=df.publisher_only / df.total * 100,
        hoverinfo='x+y',
        mode='lines',
        line=dict(width=0.5, color='#FFD700'),
        fillcolor='#FFD700',
        stackgroup='one',
        name="PUBLISHER OPEN"
    ), row=2, col=2)
    fig.add_trace(go.Scatter(
        x=df.year,
        y=df.both / df.total * 100,
        hoverinfo='x+y',
        mode='lines',
        line=dict(width=0.5, color='#4fa9dc'),
        fillcolor='#4fa9dc',
        stackgroup='one',
        name="BOTH"
    ), row=2, col=2)
    fig.add_trace(go.Scatter(
        x=df.year,
        y=df.other_platform_only / df.total * 100,
        hoverinfo='x+y',
        mode='lines',
        line=dict(width=0.5, color='#9FD27E'),
        fillcolor='#9FD27E',
        stackgroup='one',
        name="OTHER PLATFORM OPEN"
    ), row=2, col=2)
    fig.add_trace(go.Scatter(
        x=df.year,
        y=df.closed / df.total * 100,
        hoverinfo='x+y',
        mode='lines',
        line=dict(width=0.5, color="gray"),
        fillcolor='gray',
        stackgroup='one',
        name="CLOSED"
    ), row=2, col=2)

    fig.update_layout(title=dict(text='<b>GLOBAL OPEN ACCESS LEVELS</b>'
                                      '<br><sup> TREND OVER ' + str(len(YEARS) - 1) + ' YEARS FROM ' + str(min(YEARS))
                                      + ' TO ' + str(CENSUS_YEAR) + '</sup>',
                                 font=dict(family="Arial, sans-serif", size=35, color="darkorange")),
                      font=dict(family="Arial, sans-serif", size=20)
                      )
    fig.update_layout(xaxis3={'type': 'category'})
    fig.update_layout(xaxis4={'type': 'category'})
    fig.update_yaxes(title_text="# Research Outputs", row=2, col=1)
    fig.update_yaxes(title_text="% Research Outputs", row=2, col=2)
    fig.update_xaxes(title_text="Year", row=2, col=1)
    fig.update_xaxes(title_text="Year", row=2, col=2)
    fig.update_layout(legend=dict(
        orientation="v",
        yanchor="bottom",
        y=0.9,
        xanchor="center",
        x=0.5
    ))

    if quarto:
        fig.show()
    else:
        if not os.path.exists('report_graphs'):
            os.makedirs('report_graphs')
        fig.write_image('report_graphs/oa_global_trend.png', scale=FIG_SCALE, width=1500, height=600)
        af.add_existing_file('report_graphs/oa_global_trend.png')

        print('... completed')


def fig_oa_country_compare(af: AnalyticsFunction,
                           quarto: bool=False):
    # create and save locally a figure displaying country OA summaries
    print('... start fig_oa_country_trend')
    df = pd.read_csv('tempdata/oa_country_trend.csv')
    df.replace('United Kingdom of Great Britain and Northern Ireland', 'United Kingdom', inplace=True)
    df_agg = df.groupby(['name']).agg('sum')
    df_agg['total'] = df_agg.open + df_agg.closed
    df_agg['open_perc'] = df_agg.open / df_agg.total * 100
    df_oa_sort = df_agg.sort_values(by=['open_perc'], ascending=False)
    top10_low = df_oa_sort[df_oa_sort.total > 30].head(10)
    top10_high = df_oa_sort[df_oa_sort.total > 10000 * len(YEARS)].head(10)

    fig = make_subplots(rows=2, cols=2, row_heights=(0.01, 0.99), horizontal_spacing=0.12, vertical_spacing=0.16,
                        subplot_titles=["", "",
                                        "Countries with more than 30 outputs overall",
                                        "Countries averaging more than 10,000 outputs per year"]
                        )

    # countries with more than 30 outputs
    fig.add_trace(go.Bar(x=top10_low.index.values, y=top10_low.publisher_only / top10_low.total * 100,
                         marker_color='#ffd700', name='PUBLISHER OPEN', showlegend=False),
                  row=2, col=1)
    fig.add_trace(go.Bar(x=top10_low.index.values, y=top10_low.both / top10_low.total * 100,
                         marker_color='#4fa9dc', name='BOTH', showlegend=False),
                  row=2, col=1)
    fig.add_trace(go.Bar(x=top10_low.index.values, y=top10_low.other_platform_only / top10_low.total * 100,
                         marker_color='#9FD27E', name='OTHER PLATFORM OPEN', showlegend=False),
                  row=2, col=1)

    # countries with more than 210,000 outputs
    fig.add_trace(go.Bar(x=top10_high.index.values, y=top10_high.publisher_only / top10_high.total * 100,
                         marker_color='#ffd700', name='PUBLISHER OPEN', showlegend=True),
                  row=2, col=2)
    fig.add_trace(go.Bar(x=top10_high.index.values, y=top10_high.both / top10_high.total * 100,
                         marker_color='#4fa9dc', name='BOTH', showlegend=True),
                  row=2, col=2)
    fig.add_trace(go.Bar(x=top10_high.index.values, y=top10_high.other_platform_only / top10_high.total * 100,
                         marker_color='#9FD27E', name='OTHER PLATFORM OPEN', showlegend=True),
                  row=2, col=2)

    fig.update_layout(title=dict(text='<b>TOP 10 COUNTRIES BY OPEN ACCESS LEVELS</b>'
                                      '<br><sup> DATA OVER ' + str(len(YEARS) - 1) + ' YEARS FROM ' + str(min(YEARS))
                                      + ' TO ' + str(CENSUS_YEAR) + '</sup>',
                                 font=dict(family="Arial, sans-serif", size=35, color="darkorange")),
                      yaxis3_title="Open access level (%)",
                      yaxis4_title="Open access level (%)",
                      barmode='stack',
                      font=dict(family="Arial, sans-serif", size=20))
    fig.update_layout(xaxis={'type': 'category'},
                      xaxis2={'type': 'category'})
    fig.update_layout(xaxis={'categoryorder': 'total descending'},
                      xaxis2={'categoryorder': 'total descending'})
    fig.update_layout(legend=dict(
        orientation="h",
        yanchor="bottom",
        y=0.9,
        xanchor="center",
        x=0.5
    ))
    fig.update_xaxes(tickangle=270)

    if quarto:
        fig.show()

    else:
        if not os.path.exists('report_graphs'):
            os.makedirs('report_graphs')
        fig.write_image('report_graphs/oa_country_compare.png', scale=FIG_SCALE, width=1500, height=800)
        af.add_existing_file('report_graphs/oa_country_compare.png')

        print('... completed')


def fig_oa_country_trend(af: AnalyticsFunction,
                         quarto: bool=False):
    # create and save locally a figure displaying country OA trends
    print('... start fig_oa_country_trend')
    df = pd.read_csv('tempdata/oa_country_trend.csv')

    # calculate total outputs and open access percentages, notes year begin and year end
    df['total'] = df.open + df.closed
    df['open_perc'] = df.open / df.total * 100

    # filter list of countries by total outputs - one for > 30 and one for >210000
    df_agg = df.groupby(['name']).agg('sum')
    df_agg['total'] = df_agg.open + df_agg.closed
    country_list_low = df_agg[df_agg.total > 30].index.values
    country_list_high = df_agg[df_agg.total > 10000 * len(YEARS)].index.values

    # find top 10 countries in terms of change in % open access for both lists
    df_start = df[df.year == min(YEARS)][['name', 'open_perc']]
    df_end = df[df.year == max(YEARS)][['name', 'open_perc']]
    df_diff = df_start.merge(df_end, on=['name'], suffixes=('_start', '_end'))
    df_diff['open_perc_diff'] = df_diff.open_perc_end - df_diff.open_perc_start
    top10_low = df_diff[df_diff.name.isin(country_list_low)]
    top10_low = top10_low.sort_values(by=['open_perc_diff'], ascending=False).head(10).name
    top10_high = df_diff[df_diff.name.isin(country_list_high)]
    top10_high = top10_high.sort_values(by=['open_perc_diff'], ascending=False).head(10).name

    # plot and save figure for top movers in countries with more than 30 outputs
    fig = make_subplots(rows=1, cols=1)
    for country in top10_low:
        df_fig = df[df.name == country].sort_values(by='year')
        fig.add_trace(go.Scatter(x=df_fig.year,
                                 y=df_fig.open_perc,
                                 name=country,
                                 legendgroup='1'), row=1, col=1)
    fig.update_layout(xaxis_type='category')
    fig.update_xaxes(categoryorder='category ascending')
    fig.update_layout(title=dict(text='<b>TOP 10 BIGGEST MOVERS IN OPEN ACCESS LEVELS</b>'
                                      '<br><sup>COUNTRIES WITH MORE THAN 30 OUTPUTS OVERALL </sup>',
                                 font=dict(family="Arial, sans-serif", size=35, color="darkorange")),
                      yaxis_title="Open access level (%)",
                      font=dict(family="Arial, sans-serif", size=20))
    fig.update_xaxes(title_text="Year", row=1, col=1)
    fig.update_xaxes(tickangle=270)
    if not os.path.exists('report_graphs'):
        os.makedirs('report_graphs')
    fig.write_image('report_graphs/oa_country_trend_low.png', scale=FIG_SCALE, width=1500, height=600)
    af.add_existing_file('report_graphs/oa_country_trend_low.png')

    # plot and save figure for top movers in countries with more than 10,000 outputs per year
    fig = make_subplots(rows=1, cols=1)
    for country in top10_high:
        df_fig = df[df.name == country].sort_values(by='year')
        fig.add_trace(go.Scatter(x=df_fig.year,
                                 y=df_fig.open_perc,
                                 name=country,
                                 legendgroup='2'), row=1, col=1)
    fig.update_layout(xaxis_type='category')
    fig.update_xaxes(categoryorder='category ascending')
    fig.update_layout(title=dict(text='<b>TOP 10 BIGGEST MOVERS IN OPEN ACCESS LEVELS</b>'
                                      '<br><sup>COUNTRIES AVERAGING MORE THAN 10,000 OUTPUTS PER YEAR </sup>',
                                 font=dict(family="Arial, sans-serif", size=35, color="darkorange")),
                      yaxis_title="Open access level (%)",
                      font=dict(family="Arial, sans-serif", size=20))
    fig.update_xaxes(title_text="Year", row=1, col=1)
    fig.update_xaxes(tickangle=270)

    if quarto:
        fig.show()
    else:
        if not os.path.exists('report_graphs'):
            os.makedirs('report_graphs')
        fig.write_image('report_graphs/oa_country_trend_high.png', scale=FIG_SCALE, width=1500, height=600)
        af.add_existing_file('report_graphs/oa_country_trend_high.png')

        print('... completed')


def git_status(af: AnalyticsFunction,
               quarto: bool=False):
    """
    Record Git Status for Current State of the Repo
    """

    # Force git_status to run
    repo = Repo(search_parent_directories=True)
    print('This report was run from the git commit hash: ' + repo.head.object.hexsha)
    changedfiles = [item.a_path for item in repo.index.diff(None)]
    if len(changedfiles) > 0:
        print('WARNING: This report was run with local changes that were not committed to the following files: ')
        print(changedfiles)

    d = dict(
            sha=repo.head.object.hexsha,
            changedfiles=[item.a_path for item in repo.index.diff(None)],
            branch=repo.active_branch.name,
            remotes=', '.join([remote.name for remote in repo.remotes]),
            remote_url=';'.join(remote.url for remote in repo.remotes)
    )

    if quarto:
        return d
    else:
        for f in af.generate_file('git_status.json'):
            json.dump(d,f)


def file_assets(af: AnalyticsFunction):
    """
    Add key file assets to the Precipy File Records
    """

    af.add_existing_file('coki_assets/title_image.png')
    af.add_existing_file('coki_assets/blank_page.pdf')
    af.add_existing_file('coki_assets/final_page.png')