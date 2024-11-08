import streamlit as st
from datetime import datetime, timedelta
import pandas as pd
import json
import math
import requests
import plotly.graph_objects as go
import plotly.colors as colors

def PVprod(row):
   prod = row['Consumption']+row['FeedIn']+row['StoragePower']-row['Purchased']
   if prod<0:
       prod = 0
   return prod
   
def StoragePW(row):
   prod = row['Consumption']+row['FeedIn']+row['StoragePower']-row['Purchased']
   if prod<0:
       stor = row['StoragePower'] - prod
   else:
       stor = row['StoragePower']
   return stor

st.title("🎈 My new app")
st.write(
    "Let's start building! For help and inspiration, head over to [docs.streamlit.io](https://docs.streamlit.io/)."
)

# Get date
# -------------------------

d = st.date_input("Seleziona giorno", value='today')
date_string = d.strftime("%Y-%m-%d")

# Read data
# -------------------------

response = requests.get(st.secrets.api.url+"?startTime="+date_string+" 00:00:00&endTime="+date_string+" 23:59:00&api_key="+st.secrets.api.key)
df = pd.json_normalize(response.json(), record_path=['powerDetails', 'meters', 'values'], meta=[['meters', '0', 'type']])
with open('powerDetails.json', 'w') as f:
    json.dump(response.json(), f)

data = json.load(open('powerDetails.json'))
df = pd.json_normalize(data, record_path=['powerDetails', 'meters', 'values'], meta=[['meters', '0', 'type']])

date_list = df['date'].to_list()
value_list = df['value'].to_list()
type_list = df['meters.0.type'].to_list()

value_list = [x/1000 for x in value_list]

response = requests.get(st.secrets.api.url2+"?startTime="+date_string+" 00:00:00&endTime="+date_string+" 23:59:00&api_key="+st.secrets.api.key)
df = pd.json_normalize(response.json(), record_path=['storageData', 'batteries', 'telemetries'])
with open('storageData.json', 'w') as f:
    json.dump(response.json(), f)
    
data = json.load(open('storageData.json'))
df = pd.json_normalize(data, record_path=['storageData', 'batteries', 'telemetries'])

time = datetime.strptime(df['timeStamp'][0], '%Y-%m-%d %H:%M:%S').replace(hour=0, minute=0, second=0)
val = 0
num = 0
date_diff = (datetime.strptime(date_list[1], '%Y-%m-%d %H:%M:%S')-datetime.strptime(date_list[0], '%Y-%m-%d %H:%M:%S')).total_seconds() / 60

for index, row in df.iterrows():
    # print(row['timeStamp'], row['power'])
    dt = datetime.strptime(row['timeStamp'], '%Y-%m-%d %H:%M:%S')
    if math.isnan(row['power']):
        val_add = 0
    else:
        val_add = row['power']
    print(str(dt)+'\t'+str(val_add)+'\t'+str(row['batteryPercentageState']))
    if (dt-time).total_seconds() / 60 > date_diff:
        date_list.append(time.strftime('%Y-%m-%d %H:%M:%S'))
        if num == 0:
            value_list.append(0)
        else:
            value_list.append(val/num/1000)
        type_list.append('StoragePower')
        
        date_list.append(time.strftime('%Y-%m-%d %H:%M:%S'))
        value_list.append(row['batteryPercentageState'])
        type_list.append('StoragePct')
        
        time = time + timedelta(minutes=date_diff)
        val = val_add
        num = 1
    else:
        val = val + val_add
        num = num + 1
    # print(time, val_add)
date_list.append(time.strftime('%Y-%m-%d %H:%M:%S'))
if num == 0:
    value_list.append(0)
else:
    value_list.append(val/num/1000)
type_list.append('StoragePower')
date_list.append(time.strftime('%Y-%m-%d %H:%M:%S'))
value_list.append(row['batteryPercentageState'])
type_list.append('StoragePct')

df = pd.DataFrame({'date': date_list, 'meters.0.type': type_list, 'value': value_list})
table = pd.pivot(df, values='value', index='date', columns='meters.0.type')
# Calculate PV production
table['PVProduction'] = table.apply(PVprod, axis=1)

# Correct Storage Power in case PV production is negative
table['StoragePower'] = table.apply(StoragePW, axis=1)

# Sums
# -------------------------
sum_produzione = table['PVProduction'].sum()/4
sum_consumo = table['Consumption'].sum()/4

sum_venduta = table['FeedIn'].sum()/4
sum_batteria = table['StoragePower'].sum()/4
sum_acquistata = table['Purchased'].sum()/4
sum_autoconsumo = sum_consumo - sum_acquistata
sum_autoconsumo2 = sum_produzione - sum_batteria - sum_venduta

#st.write("Produzione: "+'{0:.1f}'.format(sum_produzione)+" kWh")
#st.write("Consumo: "+'{0:.1f}'.format(sum_consumo)+" kWh")

# Graphs
# -------------------------

# Riassunto
x=['Produzione ('+'{0:.1f}'.format(sum_produzione)+' kWh)', 'Consumo ('+'{0:.1f}'.format(sum_consumo)+' kWh)']
fig = go.Figure()
fig.add_trace(go.Bar(x=x, y=[sum_autoconsumo, sum_autoconsumo], name='Autoconsumo ('+'{0:.1f}'.format(sum_autoconsumo)+' kWh)', marker_color=colors.qualitative.Plotly[7]))
fig.add_trace(go.Bar(x=x, y=[sum_venduta, 0], name='Venduta ('+'{0:.1f}'.format(sum_venduta)+' kWh)', marker_color=colors.qualitative.Plotly[4]))
fig.add_trace(go.Bar(x=x, y=[sum_batteria, 0], name='Accumulata in batteria ('+'{0:.1f}'.format(sum_batteria)+' kWh)', marker_color=colors.qualitative.Plotly[0]))
fig.add_trace(go.Bar(x=x, y=[0, sum_acquistata], name='Acquistata ('+'{0:.1f}'.format(sum_acquistata)+' kWh)', marker_color=colors.qualitative.Plotly[3]))
fig.update_layout(barmode='stack', title = 'Bilancio', yaxis_title="kWh")
st.plotly_chart(fig, use_container_width=True)

# Produzione e consumo
fig = go.Figure()
fig.add_trace(go.Scatter(x=table.index, y=table['Consumption'], 
                    name='Consumo', line_color=colors.qualitative.Plotly[1]
              ))
fig.add_trace(go.Scatter(x=table.index, y=table['PVProduction'], 
                    name='Produzione', line_color=colors.qualitative.Plotly[2]
                    ))
fig.update(layout_yaxis_range = [0, 10])
fig.update_layout(title = 'Produzione e consumo', yaxis_title="kW")
st.plotly_chart(fig, use_container_width=True)

# Vendita e acquisto
fig = go.Figure()
fig.add_trace(go.Scatter(x=table.index, y=table['StoragePower'],
                    name='Alla batteria', line_color = colors.qualitative.Plotly[0]
                    ))
fig.add_trace(go.Scatter(x=table.index, y=table['FeedIn'], 
                    name='Venduta', line_color = colors.qualitative.Plotly[4]
                    ))
fig.add_trace(go.Scatter(x=table.index, y=table['Purchased'],
                    name='Acquistata', line_color = colors.qualitative.Plotly[3]
                    ))
fig.update(layout_yaxis_range = [0, 10])
fig.update_layout(title = 'Vendita e acquisto', yaxis_title="kW")
st.plotly_chart(fig, use_container_width=True)

# Carica batteria
fig = go.Figure()
fig.add_trace(go.Scatter(x=table.index, y=table['StoragePct'], 
                    name='Carica batteria', line_color = colors.qualitative.Plotly[5]
                    ))
fig.update(layout_yaxis_range = [0, 100])
fig.update_layout(title = 'Carica batteria', yaxis_title="%", showlegend=True)
st.plotly_chart(fig, use_container_width=True)