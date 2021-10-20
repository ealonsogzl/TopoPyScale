''''
Retrieve ecmwf data with cdsapi.
J. Fiddes, Origin implementation
S. Filhol adapted in 2021

'''
# !/usr/bin/env python
import pandas as pd
from datetime import datetime
import cdsapi, os, sys
from dateutil.relativedelta import *
import logging
import glob
import subprocess
from multiprocessing.dummy import Pool as ThreadPool

def retrieve_era5(product, startDate, endDate, eraDir, latN, latS, lonE, lonW, step, num_threads=10, surf_plev='surf', plevels=None):
	""" Sets up era5 surface retrieval.
	* Creates list of year/month pairs to iterate through. 
	* MARS retrievals are most efficient when subset by time. 
	* Identifies preexisting downloads if restarted. 
	* Calls api using parallel function.

	Args:
		product: "reanalysis" (HRES) or "ensemble_members" (EDA)
		startDate:
		endDate:
		eraDir: directory to write output
		latN: north latitude of bbox
		latS: south latitude of bbox
		lonE: easterly lon of bbox
		lonW: westerly lon of bbox
		step: timestep to use: 1, 3, 6
		num_threads: number of threads to use for downloading data
		surf_plev: download surface single level or pressure level product: 'surf' or 'plev'

	Returns:
		Monthly era surface files.		 

	"""
	print('\n')
	print('---> Loading ERA5 {} climate forcing'.format(surf_plev))
	bbox = (str(latN) + "/" + str(lonW) + "/" + str(latS) + "/" + str(lonE))
	time_step_dict = {1:['00:00', '01:00', '02:00',
				'03:00', '04:00', '05:00',
				'06:00', '07:00', '08:00',
				'09:00', '10:00', '11:00',
				'12:00', '13:00', '14:00',
				'15:00', '16:00', '17:00',
				'18:00', '19:00', '20:00',
				'21:00', '22:00', '23:00'],
				  3: ['00:00', '03:00', '06:00', '09:00', '12:00', '15:00', '18:00', '21:00'],
				  6: ['00:00', '03:00', '06:00', '09:00', '12:00', '15:00', '18:00', '21:00']}

	df = pd.DataFrame()
	df['dates'] = pd.date_range(startDate, endDate, freq='M')
	df['month'] = df.dates.dt.month
	df['year'] = df.dates.dt.year
	if surf_plev == 'surf':
		df['target_file'] = df.dates.apply(lambda x: eraDir + "SURF_%04d%02d.nc" % (x.year, x.month))
	elif surf_plev == 'plev':
		df['target_file'] = df.dates.apply(lambda x: eraDir + "PLEV_%04d%02d.nc" % (x.year, x.month))
		loc_list = []
		loc_list.extend([plevels]*df.shape[0])
		df['plevels'] = loc_list
	else:
		sys.exit('ERROR: surf_plev can only be surf or plev')
	df['file_exist'] = 0
	df.file_exist = df.target_file.apply(lambda x: os.path.isfile(x)*1)
	df['step'] = step
	df['time_steps'] = df.step.apply(lambda x: time_step_dict.get(x))
	df['bbox'] = bbox
	df['product_type'] = product

	print("Start date = ", df.dates[0])
	print("End date = ", df.dates[len(df.dates) - 1])

	logging.info(("ECWMF {} data found:").format(surf_plev.upper()))
	logging.info(df.target_file.loc[df.file_exist == 1])
	logging.info(("Downloading {} from ECWMF:").format(surf_plev.upper()))
	logging.info(df.target_file.loc[df.file_exist == 0])

	print(("ECWMF {} data found:").format(surf_plev.upper()))
	print(df.target_file.loc[df.file_exist == 1].apply(lambda x: x.split('/')[-1]))
	print(("Downloading {} from ECWMF:").format(surf_plev.upper()))
	print(df.target_file.loc[df.file_exist == 0].apply(lambda x: x.split('/')[-1]))


	download = df.loc[df.file_exist == 0]
	if download.shape[0] > 0:
		ans = input(('---> Download ERA5 {} data? (y/n)').format(surf_plev.upper()))
		if (ans.lower() == 'y') or (ans == '1'):
			if surf_plev == 'surf':
				pool = ThreadPool(num_threads)
				pool.starmap(era5_request_surf, zip(list(download.year),
													list(download.month),
													list(download.bbox),
													list(download.target_file),
													list(download.product_type),
													list(download.time_steps)))
				pool.close()
				pool.join()
			elif surf_plev == 'plev':
				pool = ThreadPool(num_threads)
				pool.starmap(era5_request_plev, zip(list(download.year),
													list(download.month),
													list(download.bbox),
													list(download.target_file),
													list(download.product_type),
													list(download.time_steps),
													list(download.plevels)))
				pool.close()
				pool.join()
			else:
				sys.exit('ERROR: surf_plev can only be surf or plev')
		else:
			sys.exit('ERROR: Some forcing files are missing given the date range provided\n ---> or implement a method to modify start/end date of project to file available')

def era5_request_surf(year, month, bbox, target, product, time):
	"""CDS surface api call"""
	c = cdsapi.Client()
	c.retrieve(
		'reanalysis-era5-single-levels',
		{'variable': ['geopotential', '2m_dewpoint_temperature', 'surface_thermal_radiation_downwards',
					  'surface_solar_radiation_downwards',
					  'Total precipitation', '2m_temperature', 'TOA incident solar radiation',
					  'friction_velocity', 'instantaneous_moisture_flux', 'instantaneous_surface_sensible_heat_flux'
					  ],
		 'product_type': product,
		 "area": bbox,
		 'year': year,
		 'month': month,
		 'day': ['01', '02', '03',
				 '04', '05', '06',
				 '07', '08', '09',
				 '10', '11', '12',
				 '13', '14', '15',
				 '16', '17', '18',
				 '19', '20', '21',
				 '22', '23', '24',
				 '25', '26', '27',
				 '28', '29', '30',
				 '31'
				 ],
		 'time': time,
		 'grid': [0.25, 0.25],
		 'format': 'netcdf'
		 },
		target)
	print(target + " complete")

def era5_request_plev(year, month, bbox, target, product, time, plevels):
	"""CDS plevel api call"""
	c = cdsapi.Client()
	c.retrieve(
		'reanalysis-era5-pressure-levels',
		{
			'product_type': product,
			'format': 'netcdf',
			"area": bbox,
			'variable': [
				'geopotential', 'temperature', 'u_component_of_wind',
				'v_component_of_wind', 'relative_humidity', 'specific_humidity'
			],
			'pressure_level': plevels,
			'year': year,
			'month': month,
			'day': [
				'01', '02', '03',
				'04', '05', '06',
				'07', '08', '09',
				'10', '11', '12',
				'13', '14', '15',
				'16', '17', '18',
				'19', '20', '21',
				'22', '23', '24',
				'25', '26', '27',
				'28', '29', '30',
				'31'
			],
			'time': time,
			'grid': [0.25, 0.25],
		},
		target)
	print(target + " complete")


def eraCat(wd, grepStr):
	"""
	*** CDO ***
	Concats monthly era (interim or 5) files by some keyword *grepStr*. Depends on CDO.
	- reads monthly ERA5 data files (MARS efficiency)
	- concats to single file timeseries

	Syntax: cdo -b F64 -f nc2 mergetime SURF* SURF.nc

	Args:
		wd: directory of era monthly datafiles
		grepStr: "PLEV" or "SURF"
	Example:
		wd=/home/eraDat/
		grepStr= "PLEV"
		eraCat("/home/joel/mnt/myserver/sim/wfj_era5/eraDat/", "PLEV")
	"""

	cmd = ("cdo -b F64 -f nc2 mergetime " + wd + grepStr + "* " + wd + "/" + grepStr + ".nc")
	subprocess.check_output(cmd, shell="TRUE")

def eraCat5d(wd, grepStr):
	"""
	*** NCO ***
	Updated method to deal with 5D of ensemble datasets NOT supported by CDO
	Concats monthly era (interim or 5) files by some keyword *grepStr*. Depends on NCO.
	sudo apt-get install nco
	- reads monthly ERA5 data files (MARS efficiency)
	- concats to single file timeseries
	- 2 steps 
		- assign time to "record" dimeanion in firstfile
		- concat files

	Args:
		wd: directory of era monthly datafiles
		grepStr: "PLEV" or "SURF"
	Example:
		wd=/home/eraDat/
		grepStr= "PLEV"
		eraCat("/home/joel/mnt/myserver/sim/wfj_era5/eraDat/", "PLEV")
	"""

	lst = glob.glob(wd + grepStr + '*')
	lst.sort()

	firstfile = lst[0]
	cmd = ("ncks -O --mk_rec_dmn time " + firstfile + " " + firstfile)
	subprocess.check_output(cmd, shell="TRUE")

	cmd = ("ncrcat " + grepStr + "*" + " " + grepStr + ".nc")
	subprocess.check_output(cmd, shell="TRUE")


def retrieve_era5_tpmm(startDate, endDate, eraDir, latN, latS, lonE, lonW):
	"""
	retrieve monthly tp means to correct 6 or 3h TP retrieval
	documented era5 here: https://confluence.ecmwf.int/display/CKB/ERA5+data+documentation#ERA5datadocumentation-Monthlymeans
	values are mean daily for that month, weight by number of days in month eg annualtotal = sum(wfj_m*c(31,28,31,30,31,30,31,31,30,31,30,31))
	"""
	# eraDir='/home/joel/sim/imis/forcing/'
	# latN=47.9
	# latS=45.75
	# lonW=5.7
	# lonE=10.6

	# startDate = '1979-09-01'    # adjust to your requirements - as of 2017-07 only 2010-01-01 onwards is available
	# endDate = '2018-09-01'
	param = 'total_precipitation'  # adjust to your requirements
	months = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
	dates = [str(startDate), str(endDate)]
	start = datetime.strptime(dates[0], "%Y-%m-%d")
	end = datetime.strptime(dates[1], "%Y-%m-%d")
	start = start + relativedelta(months=-1)
	end = end + relativedelta(months=+1)
	# dateList = OrderedDict(((start + timedelta(_)).strftime(r"%Y-%m"), None) for _ in xrange((end - start).days)).keys()
	dateList = pd.date_range(start, end, freq='D')

	# target = eraDir + "tp_%04d%02d.nc" % (startDate, endDate)
	target = eraDir + "tpmm.nc"
	bbox = (str(latN) + "/" + str(lonW) + "/" + str(latS) + "/" + str(lonE))

	yearVec = []
	for date in dateList:
		# strsplit = date.split('-' )
		# year =  int(strsplit[0])
		yearVec.append(date.year)

	myyears = list(sorted(set(yearVec)))

	c = cdsapi.Client()

	c.retrieve(
		'reanalysis-era5-single-levels-monthly-means',
		{
			'product_type': 'reanalysis-monthly-means-of-daily-means',
			'area': bbox,
			'variable': param,
			'year': myyears,
			'month': [
				'01', '02', '03',
				'04', '05', '06',
				'07', '08', '09',
				'10', '11', '12'
			],
			'time': '00:00',
			'format': 'netcdf'
		},
		target)