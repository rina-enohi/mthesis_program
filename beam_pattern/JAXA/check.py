#!python3

import numpy as np
import pandas as pd
import datetime

import matplotlib as mpl
import matplotlib.pyplot as plt
from mpl_toolkits.axes_grid1 import make_axes_locatable

mpl.rcParams.update({'font.size': 14})
mpl.rcParams.update({'axes.facecolor': 'w'})
mpl.rcParams.update({'axes.edgecolor': 'k'})
mpl.rcParams.update({'figure.facecolor': 'w'})
mpl.rcParams.update({'figure.edgecolor': 'w'})
mpl.rcParams.update({'axes.grid': True})
mpl.rcParams.update({'grid.linestyle': ':'})
mpl.rcParams.update({'figure.figsize': [12, 9]})


#DIRNAME = 'images/'

#def get_azel_ant30logdata(filename,linemargin=10,starting_keyword='raster scan timing check'):
def get_azel_ant30logdata(filename,linemargin=10,starting_keyword='trk.cpp-817'):

    ret = {}

    # file reading
    datalines = ''
    with open(filename)as f:
        datalines= f.readlines()
        pass

    # get target-line region
    tmp = np.where([starting_keyword in d for d in datalines])[0]
    lnbgn = tmp[0] - linemargin
    lnend = tmp[-2] + linemargin
    
    # get azel lines
    #dl_ri = np.array([l.replace('\n','').replace(',','').replace('[','').replace(']','').split(' ') for l in datalines[lnbgn:lnend] if 'cmd' in l])
    dl_ri = np.array([l.replace('\n','').replace(',','').replace('[','').replace(']','').split(' ') for l in datalines[lnbgn:lnend] if 'cmd' in l])

    # convert line strings to azel or time
    dt = np.array([datetime.datetime.strptime(' '.join(x.split('-')[:2]),'%Y/%m/%d %H:%M:%S.%f') for x in dl_ri[:,0]])
    ts = np.array([x.timestamp() for x in dt])

    cmdaz = np.array([float(x) for x in dl_ri[:,3]])
    cmdel = np.array([float(x) for x in dl_ri[:,4]])

    acuaz = np.array([float(x) for x in dl_ri[:,8]])
    acuel = np.array([float(x) for x in dl_ri[:,9]])
    
    ret['cmd_az'] = cmdaz
    ret['cmd_el'] = cmdel
    ret['actual_az'] = acuaz
    ret['actual_el'] = acuel
    ret['date'] = dt
    ret['timestamp'] = ts
    ret['fn'] = '.'.join(filename.split('/')[-1].split('.')[:-1])

    # get process time info. for each position moving
    #dl_ri = np.array([l.replace('\n','').replace(',','').replace('[','').replace(']','').split(' ') for l in datalines if 'raster scan timing check' in l])
    #timedelay_dt = np.array([datetime.datetime.strptime(' '.join(x.split('-')[:2]),'%Y/%m/%d %H:%M:%S.%f') for x in dl_ri[:,0]])
    #timedelay = np.array([float(x) for x in dl_ri[:,6]])
    #ret['timedelay'] = timedelay
    #ret['timedelay_dt'] = timedelay_dt
    
    return ret

def get_spadata(filename):
    ret = {}

    spa_pd = pd.read_csv(filename, sep=',', header=None, names=['date','power','psd'])
    ret['date'] = np.array([datetime.datetime.strptime(x,'%Y-%m-%d %H:%M:%S.%f') for x in spa_pd.date])
    ret['timestamp'] = np.array([x.timestamp() for x in ret['date']])
    ret['power'] = 10**(np.array(spa_pd.power)/10)
    ret['psd'] = 10**(np.array(spa_pd.psd)/10)
    ret['fn'] = '.'.join(filename.split('/')[-1].split('.')[:-1])

    return ret

import scipy 
from scipy import stats

def make_binnedarray(tod_az,tod_el,tod_val,az_bins=None,el_bins=None,select=None,statistic='mean'):
    if az_bins is None:
        az_bins = np.linspace(np.min(tod_az),np.max(tod_az),51)
    if el_bins is None:
        el_bins = np.linspace(np.min(tod_el),np.max(tod_el),51)

    if select is not None and np.shape(select) != np.shape(tod_val):
        print(f"ERROR:: Inconsistent array shape btw select ({np.shape(select)}) and tod_val ({np.shape(tod_val)})")
        return None

    x = None
    y = None
    z = None
    if select is None:
        x = tod_az
        y = tod_el
        z = tod_val
    else:
        x = tod_az[select]
        y = tod_el[select]
        z = tod_val[select]
    ret = stats.binned_statistic_2d(x,y,values=z,statistic=statistic,bins=(az_bins,el_bins))

    return ret.statistic.T,az_bins,el_bins



def main(ant30filename,spafilename,step_az,step_el):
    
    ##### data reading
    dict_azel = get_azel_ant30logdata(ant30filename)
    dict_spa  = get_spadata(spafilename)
    
    ##### AZEL plot
    fig,ax = plt.subplots(figsize=(20,8),nrows=2,ncols=2,sharex=True)

    ax[0][0].plot(dict_azel['date'],dict_azel['actual_az'],':.b',label='actual')
    ax[0][0].plot(dict_azel['date'],dict_azel['cmd_az'],':.r',label='command')
    ax[1][0].plot(dict_azel['date'],(dict_azel['cmd_az']-dict_azel['actual_az'])*3600,'.k',label='command-actual')
    ax[0][0].set_ylabel('azimuth [deg]')
    ax[1][0].set_ylabel('daz [arcsec]')
    ax[1][0].set_xlabel('time')
    ax[0][0].legend()
    ax[1][0].legend()
    ax[1][0].set_ylim(-10,10)
    ax[0][0].set_title('azimuth time-ordered-data')
    
    
    ax[0][1].plot(dict_azel['date'],dict_azel['actual_el'],':.b',label='actual')
    ax[0][1].plot(dict_azel['date'],dict_azel['cmd_el'],':.r',label='command')
    ax[1][1].plot(dict_azel['date'],(dict_azel['cmd_el']-dict_azel['actual_el'])*3600,'.k',label='command-actual')
    ax[0][1].set_ylabel('elevation [deg]')
    ax[1][1].set_ylabel('del [arcsec]')
    ax[1][1].set_xlabel('time')
    ax[0][1].legend()
    ax[1][1].legend()
    ax[1][1].set_ylim(-2,2)
    ax[0][1].set_title('elevation time-ordered-data')
    
    fig.tight_layout()
    fig.savefig(dict_azel['fn']+'_azel.png')
    
    ##### AZEL calculation for each SPA data
    
    import scipy
    from scipy import signal
    from scipy import interpolate
    
    f_az = scipy.interpolate.interp1d(dict_azel['timestamp'],dict_azel['actual_az'])
    f_el = scipy.interpolate.interp1d(dict_azel['timestamp'],dict_azel['actual_el'])
    
    ss = np.where((dict_azel['timestamp'][0]<dict_spa['timestamp']) & (dict_spa['timestamp']<dict_azel['timestamp'][-1]))
    
    ret_az = f_az(dict_spa['timestamp'][ss])
    ret_el = f_el(dict_spa['timestamp'][ss])
    ret_data = dict_spa['power'][ss]
    
    ##### SPA data plot
    
    fig,ax = plt.subplots(figsize=(16,5),ncols=2)

    ax[0].plot(ret_az,ret_el,':.b')
    ax[0].set_aspect(1)
    
    ax[0].set_ylabel('elevation [deg]')
    ax[0].set_xlabel('azimuth [deg]')
    #ax[0].legend()
    #ax[0].set_xlim(np.min(acuaz)-(np.max(acuaz)-np.min(acuaz))*0.5,None)
    
    ax[1].plot(dict_spa['date'][ss],np.log10(ret_data)*10,'k')
    ax[1].set_ylabel('power [dBm]')
    ax[1].set_xlabel('time')
    
    fig.tight_layout()
    fig.savefig(dict_spa['fn']+'_tod.png')
    
    ##### SPA map making
    
    from mpl_toolkits.axes_grid1 import make_axes_locatable
    do_colorbar = True
    
    d = np.max(ret_az) - np.min(ret_az)
    az_bins = np.arange(np.min(ret_az)-0.01*d,np.max(ret_az)+0.99*step_az,step_az)
    
    d = np.max(ret_el) - np.min(ret_el)
    el_bins = np.arange(np.min(ret_el)-0.01*d-step_el*0.5,np.max(ret_el)+0.99*step_el,step_el)
    
    fig,ax = plt.subplots(figsize=(16,6),ncols=2)
    
#    z0,_,_ = make_binnedarray(ret_az,ret_el,ret_data,az_bins=az_bins,el_bins=el_bins,statistic='count')
#    im0 = ax[0].imshow(z0,extent=(az_bins[0],az_bins[-1],el_bins[0],el_bins[-1]),
#                       vmax=5,vmin=1,
#                       origin='lower',cmap=mpl.cm.jet,interpolation='none')
    
    z0,_,_ = make_binnedarray(ret_az,ret_el,ret_data,az_bins=az_bins,el_bins=el_bins)
    im0 = ax[0].imshow(z0,vmax=np.nanmax(z0),vmin=np.nanmin(z0),
                   extent=(az_bins[0],az_bins[-1],el_bins[0],el_bins[-1]),
                   origin='lower',cmap=mpl.cm.jet,interpolation='none')
    if do_colorbar:
        divider = make_axes_locatable(ax[0])
        cax = divider.append_axes("right", size="5%", pad=0.1, axes_class=mpl.axes.Axes)
        fig.colorbar(im0, cax=cax)
    
    z1,_,_ = make_binnedarray(ret_az,ret_el,ret_data,az_bins=az_bins,el_bins=el_bins)
    z1dBm = np.log10(z1)*10
    im1 = ax[1].imshow(z1dBm,vmax=np.nanmax(z1dBm),vmin=np.nanmin(z1dBm),
                   extent=(az_bins[0],az_bins[-1],el_bins[0],el_bins[-1]),
                   origin='lower',cmap=mpl.cm.jet,interpolation='none')
    if do_colorbar:
        divider = make_axes_locatable(ax[1])
        cax = divider.append_axes("right", size="5%", pad=0.1, axes_class=mpl.axes.Axes)
        fig.colorbar(im1, cax=cax)
    
    for iax in ax:
        iax.set_aspect(1)
        iax.set_xlabel('AZ [deg]')
        iax.set_ylabel('EL [deg]')
        iax.set_aspect('equal')
    
    ax[0].set_title('SPA power map [mW]')
    ax[1].set_title('SPA power map [dBm]')

    #ax[0].set_xlim(88.8, 90.6) # [mW]
    #ax[1].set_xlim(88.8, 90.6) # [dBm]
    #ax[0].set_ylim(2.65, 3.75) # [mW]
    #ax[1].set_ylim(2.65, 3.75) # [dBm]
    
    fig.tight_layout()
    
    fig.savefig(dict_spa['fn']+'_map.png')

    return

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('ant30filename', help='ant30 logfile name')
    parser.add_argument('spafilename', help='spa file name')
    parser.add_argument('--step_az', help='step azimuth [deg] for map bins',default=0.005,type=float)
    parser.add_argument('--step_el', help='step elevation [deg] for map bins',default=0.25,type=float)
    
    args = parser.parse_args()
    main(args.ant30filename,args.spafilename,args.step_az,args.step_el)