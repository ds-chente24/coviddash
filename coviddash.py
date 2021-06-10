import dash
import dash_html_components as html
import dash_core_components as dcc
import dash_bootstrap_components as dbc
from dash.dependencies import Input, Output
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.express as px
from datetime import date, datetime, timedelta, time
from urllib.request import urlopen
import json
import pytz

pd.set_option('mode.chained_assignment', None)

#CA Vaccine Data
v_df = pd.read_csv('https://data.chhs.ca.gov/dataset/e283ee5a-cf18-4f20-a92c-ee94a2866ccd/resource/130d7ba2-b6eb-438d-a412-741bde207e1c/download/covid19vaccinesbycounty.csv')
v_df_ca = v_df.query('california_flag == "California"')
df_1 = v_df_ca.rename(columns={'administered_date':'date'})

#CA Case Data
case_df = pd.read_csv('https://data.chhs.ca.gov/dataset/f333528b-4d38-4814-bebb-12db1f10f535/resource/046cdd2b-31e5-4d34-9ed3-b48cdbc4be7a/download/covid19cases_test.csv')

demo_df = pd.read_csv('https://data.chhs.ca.gov/dataset/f333528b-4d38-4814-bebb-12db1f10f535/resource/e2c6a86b-d269-4ce1-b484-570353265183/download/covid19casesdemographics.csv')

case_df_ca = case_df.query('area_type == "County"')
df_2 = case_df_ca.rename(columns={'area':'county'})

#Merge Vaccine and Case Datasets
m_df = df_2.merge(df_1, on=['county', 'date'],how='left')
m_df.set_index('date', inplace=True)
m_df.sort_values(['date','county'],inplace=True)

#Add Columns to Merged Dataset
m_df['cumulative_cases'] = m_df.groupby('county')['cases'].cumsum()
m_df['case_MA7'] = m_df.groupby('county')['cases'].transform(lambda s: s.rolling(7).mean())
m_df['case_rate'] = m_df['case_MA7']/m_df['population']
m_df['cases_per_100k'] = ((m_df['case_rate']*100000)).round(2)
m_df['percent_total_vaccinated'] = ((m_df['cumulative_fully_vaccinated']/m_df['population'])*100).round(2)
m_df['pop_vaccinated'] = m_df['cumulative_fully_vaccinated']
m_df['pop_unvaccinated'] = (m_df['population'] - m_df['pop_vaccinated']).round(0)
m_df['sus_pop_vaccinated'] = (m_df['pop_vaccinated']*0.15).round(0)
m_df['sus_pop'] = (m_df['pop_unvaccinated'] + m_df['sus_pop_vaccinated']).round(0)
m_df['vax_adj_cr'] = m_df['case_MA7']/m_df['sus_pop']
m_df['vax_adj_cper100k'] = ((m_df['vax_adj_cr']*100000)).round(2)
m_df.fillna(0, inplace=True)

#fips data
df_fips = pd.read_csv('https://github.com/ds-chente24/coviddash/blob/5a8c915f9f30315aa8012177f982fe23b43dc647/ca_fips_county.csv', dtype={'fips':str})
m_df_fips = m_df.reset_index().merge(df_fips, on='county', how='left').set_index('date')

#County Map
with urlopen('https://raw.githubusercontent.com/plotly/datasets/master/geojson-counties-fips.json') as response:
    counties = json.load(response)

#Choropleth Map
tday = date.today().strftime('%Y-%m-%d')
yday = (date.today()-timedelta(1)).strftime('%Y-%m-%d')
dbyday = (date.today()-timedelta(2)).strftime('%Y-%m-%d')
t_10am = time(hour=10, minute=00).strftime('%H:%M')
tz_LA = pytz.timezone('US/Pacific')
time_now = datetime.now(tz_LA).strftime('%H:%M')

def mapdata():
    global curr_m_df
    global uday
    if time_now > t_10am:
       curr_m_df = m_df_fips.loc[yday]
       uday = yday
    else:
        curr_m_df = m_df_fips.loc[dbyday]
        uday = dbyday
    
mapdata()
curr_m_df.dropna(inplace=True)

fig_px = px.choropleth_mapbox(curr_m_df,geojson=counties,locations='fips',
                           color='cases_per_100k',
                           color_continuous_scale="Portland",
                           mapbox_style="carto-positron",
                           zoom=4.5, center = {"lat": 36.7783, "lon": -119.4179},
                           opacity=0.5,
                           labels={'cases_per_100k':'New Cases/100k',
                                   'county':'County',
                                   'percent_total_vaccinated':'% Fully Vaccinated',
                                   'vax_adj_cper100k':'Vax Adjusted New Cases/100k'
                                   },
                           hover_data={'county':True,
                                       'cases_per_100k':True,
                                       'percent_total_vaccinated':True,
                                       'fips': False,
                                       'vax_adj_cper100k':True},
                            )
fig_px.update_layout(
    title_text='<br>CA Counties New Cases Rate<br>(Hover for more info)<br>As of: '+uday,
    margin={"r":0,"t":0,"l":0,"b":0})


#Demographic Data
demo_df = pd.read_csv('https://data.chhs.ca.gov/dataset/f333528b-4d38-4814-bebb-12db1f10f535/resource/e2c6a86b-d269-4ce1-b484-570353265183/download/covid19casesdemographics.csv')
demo_df_race = demo_df.query('demographic_category == "Race Ethnicity"')
demo_df_race.set_index('report_date',inplace=True)
demo_df_race.sort_index(inplace=True)
demo_df_race.reset_index(inplace=True)
demo_df_race.drop(demo_df_race[demo_df_race['demographic_value']== 'Total'].index, inplace=True)
demo_df_race['ystr_cases'] = demo_df_race.groupby('demographic_value')['total_cases'].shift(1)
demo_df_race['new_cases'] = demo_df_race['total_cases'] - demo_df_race['ystr_cases']
demo_df_race['ystr_deaths'] = demo_df_race.groupby('demographic_value')['deaths'].shift(1)
demo_df_race['new_deaths'] = demo_df_race['deaths'] - demo_df_race['ystr_deaths']
demo_df_race['CA_pop'] = 40129160
demo_df_race['pct_CA_pop'] = (demo_df_race['percent_of_ca_population']/100)
demo_df_race['est_pop_race'] = ((demo_df_race['pct_CA_pop']*demo_df_race['CA_pop']).round(0))
def adjnewcase(df):
    newcase = df['new_cases']
    ystrcase = df['ystr_cases']
    adj = (df['new_cases']+df['ystr_cases'])
    ystr = df['ystr_cases']
    if newcase < 0:
        return adj
    else:
        return ystr

demo_df_race['adj_ystr_cases']= demo_df_race.apply(axis='columns', func=lambda df: adjnewcase(df))

def adjnewdeath(df):
    newdeaths = df['new_deaths']
    ystrdeaths = df['ystr_deaths']
    adj = (df['new_deaths']+df['ystr_deaths'])
    ystr = df['ystr_deaths']
    if newdeaths < 0:
        return adj
    else:
        return ystr

demo_df_race['adj_ystr_deaths']= demo_df_race.apply(axis='columns', func=lambda df: adjnewdeath(df))
demo_df_race['adj_new_cases'] = demo_df_race['total_cases'] - demo_df_race['adj_ystr_cases']
demo_df_race['adj_new_deaths'] = demo_df_race['deaths'] - demo_df_race['adj_ystr_deaths']
demo_df_race['total_new_cases'] = demo_df_race.groupby('report_date')['adj_new_cases'].transform(lambda s: s.sum())
demo_df_race['total_new_deaths'] = demo_df_race.groupby('report_date')['adj_new_deaths'].transform(lambda s: s.sum())
demo_df_race['percent_new_cases'] = ((demo_df_race['adj_new_cases']/demo_df_race['total_new_cases'])*100).round(2)
demo_df_race['percent_new_deaths'] = ((demo_df_race['adj_new_deaths']/demo_df_race['total_new_deaths'])*100).round(2)
demo_df_race['new_case_MA7'] = demo_df_race.groupby('demographic_value')['adj_new_cases'].transform(lambda s: s.rolling(7).mean())
demo_df_race['new_deaths_MA7'] = demo_df_race.groupby('demographic_value')['adj_new_deaths'].transform(lambda s: s.rolling(7).mean())
demo_df_race['case_rate'] = demo_df_race['new_case_MA7']/demo_df_race['est_pop_race']
demo_df_race['cases_per_100k'] = ((demo_df_race['case_rate']*100000)).round(2)
demo_df_race['death_rate'] = demo_df_race['new_deaths_MA7']/demo_df_race['total_cases']
demo_df_race['deaths_per_10k'] = ((demo_df_race['death_rate']*10000)).round(2)

#Create Graphs for Demo Data
fig_rc_pct = px.bar(demo_df_race,x='report_date',y='percent_new_cases',color='demographic_value',
                  color_discrete_sequence=px.colors.qualitative.G10,
                  labels={'report_date':'Date',
                          'percent_new_cases': '% of New Cases',
                          'demographic_value':'Race/Ethnicity'})
fig_rc_pct.update_layout(title='Proportion of New Cases by Race/Ethnicity',
                         xaxis=dict(title='Date'),
                         yaxis=dict(title='% of New Cases'))
fig_rd_pct = px.bar(demo_df_race,x='report_date',y='percent_new_deaths',color='demographic_value',
                  color_discrete_sequence=px.colors.qualitative.G10,
                  labels={'report_date':'Date',
                          'percent_new_deaths': '% of New Deaths',
                          'demographic_value':'Race/Ethnicity'})
fig_rd_pct.update_layout(title='Proportion of New Deaths by Race/Ethnicity',
                         xaxis=dict(title='Date'),
                         yaxis=dict(title='% of New Deaths'))
fig_rc100k = px.line(demo_df_race,x='report_date',y='cases_per_100k',color='demographic_value',
                  color_discrete_sequence=px.colors.qualitative.G10,
                  labels={'report_date':'Date',
                          'cases_per_100k': 'New Cases per 100k',
                          'demographic_value':'Race/Ethnicity'})
fig_rc100k.update_layout(title='New Cases Rate by Race/Ethnicity',
                         xaxis=dict(title='Date'),
                         yaxis=dict(title='New Cases/100k'))
fig_rd10k = px.line(demo_df_race,x='report_date',y='deaths_per_10k',color='demographic_value',
                  color_discrete_sequence=px.colors.qualitative.G10,
                  labels={'report_date':'Date',
                          'deaths_per_10k': 'New Deaths per 10k',
                          'demographic_value':'Race/Ethnicity'})
fig_rd10k.update_layout(title='New Deaths Rate by Race/Ethnicity',
                         xaxis=dict(title='Date'),
                         yaxis=dict(title='New Deaths/10k'))

#Create the Dash app
app = dash.Dash(external_stylesheets=[dbc.themes.BOOTSTRAP])
server = app.server

#Setup the app layout
tab1_content= dbc.Card(dbc.CardBody([dcc.Graph(id='choropleth',figure=fig_px,
                                               config={'displayModeBar':False})]))
tab2_content=dbc.Card(
    dbc.CardBody(
        [
            dcc.Markdown('''###### Please select:'''),
            dcc.Dropdown(id='county-dropdown', options=[{'label': i, 'value': i}
                                                        for i in m_df['county'].unique()],
                         value='Los Angeles'),
            dcc.Graph(id='cv-graph'),
            dcc.Graph(id='case-graph')
        ]
    )
)
tab3_content=dbc.Card(
    dbc.CardBody(
        [
            dcc.RadioItems(id='radio-cd',
                           options=[{'label': 'Cases', 'value':'case_graph'},
                                    {'label': 'Deaths', 'value':'deaths_graph'}],
                           value='case_graph'),
            dcc.Graph(id='cd-graph'),
            dcc.Graph(id='crdr-graph')
        ]
    )
)
tab4_content= html.Div(
    [
        dbc.Card(
            dbc.CardBody(
                [
                    html.H5('Purpose', className='card-title'),
                    html.P(
                        [
                          'A resource to track COVID-19 cases in California, ',
                          'while also demonstrating the utility of Python for ',
                          'epidemiological practice and analysis.'  
                        ],
                        className='card-text'
                    ),
                ]
            ),
        ),
        dbc.Card(
            dbc.CardBody(
                [
                    html.H5('Data Sources', className='card-title'),
                    html.P(
                        [
                            'Case, vaccination, and demographic datasets are ',
                            'available via CHHS Open Data Portal at the below links:'
                        ],
                        className='card-text'
                    ),
                    dbc.CardLink('Case Data', href='https://data.chhs.ca.gov/dataset/f333528b-4d38-4814-bebb-12db1f10f535/resource/046cdd2b-31e5-4d34-9ed3-b48cdbc4be7a'),
                    dbc.CardLink('Vaccine Data', href='https://data.chhs.ca.gov/dataset/e283ee5a-cf18-4f20-a92c-ee94a2866ccd/resource/130d7ba2-b6eb-438d-a412-741bde207e1c'),
                    dbc.CardLink('Demographic Data', href='https://data.chhs.ca.gov/dataset/f333528b-4d38-4814-bebb-12db1f10f535/resource/e2c6a86b-d269-4ce1-b484-570353265183'),
                ]
            ),            
        ),
        dbc.Card(
            dbc.CardBody(
                [
                    html.H5('Methodology', className='card-title'),
                    html.P(
                        [
                            'All figures were generated using the open source Python packages of ',
                            'Plotly and Dash. All calculations were completed using Pandas. ',
                            'Vaccine-adjusted case rates were calculated conservatively, where ',
                            '15% of fully vaccinated individuals were considered at-risk for breakthrough infection. ',                            
                            'Actual breakthrough infection rate may be greater or less than the estimation used. ',
                            'All partially vaccinated individuals were included in the at-risk population.'
                        ],
                        className='card-text'
                    ),
                ]
            ),
        ),
        dbc.Card(
            dbc.CardBody(
                [
                    html.H5('Data Updates and Quality', className='card-title'),
                    html.P(
                        [
                            'Original data is directly pulled from sources above. Typically, the most recent data availble is from the day before. '
                            'County map data is updated everyday at 10am PST. Original data quality is dependent on county and/or state reporting authorities. ',
                        ],
                        className='card=text'
                    ),
                ]
            )
        ),
        dbc.Card(
            dbc.CardBody(
                [
                    html.H5('About the Author', className='card-title'),
                    html.P(
                        [
                          'This dashboard was created by Vincent Puga-Aragon, a public health/biotech data professional. ',
                          'Vincent received his BS from the University of La Verne, majoring in Biology. He earned ',
                          'his MPH from the University of Southern California, with a concentration in ',
                          'Biostatistics and Epidemiology. As a Python evangelist, Vincent is dedicated to developing and communicating health ',
                          'outcomes for all populations through data visualization.'  
                        ],
                        className='card-text'
                    ),
                ]
            )
        ),
        dbc.Card(
            dbc.CardBody(
                [
                  html.H5('Contact', className='card-title'),
                  html.P(
                      [
                          'For any questions or inquiries please contact Vincent via email, chente16ds@gmail.com or ',
                          'on LinkedIn at the profile below: ',                    
                        ],
                        className='card-text'
                    ),                  
                  dbc.CardLink('LinkedIn', href='https://www.linkedin.com/in/vincent-puga-aragon-332976100/')                    
                ]
            )
        ),
        dbc.Card(
            dbc.CardBody(
                [
                    html.H6('Version', className='card-title'),
                    html.P(
                        [
                            'V1.0 released June 10th, 2021'
                        ],
                        className='card-text'
                    ),
                ]
            )
        ),
    ]
)

app.layout = dbc.Container(
    [
     html.H1(children='California COVID-19 Case Surveillance Dashboard'),
     html.Hr(),
     dbc.Tabs(
         [
             dbc.Tab(tab1_content, label='Counties Map'),
             dbc.Tab(tab2_content,label='7-Day Moving Average'),
             dbc.Tab(tab3_content,label='State Race/Ethnicity Cases and Deaths'),
             dbc.Tab(tab4_content,label='About')
         ])
    ])
  

#Setup the callback function
@app.callback(
    [Output(component_id='cv-graph', component_property='figure'),
     Output(component_id='case-graph', component_property='figure')],
    [Input(component_id='county-dropdown', component_property='value')]
    )
def update_graph(selected_county):
    m_df_c = m_df[m_df['county'] == selected_county]
    m_df_c_vax = m_df_c[m_df_c['vax_adj_cper100k'] != 0]
    fig_cv = make_subplots(specs=[[{"secondary_y": True}]])
    fig_cv.add_scatter(x=m_df_c.index,
                      y=m_df_c['cases_per_100k'],
                      mode='lines',
                      name='New Cases/100k',
                      line_color='firebrick',
                      secondary_y=False)
    fig_cv.add_scatter(x=m_df_c_vax.index,
                      y=m_df_c_vax['vax_adj_cper100k'],
                      mode='lines',
                      name='Vaccine Adjusted New Cases/100k',
                      line_color='green',
                      secondary_y=False)
    fig_cv.add_scatter(x=m_df_c.index,
                      y=m_df_c['percent_total_vaccinated'],
                      mode='lines',
                      name='% of Total Population Fully Vaccinated',
                      line_color='royalblue',
                      secondary_y=True)
    fig_cv.update_layout(title='7-Day Moving Average New Cases Rate and Fully Vaccinated Population Percentage',
                     xaxis=dict(title='Date'),
                     yaxis=dict(title='New Cases per 100k'))
    fig_cv.update_yaxes(title_text='% of Population Fully Vaccinated',
                    secondary_y = True,
                    range=[0,100])
    fig_case=go.Figure()
    fig_case.add_bar(x=m_df_c.index,
                     y=m_df_c['cases'],
                     name='New Cases/Day')
    fig_case.add_scatter(x=m_df_c.index,
                         y=m_df_c['case_MA7'],
                         name='7-Day Moving Average of New Cases')
    fig_case.update_layout(title='New Cases per Day',
                           xaxis=dict(title='Date'),
                           yaxis=dict(title='# of New Cases'))
    
    return fig_cv, fig_case

@app.callback(
    [Output(component_id='cd-graph', component_property='figure'),
     Output(component_id='crdr-graph', component_property='figure')],
    [Input(component_id='radio-cd', component_property='value')]
    )
def demo_graph(value):
    if value == 'case_graph':
        return fig_rc_pct, fig_rc100k
    else:
        return fig_rd_pct, fig_rd10k

