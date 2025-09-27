This repository contain load data for every county in the US.  

# Data structure

Data is organized by state in geodata panels for the following

* Weather
  * `solar.csv`
  * `temperature.csv`
  * `wind.csv`

* Load
  * `cooling.csv`
  * `heating.csv`
  * `total.csv`

Geodata panels are organized by timestamps in rows and geohashes in columns. The county geohash can be obtained from the `counties.csv` file.

# Getting data

To read the load data for a state, e.g., California, use the following 

	from makedata import get_state
	data = get_state("CA")

The result will be a dict with the weather and load data in separate dataframes, with
time in rows, and county geodata in columns.

You can scale the load to any particular year in the EIA annual energy file using the command:

	data = get_state("CA",year=2022)

In addition, you can apply your own load growth relative to a particular year, e.g., 7% higher than 2024:

	data = get_state("CA",year=2024,scalar=1.07)

