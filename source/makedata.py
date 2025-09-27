"""Make load data"""

import os
import sys
import datetime as dt
import pandas as pd
import config
import states
import urllib
from utils import *

INPUTS = {
    "COUNTIES" : "../data/US/counties.csv",
}

OUTPUTS = {
    "COOLING" : "../data/US/{state}/cooling.csv",
    "HEATING" : "../data/US/{state}/heating.csv",
    "SOLAR" : "../data/US/{state}/solar.csv",
    "TEMPERATURE" : "../data/US/{state}/temperature.csv",
    "TOTAL" : "../data/US/{state}/total.csv",
    "WIND" : "../data/US/{state}/wind.csv",
}

REFRESH = False
FREQ = "1h"

residential_buildings = [
    "mobile_home",
    "multi-family_with_2_-_4_units",
    "multi-family_with_5plus_units",
    "single-family_attached",
    "single-family_detached",
]

commercial_buildings = [
    "fullservicerestaurant",
    "hospital",
    "largehotel",
    "largeoffice",
    "mediumoffice",
    "outpatient",
    "primaryschool",
    "quickservicerestaurant",
    "retailstandalone",
    "retailstripmall",
    "secondaryschool",
    "smallhotel",
    "smalloffice",
    "warehouse",
]

resstock_server = "https://oedi-data-lake.s3.amazonaws.com/nrel-pds-building-stock/end-use-load-profiles-for-us-building-stock/2021/resstock_amy2018_release_1/timeseries_aggregates/by_county"
resstock_data = "{repo}/state={usps}/g{fips}0{puma}0-{type}.csv"

comstock_server = "https://oedi-data-lake.s3.amazonaws.com/nrel-pds-building-stock/end-use-load-profiles-for-us-building-stock/2021/comstock_amy2018_release_1/timeseries_aggregates/by_county"
comstock_data = "{repo}/state={usps}/g{fips}0{puma}0-{type}.csv"

weather_server = "https://oedi-data-lake.s3.amazonaws.com/nrel-pds-building-stock/end-use-load-profiles-for-us-building-stock/2021/resstock_amy2018_release_1/weather/amy2018"
weather_data = "{repo}/G{fips}0{puma}0_2018.csv"

counties = pd.read_csv(INPUTS["COUNTIES"],
    converters = {"fips":str},
    index_col = ["fips"],
    )

geodata = dict(
    temperature = [],
    wind = [],
    solar = [],
    cooling = [],
    heating = [],
    total = [],
    )
sources = dict(
    temperature = "temperature[degC]",
    wind = "wind[m/s]",
    solar = "solar[W/m^2]",
    cooling = "cooling[MW]",
    heating = "heating[MW]",
    total = "total[MW]",
    )

options.context = "geodata.py"
options.verbose = True
pd.options.display.max_columns = None
pd.options.display.width = None

def get_residential(state_usps,state_fips,puma,building_type):
    url = resstock_data.format(repo=resstock_server,usps=state_usps,fips=state_fips,puma=puma[2:],type=building_type)
    try:

        data = pd.read_csv(url,
            index_col=["timestamp"],
            usecols = ["timestamp",
                "in.geometry_building_type_recs",
                "out.electricity.cooling.energy_consumption",
                "out.electricity.heating.energy_consumption",
                "out.electricity.heating_supplement.energy_consumption",
                "out.electricity.total.energy_consumption",
                ],
            parse_dates = ["timestamp"],
            converters = {
                "out.electricity.cooling.energy_consumption" : lambda x: float(x)/1000,
                "out.electricity.heating.energy_consumption" : lambda x: float(x)/1000,
                "out.electricity.heating_supplement.energy_consumption" : lambda x: float(x)/1000,
                "out.electricity.total.energy_consumption" : lambda x: float(x)/1000,
            },
            low_memory=True)
        verbose(".",end="")
        data.columns = ["building_type","cooling[MW]","heating[MW]","auxheat[MW]","total[MW]"]
        data["heating[MW]"] += data["auxheat[MW]"]
        data.drop("auxheat[MW]",axis=1,inplace=True)
        data = pd.DataFrame(data.resample(FREQ).sum())
        return data.iloc[:8760].reset_index()

    except urllib.error.HTTPError as err:
        
        return None

def get_weather(state_fips,puma):
    url = weather_data.format(repo=weather_server,fips=state_fips,puma=puma[2:])
    try:
        data = pd.read_csv(url,
            index_col = [0],
            usecols = [0,1,3,5],
            parse_dates = [0],
            dtype = float,
            low_memory = True,
            header=None,
            skiprows=1,
            )
        data.columns = ["temperature[degC]","wind[m/s]","solar[W/m^2]"]
        data.index.name = "timestamp"
        data.index = data.index - dt.timedelta(hours=1) # change fromto leading timestamp
        return data.resample(FREQ).mean()
    except urllib.error.HTTPError:

        return None

def get_commercial(state_usps,state_fips,puma,building_type):
    url = comstock_data.format(repo=comstock_server,usps=state_usps,fips=state_fips,puma=puma[2:],type=building_type)
    try:

        data = pd.read_csv(url,
            index_col=["timestamp"],
            usecols = ["timestamp",
                "in.building_type",
                "out.electricity.cooling.energy_consumption",
                "out.electricity.heating.energy_consumption",
                "out.electricity.total.energy_consumption",
                ],
            parse_dates = ["timestamp"],
            converters = {
                "out.electricity.cooling.energy_consumption" : lambda x: float(x)/1000,
                "out.electricity.heating.energy_consumption" : lambda x: float(x)/1000,
                "out.electricity.total.energy_consumption" : lambda x: float(x)/1000,
            },
            low_memory=True)
        verbose(".",end="")
        data.columns = ["building_type","cooling[MW]","heating[MW]","total[MW]"]
        data = pd.DataFrame(data[["cooling[MW]","heating[MW]","total[MW]"]].resample(FREQ).sum())
        data["building_type"] = building_type
        return data[:8760].reset_index()

    except urllib.error.HTTPError as err:
        
        return None

def get_state(state_usps,year=2018,scalar=1.0):

    state_fips = states.fips(state_usps)

    verbose(f"Processing {state_usps} (fips={state_fips})...")
    geodata = dict(
        temperature = [],
        wind = [],
        solar = [],
        cooling = [],
        heating = [],
        total = [],
        )

    verbose("Loading existing county geodata",end="...")
    for table in geodata:
        try:
            data = pd.read_csv(OUTPUTS[table.upper()].format(state=state_usps),index_col=["timestamp"],parse_dates=["timestamp"])
            for column in data:
                geodata[table].append(pd.DataFrame(data=data[column].values,index=data.index,columns=[column]))
        except:
            geodata[table] = []
    verbose("ok")

    for puma in [x for x in counties.index.values if x.startswith(state_fips)]:

        geocode = counties.loc[puma]['geocode']

        # check if data exists already
        found = 0
        for table in geodata:
            if geocode in [list(x.columns)[0] for x in geodata[table]]:
                found += 1
        if found == len(geodata):
            continue # data is up-to-date

        verbose(f"Processing {counties.loc[puma]['county']} {counties.loc[puma]['usps']} ({geocode})",end="...")

        # weather data
        weather = get_weather(state_fips,puma)

        # residential buildings
        buildings = []
        for building_type in residential_buildings:
            buildings.append(get_residential(state_usps,state_fips,puma,building_type))

        # commercial buildings
        for building_type in commercial_buildings:
            buildings.append(get_commercial(state_usps,state_fips,puma,building_type))

        try:

            buildings = pd.DataFrame(pd.concat(buildings).set_index(["timestamp","building_type"]).groupby("timestamp").sum())

            for group,prec in [[weather,1],[buildings,3]]:
                for table,column in sources.items():
                    if column in group.columns:
                        geodata[table].append(pd.DataFrame(data=group[column].values,index=group.index,columns=[geocode]).round(prec))

            verbose("ok")

        except Exception as err:

            verbose(err)

        # save progress
        for table,data in geodata.items():
            outfile = OUTPUTS[table.upper()].format(state=state_usps)
            os.makedirs(os.path.dirname(outfile),exist_ok=True)
            pd.concat(data,axis=1).to_csv(outfile,index=True,header=True)

    total = pd.concat(geodata["total"],axis=1)
    heating = pd.concat(geodata["heating"],axis=1)
    cooling = pd.concat(geodata["cooling"],axis=1)
    model = total.sum().sum()/1000

    eia = pd.read_csv("../data/US/eia_electricity_annual.csv",
        skiprows=4,header=0).dropna(subset="source key")
    ndx = [tuple(x.split(".")[2].split("-")) for x in eia["source key"].astype(str).values.tolist()]
    eia["group"] = [x[0] for x in ndx]
    eia["subgroup"] = [x[1] for x in ndx]
    eia.set_index(["group","subgroup"],inplace=True)
    eia.sort_index(inplace=True)
    actual0 = sum([float(eia.loc[state_usps,x]["2018"].values[0]) for x in ["RES","COM"]])
    actual = sum([float(eia.loc[state_usps,x][str(year)].values[0]) for x in ["RES","COM"]])

    result = {x:(pd.concat(y,axis=1)*scalar*actual/model).round(3) for x,y in geodata.items()}
    return result


if __name__ == "__main__":

    print("Processing all US states...",flush=True)
    for state_usps in [states.state_codes_byname[x]["usps"] for x in config.state_list if x in states.state_codes_byname]:

        get_state(state_usps)

    print("Done")
