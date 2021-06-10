import pkg_resources
##figure out where the big fits files are in this installation
datapath = pkg_resources.resource_filename('Comove','resources')
import math as math
import numpy as np
import matplotlib.pyplot as plt
import astropy.units as u
from astroquery.gaia import Gaia
from astroquery.simbad import Simbad
from astropy.coordinates import SkyCoord
from astropy import coordinates
from astropy.coordinates import ICRS
from astroquery.gaia import Gaia
from astroquery.exceptions import NoResultsWarning
import galpy.util.bovy_coords as bc
import matplotlib.pyplot as plt
from matplotlib import cm
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import matplotlib.ticker as mticker
from astroquery.mast import Catalogs
from astroquery.irsa import Irsa
Irsa.TIMEOUT = 600
from astropy.coordinates import SkyCoord
from scipy.interpolate import interp1d
from scipy.io.idl import readsav
from astroquery.vizier import Vizier
Vizier.TIMEOUT = 600
import os,warnings
import csv
import matplotlib as mpl
mpl.rcParams['lines.linewidth']   = 2
mpl.rcParams['axes.linewidth']    = 2
mpl.rcParams['xtick.major.width'] =2
mpl.rcParams['ytick.major.width'] =2
mpl.rcParams['ytick.labelsize'] = 10
mpl.rcParams['xtick.labelsize'] = 10
mpl.rcParams['axes.labelsize'] = 14
mpl.rcParams['legend.numpoints'] = 1
mpl.rcParams['axes.labelweight']='semibold'
mpl.rcParams['axes.titlesize']=9
mpl.rcParams['axes.titleweight']='semibold'
mpl.rcParams['font.weight'] = 'semibold'


def findfriends(targname,radial_velocity,velocity_limit=5.0,search_radius=25.0,rvcut=5.0,radec=[None,None],output_directory = None,showplots=False,verbose=False,DoGALEX=True,DoWISE=True,DoROSAT=True):
    
    radvel= radial_velocity * u.kilometer / u.second
    
    if output_directory == None:
        outdir = './' + targname.replace(" ", "") + '_friends/'
    else: 
        outdir = output_directory
    if os.path.isdir(outdir) == True:
        print('Output directory ' + outdir +' Already Exists!!')
        print('Either Move it, Delete it, or input a different [output_directory] Please!')
        return
    os.mkdir(outdir)
    
    if velocity_limit < 0.00001 : 
        print('input velocity_limit is too small, try something else')
        print('velocity_limit: ' + str(velocity_limit))
    if search_radius < 0.0000001:
        print('input search_radius is too small, try something else')
        print('search_radius: ' + str(search_radius))
     
    # Search parameters
    vlim=velocity_limit * u.kilometer / u.second
    searchradpc=search_radius * u.parsec

    if (radec[0] != None) & (radec[1] != None):
        usera,usedec = radec[0],radec[1]
    else:  ##use the target name to get simbad ra and dec.
        print('Asking Simbad for RA and DEC')
        result_table = Simbad.query_object(targname)
        usera,usedec = result_table['RA'][0],result_table['DEC'][0]
    
    if verbose == True:
        print('Target name: ',targname)
        print('Coordinates: ' + str(usera) +' '+str(usedec))
        print()

    c = SkyCoord( ra=usera , dec=usedec , unit=(u.hourangle, u.deg) , frame='icrs')
    if verbose == True: print(c)

    # Find precise coordinates and distance from Gaia, define search radius and parallax cutoff
    print('Asking Gaia for precise coordinates')
    sqltext = "SELECT * FROM gaiaedr3.gaia_source WHERE CONTAINS( \
               POINT('ICRS',gaiaedr3.gaia_source.ra,gaiaedr3.gaia_source.dec), \
               CIRCLE('ICRS'," + str(c.ra.value) +","+ str(c.dec.value) +","+ str(6.0/3600.0) +"))=1;"
    job = Gaia.launch_job_async(sqltext , dump_to_file=False)
    Pgaia = job.get_results()
    if verbose == True:
        print(sqltext)
        print()
        print(Pgaia['source_id','ra','dec','phot_g_mean_mag','parallax','ruwe'].pprint_all())
        print()

    minpos = Pgaia['phot_g_mean_mag'].tolist().index(min(Pgaia['phot_g_mean_mag']))
    Pcoord = SkyCoord( ra=Pgaia['ra'][minpos]*u.deg , dec=Pgaia['dec'][minpos]*u.deg , \
                      distance=(1000.0/Pgaia['parallax'][minpos])*u.parsec , frame='icrs' , \
                      radial_velocity=radvel , \
                      pm_ra_cosdec=Pgaia['pmra'][minpos]*u.mas/u.year , pm_dec=Pgaia['pmdec'][minpos]*u.mas/u.year )

    searchraddeg = np.arcsin(searchradpc/Pcoord.distance).to(u.deg)
    minpar = (1000.0 * u.parsec) / (Pcoord.distance + searchradpc) * u.mas
    if verbose == True:
        print(Pcoord)
        print()
        print('Search radius in deg: ',searchraddeg)
        print('Minimum parallax: ',minpar)


    # Query Gaia with search radius and parallax cut
    # Note, a cut on parallax_error was added because searches at low galactic latitude 
    # return an overwhelming number of noisy sources that scatter into the search volume - ALK 20210325
    print('Querying Gaia for neighbors')

    Pllbb     = bc.radec_to_lb(Pcoord.ra.value , Pcoord.dec.value , degree=True)
    if ( np.abs(Pllbb[1]) > 10.0): plxcut = max( 0.5 , (1000.0/Pcoord.distance.value/10.0) )
    else: plxcut = 0.5
    print('Parallax cut: ',plxcut)

    if (searchradpc < Pcoord.distance):
        sqltext = "SELECT * FROM gaiaedr3.gaia_source WHERE CONTAINS( \
            POINT('ICRS',gaiaedr3.gaia_source.ra,gaiaedr3.gaia_source.dec), \
            CIRCLE('ICRS'," + str(Pcoord.ra.value) +","+ str(Pcoord.dec.value) +","+ str(searchraddeg.value) +"))\
            =1 AND parallax>" + str(minpar.value) + " AND parallax_error<" + str(plxcut) + ";"
    if (searchradpc >= Pcoord.distance):
        sqltext = "SELECT * FROM gaiaedr3.gaia_source WHERE parallax>" + str(minpar.value) + " AND parallax_error<" + str(plxcut) + ";"
        print('Note, using all-sky search')
    if verbose == True:
        print(sqltext)
        print()

    job = Gaia.launch_job_async(sqltext , dump_to_file=False)
    r = job.get_results()
   
    if verbose == True: print('Number of records: ',len(r['ra']))


    # Construct coordinates array for all stars returned in cone search

    gaiacoord = SkyCoord( ra=r['ra'] , dec=r['dec'] , distance=(1000.0/r['parallax'])*u.parsec , \
                         frame='icrs' , \
                         pm_ra_cosdec=r['pmra'] , pm_dec=r['pmdec'] )

    sep = gaiacoord.separation(Pcoord)
    sep3d = gaiacoord.separation_3d(Pcoord)

    if verbose == True:
        print('Printing angular separations in degrees as sanity check')
        print(sep.degree)



    Pllbb     = bc.radec_to_lb(Pcoord.ra.value , Pcoord.dec.value , degree=True)
    Ppmllpmbb = bc.pmrapmdec_to_pmllpmbb( Pcoord.pm_ra_cosdec.value , Pcoord.pm_dec.value , \
                                         Pcoord.ra.value , Pcoord.dec.value , degree=True )
    Pvxvyvz   = bc.vrpmllpmbb_to_vxvyvz(Pcoord.radial_velocity.value , Ppmllpmbb[0] , Ppmllpmbb[1] , \
                                   Pllbb[0] , Pllbb[1] , Pcoord.distance.value/1000.0 , XYZ=False , degree=True)

    if verbose == True:
        print('Science Target Name: ',targname)
        print('Science Target RA/DEC: ',Pcoord.ra.value,Pcoord.dec.value)
        print('Science Target Galactic Coordinates: ',Pllbb)
        print('Science Target UVW: ',Pvxvyvz)
        print()

    Gllbb = bc.radec_to_lb(gaiacoord.ra.value , gaiacoord.dec.value , degree=True)
    Gxyz = bc.lbd_to_XYZ( Gllbb[:,0] , Gllbb[:,1] , gaiacoord.distance/1000.0 , degree=True)
    Gvrpmllpmbb = bc.vxvyvz_to_vrpmllpmbb( \
                    Pvxvyvz[0]*np.ones(len(Gxyz[:,0])) , Pvxvyvz[1]*np.ones(len(Gxyz[:,1])) , Pvxvyvz[2]*np.ones(len(Gxyz[:,2])) , \
                    Gxyz[:,0] , Gxyz[:,1] , Gxyz[:,2] , XYZ=True)
    Gpmrapmdec = bc.pmllpmbb_to_pmrapmdec( Gvrpmllpmbb[:,1] , Gvrpmllpmbb[:,2] , Gllbb[:,0] , Gllbb[:,1] , degree=True)

    # Code in case I want to do chi^2 cuts someday
    Gvtanerr = 1.0 * np.ones(len(Gxyz[:,0]))
    Gpmerr = Gvtanerr * 206265000.0 * 3.154e7 / (gaiacoord.distance.value * 3.086e13)


    Gchi2 = ( (Gpmrapmdec[:,0]-gaiacoord.pm_ra_cosdec.value)**2 + (Gpmrapmdec[:,1]-gaiacoord.pm_dec.value)**2 )**0.5
    Gchi2 = Gchi2 / Gpmerr
    if verbose == True:
        print('Predicted PMs if comoving:')
        print(Gpmrapmdec , "\n")
        print('Actual PMRAs from Gaia:')
        print(gaiacoord.pm_ra_cosdec.value , "\n")
        print('Actual PMDECs from Gaia:')
        print(gaiacoord.pm_dec.value , "\n")
        print('Predicted PM errors:')
        print(Gpmerr , "\n")
        print('Chi^2 values:')
        print(Gchi2)


    # Query external list(s) of RVs

    zz = np.where( (sep3d.value < searchradpc.value) & (Gchi2 < vlim.value) )
    yy = zz[0][np.argsort(sep3d[zz])]
    
    RV    = np.empty(np.array(r['ra']).size)
    RVerr = np.empty(np.array(r['ra']).size)
    RVsrc = np.array([ '                             None' for x in range(np.array(r['ra']).size) ])
    RV[:]    = np.nan
    RVerr[:] = np.nan

    print('Populating RV table')
    for x in range(0 , np.array(yy).size):
        if np.isnan(r['dr2_radial_velocity'][yy[x]]) == False:        # First copy over DR2 RVs
            RV[yy[x]]    = r['dr2_radial_velocity'][yy[x]]
            RVerr[yy[x]] = r['dr2_radial_velocity_error'][yy[x]]
            RVsrc[yy[x]] = 'Gaia DR2'
    if os.path.isfile('LocalRV.csv'):
        with open('LocalRV.csv') as csvfile:                          # Now check for a local RV that would supercede
            readCSV = csv.reader(csvfile, delimiter=',')
            for row in readCSV:
                ww = np.where(r['designation'] == row[0])[0]
                if (np.array(ww).size == 1):
                    RV[ww]    = row[2]
                    RVerr[ww] = row[3]
                    RVsrc[ww] = row[4]
                    if verbose == True: 
                        print('Using stored RV: ',row)
                        print(r['ra','dec','phot_g_mean_mag'][ww])
                        print(RV[ww])
                        print(RVerr[ww])
                        print(RVsrc[ww])



    # Create Gaia CMD plot

    mamajek  = np.loadtxt(datapath+'/sptGBpRp.txt')
    pleiades = np.loadtxt(datapath+'/PleGBpRp.txt')
    tuchor   = np.loadtxt(datapath+'/TucGBpRp.txt')
    usco     = np.loadtxt(datapath+'/UScGBpRp.txt')
    chai     = np.loadtxt(datapath+'/ChaGBpRp.txt')

    zz = np.where( (sep3d.value < searchradpc.value) & (Gchi2 < vlim.value) & (np.isnan(r['bp_rp']) == False) ) # Note, this causes an error because NaNs
    yy = zz[0][np.argsort(sep3d[zz])]
    zz2= np.where( (sep3d.value < searchradpc.value) & (Gchi2 < vlim.value) & (sep.degree > 0.00001) & \
                 (r['phot_bp_rp_excess_factor'] < (1.3 + 0.06*r['bp_rp']**2)) & \
                 (np.isnan(r['bp_rp']) == False) )                                                              # Note, this causes an error because NaNs
    yy2= zz2[0][np.argsort((-Gchi2)[zz2])]


    figname=outdir + targname.replace(" ", "") + "cmd.png"
    if verbose == True: print(figname)

    fig,ax1 = plt.subplots(figsize=(12,8))

    ax1.axis([ math.floor(min(r['bp_rp'][zz])) , \
               math.ceil(max(r['bp_rp'][zz])), \
               math.ceil(max((r['phot_g_mean_mag'][zz] - (5.0*np.log10(gaiacoord.distance[zz].value)-5.0))))+1, \
               math.floor(min((r['phot_g_mean_mag'][zz] - (5.0*np.log10(gaiacoord.distance[zz].value)-5.0))))-1 ] )
    ax1.set_xlabel(r'$B_p-R_p$ (mag)' , fontsize=16)
    ax1.set_ylabel(r'$M_G$ (mag)' , fontsize=16)
    ax1.tick_params(axis='both',which='major',labelsize=12)

    ax2 = ax1.twiny()
    ax2.set_xlim(ax1.get_xlim())
    spttickvals = np.array([ -0.037 , 0.377 , 0.782 , 0.980 , 1.84 , 2.50 , 3.36 , 4.75 ])
    sptticklabs = np.array([ 'A0' , 'F0' , 'G0' , 'K0' , 'M0' , 'M3' , 'M5' , 'M7' ])
    xx = np.where( (spttickvals >= math.floor(min(r['bp_rp'][zz]))) & (spttickvals <= math.ceil(max(r['bp_rp'][zz]))) )[0]
    ax2.set_xticks(spttickvals[xx])
    ax2.set_xticklabels( sptticklabs[xx] )
    ax2.set_xlabel('SpT' , fontsize=16, labelpad=15)
    ax2.tick_params(axis='both',which='major',labelsize=12)

    ax1.plot(    chai[:,1] ,     chai[:,0]  , zorder=1 , label='Cha-I (0-5 Myr)')
    ax1.plot(    usco[:,1] ,     usco[:,0]  , zorder=2 , label='USco (11 Myr)')
    ax1.plot(  tuchor[:,1] ,   tuchor[:,0]  , zorder=3 , label='Tuc-Hor (40 Myr)')
    ax1.plot(pleiades[:,1] , pleiades[:,0]  , zorder=4 , label='Pleiades (125 Myr)')
    ax1.plot( mamajek[:,2] ,  mamajek[:,1]  , zorder=5 , label='Mamajek MS')

    for x in range(0 , np.array(yy2).size):
        msize  = (17-12.0*(sep3d[yy2[x]].value/searchradpc.value))**2
        mcolor = Gchi2[yy2[x]]
        medge  = 'black'
        mzorder= 7
        if (r['ruwe'][yy2[x]] < 1.2):
            mshape='o'
        if (r['ruwe'][yy2[x]] >= 1.2):
            mshape='s'
        if (np.isnan(rvcut) == False): 
            if (np.isnan(RV[yy2[x]])==False) & (np.abs(RV[yy2[x]]-Gvrpmllpmbb[yy2[x],0]) > rvcut):
                mshape='+'
                mcolor='black'
                mzorder=6
            if (np.isnan(RV[yy2[x]])==False) & (np.abs(RV[yy2[x]]-Gvrpmllpmbb[yy2[x],0]) <= rvcut):
                medge='blue'

        ccc = ax1.scatter(r['bp_rp'][yy2[x]] , (r['phot_g_mean_mag'][yy2[x]] - (5.0*np.log10(gaiacoord.distance[yy2[x]].value)-5.0)) , \
                s=msize , c=mcolor , marker=mshape , edgecolors=medge , zorder=mzorder , \
                vmin=0.0 , vmax=vlim.value , cmap='cubehelix' , label='_nolabel' )

    temp1 = ax1.scatter([] , [] , c='white' , edgecolors='black', marker='o' , s=12**2 , label = 'RUWE < 1.2')
    temp2 = ax1.scatter([] , [] , c='white' , edgecolors='black', marker='s' , s=12**2 , label = 'RUWE >= 1.2')
    temp3 = ax1.scatter([] , [] , c='white' , edgecolors='blue' , marker='o' , s=12**2 , label = 'RV Comoving')
    temp4 = ax1.scatter([] , [] , c='black' , marker='+' , s=12**2 , label = 'RV Outlier')

    ax1.plot(r['bp_rp'][yy[0]] , (r['phot_g_mean_mag'][yy[0]] - (5.0*np.log10(gaiacoord.distance[yy[0]].value)-5.0)) , \
             'rx' , markersize=18 , mew=3 , markeredgecolor='red' , zorder=10 , label=targname)

    ax1.arrow( 1.3 , 2.5 , 0.374, 0.743 , length_includes_head=True , head_width=0.07 , head_length = 0.10 )
    ax1.text(  1.4 , 2.3, r'$A_V=1$' , fontsize=12)



    ax1.legend(fontsize=11)
    cb = plt.colorbar(ccc , ax=ax1)
    cb.set_label(label='Velocity Difference (km/s)',fontsize=14)
    plt.savefig(figname , bbox_inches='tight', pad_inches=0.2 , dpi=200)
    if showplots == True: plt.show()
    plt.close('all')


    # Create PM plot


    zz2= np.where( (sep3d.value < searchradpc.value) & (Gchi2 < vlim.value) & (sep.degree > 0.00001) )
    yy2= zz2[0][np.argsort((-Gchi2)[zz2])]
    zz3= np.where( (sep3d.value < searchradpc.value) & (sep.degree > 0.00001) )

    figname=outdir + targname.replace(" ", "") + "pmd.png"

    fig,ax1 = plt.subplots(figsize=(12,8))

    ax1.axis([ (max(r['pmra'][zz2]) + 0.05*np.ptp(r['pmra'][zz2]) ) , \
           (min(r['pmra'][zz2]) - 0.05*np.ptp(r['pmra'][zz2]) ) , \
           (min(r['pmdec'][zz2])- 0.05*np.ptp(r['pmra'][zz2]) ) , \
           (max(r['pmdec'][zz2])+ 0.05*np.ptp(r['pmra'][zz2]) ) ] )
    ax1.tick_params(axis='both',which='major',labelsize=16)

    if  ((max(r['pmra'][zz2]) + 0.05*np.ptp(r['pmra'][zz2])) > 0.0) & \
            ((min(r['pmra'][zz2]) - 0.05*np.ptp(r['pmra'][zz2])) < 0.0) & \
            ((min(r['pmdec'][zz2])- 0.05*np.ptp(r['pmra'][zz2])) < 0.0) & \
            ((max(r['pmdec'][zz2])+ 0.05*np.ptp(r['pmra'][zz2])) > 0.0):
        ax1.plot( [0.0,0.0] , [-1000.0,1000.0] , 'k--' , linewidth=1 )
        ax1.plot( [-1000.0,1000.0] , [0.0,0.0] , 'k--' , linewidth=1 )

    ax1.errorbar( (r['pmra'][yy2]) , (r['pmdec'][yy2]) , \
            yerr=(r['pmdec_error'][yy2]) , xerr=(r['pmra_error'][yy2]) , fmt='none' , ecolor='k' )

    ax1.scatter( (r['pmra'][zz3]) , (r['pmdec'][zz3]) , \
              s=(0.5)**2 , marker='o' , c='black' , zorder=2 , label='Field' )

    for x in range(0 , np.array(yy2).size):
        msize  = (17-12.0*(sep3d[yy2[x]].value/searchradpc.value))**2
        mcolor = Gchi2[yy2[x]]
        medge  = 'black'
        mzorder= 7
        if (r['ruwe'][yy2[x]] < 1.2):
            mshape='o'
        if (r['ruwe'][yy2[x]] >= 1.2):
            mshape='s'
        if (np.isnan(rvcut) == False): 
            if (np.isnan(RV[yy2[x]])==False) & (np.abs(RV[yy2[x]]-Gvrpmllpmbb[yy2[x],0]) > rvcut):
                mshape='+'
                mcolor='black'
                mzorder=6
            if (np.isnan(RV[yy2[x]])==False) & (np.abs(RV[yy2[x]]-Gvrpmllpmbb[yy2[x],0]) <= rvcut):
                medge='blue'
        ccc = ax1.scatter(r['pmra'][yy2[x]] , r['pmdec'][yy2[x]] , \
                s=msize , c=mcolor , marker=mshape , edgecolors=medge , zorder=mzorder , \
                vmin=0.0 , vmax=vlim.value , cmap='cubehelix' , label='_nolabel' )

    temp1 = ax1.scatter([] , [] , c='white' , edgecolors='black', marker='o' , s=12**2 , label = 'RUWE < 1.2')
    temp2 = ax1.scatter([] , [] , c='white' , edgecolors='black', marker='s' , s=12**2 , label = 'RUWE >= 1.2')
    temp3 = ax1.scatter([] , [] , c='white' , edgecolors='blue' , marker='o' , s=12**2 , label = 'RV Comoving')
    temp4 = ax1.scatter([] , [] , c='black' , marker='+' , s=12**2 , label = 'RV Outlier')

    ax1.plot( Pgaia['pmra'][minpos] , Pgaia['pmdec'][minpos] , \
         'rx' , markersize=18 , mew=3 , markeredgecolor='red' , zorder=3 , label=targname)

    ax1.set_xlabel(r'$\mu_{RA}$ (mas/yr)' , fontsize=22 , labelpad=10)
    ax1.set_ylabel(r'$\mu_{DEC}$ (mas/yr)' , fontsize=22 , labelpad=10)
    ax1.legend(fontsize=12)

    cb = plt.colorbar(ccc , ax=ax1)
    cb.set_label(label='Tangential Velocity Difference (km/s)',fontsize=18 , labelpad=10)
    plt.savefig(figname , bbox_inches='tight', pad_inches=0.2 , dpi=200)
    if showplots == True: plt.show()
    plt.close('all')


    # Create RV plot

    zz2= np.where( (sep3d.value < searchradpc.value) & (Gchi2 < vlim.value) & (sep.degree > 0.00001) & \
             (np.isnan(RV) == False) )
    yy2= zz2[0][np.argsort((-Gchi2)[zz2])]

    zz3= np.where( (sep3d.value < searchradpc.value) & (Gchi2 < vlim.value) & (sep.degree > 0.00001) & \
             (np.isnan(RV) == False) & (np.isnan(r['phot_g_mean_mag']) == False) & \
             (np.abs(RV-Gvrpmllpmbb[:,0]) < 20.0) ) # Just to set Y axis

    fig,ax1 = plt.subplots(figsize=(12,8))
    ax1.axis([ -20.0 , +20.0, \
           max( np.append( np.array(r['phot_g_mean_mag'][zz3] - (5.0*np.log10(gaiacoord.distance[zz3].value)-5.0)) ,  0.0 )) + 0.3 , \
           min( np.append( np.array(r['phot_g_mean_mag'][zz3] - (5.0*np.log10(gaiacoord.distance[zz3].value)-5.0)) , 15.0 )) - 0.3   ])
    ax1.tick_params(axis='both',which='major',labelsize=16)

    ax1.plot( [0.0,0.0] , [-20.0,25.0] , 'k--' , linewidth=1 )

    ax1.errorbar( (RV[yy2]-Gvrpmllpmbb[yy2,0]) , \
           (r['phot_g_mean_mag'][yy2] - (5.0*np.log10(gaiacoord.distance[yy2].value)-5.0)) , \
            yerr=None,xerr=(RVerr[yy2]) , fmt='none' , ecolor='k' )

    for x in range(0 , np.array(yy2).size):
        msize  = (17-12.0*(sep3d[yy2[x]].value/searchradpc.value))**2
        mcolor = Gchi2[yy2[x]]
        medge  = 'black'
        mzorder= 2
        if (r['ruwe'][yy2[x]] < 1.2):
            mshape='o'
        if (r['ruwe'][yy2[x]] >= 1.2):
            mshape='s'
        ccc = ax1.scatter( (RV[yy2[x]]-Gvrpmllpmbb[yy2[x],0]) , \
                (r['phot_g_mean_mag'][yy2[x]] - (5.0*np.log10(gaiacoord.distance[yy2[x]].value)-5.0)) , \
                s=msize , c=mcolor , marker=mshape , edgecolors=medge , zorder=mzorder , \
                vmin=0.0 , vmax=vlim.value , cmap='cubehelix' , label='_nolabel' )

    temp1 = ax1.scatter([] , [] , c='white' , edgecolors='black', marker='o' , s=12**2 , label = 'RUWE < 1.2')
    temp2 = ax1.scatter([] , [] , c='white' , edgecolors='black', marker='s' , s=12**2 , label = 'RUWE >= 1.2')
    temp3 = ax1.scatter([] , [] , c='white' , edgecolors='blue' , marker='o' , s=12**2 , label = 'RV Comoving')

    if ( (Pgaia['phot_g_mean_mag'][minpos] - (5.0*np.log10(Pcoord.distance.value)-5.0)) < \
                                     (max( np.append( np.array(r['phot_g_mean_mag'][zz3] - (5.0*np.log10(gaiacoord.distance[zz3].value)-5.0)) , 0.0 )) + 0.3) ):
        ax1.plot( [0.0] , (Pgaia['phot_g_mean_mag'][minpos] - (5.0*np.log10(Pcoord.distance.value)-5.0)) , \
                  'rx' , markersize=18 , mew=3 , markeredgecolor='red' , zorder=3 , label=targname)


    ax1.set_ylabel(r'$M_G$ (mag)' , fontsize=22 , labelpad=10)
    ax1.set_xlabel(r'$v_{r,obs}-v_{r,pred}$ (km/s)' , fontsize=22 , labelpad=10)
    ax1.legend(fontsize=12)

    cb = plt.colorbar(ccc , ax=ax1)
    cb.set_label(label='Tangential Velocity Difference (km/s)',fontsize=18 , labelpad=10)

    figname=outdir + targname.replace(" ", "") + "drv.png"
    plt.savefig(figname , bbox_inches='tight', pad_inches=0.2 , dpi=200)
    if showplots == True: plt.show()
    plt.close('all')



    
    # Create XYZ plot

    Pxyz = bc.lbd_to_XYZ( Pllbb[0] , Pllbb[1] , Pcoord.distance.value/1000.0 , degree=True)

    fig,axs = plt.subplots(2,2)
    fig.set_figheight(16)
    fig.set_figwidth(16)
    fig.subplots_adjust(hspace=0.03,wspace=0.03)

    zz2= np.where( (sep3d.value < searchradpc.value) & (Gchi2 < vlim.value) & (sep.degree > 0.00001) )
    yy2= zz2[0][np.argsort((-Gchi2)[zz2])]

    for x in range(0 , np.array(yy2).size):
        msize  = (17-12.0*(sep3d[yy2[x]].value/searchradpc.value))**2
        mcolor = Gchi2[yy2[x]]
        medge  = 'black'
        mzorder= 3
        if (r['ruwe'][yy2[x]] < 1.2):
            mshape='o'
        if (r['ruwe'][yy2[x]] >= 1.2):
            mshape='s'
        if (np.isnan(rvcut) == False): 
            if (np.isnan(RV[yy2[x]])==False) & (np.abs(RV[yy2[x]]-Gvrpmllpmbb[yy2[x],0]) > rvcut):
                mshape='+'
                mcolor='black'
                mzorder=2
            if (np.isnan(RV[yy2[x]])==False) & (np.abs(RV[yy2[x]]-Gvrpmllpmbb[yy2[x],0]) <= rvcut):
                medge='blue'
        ccc = axs[0,0].scatter( 1000.0*Gxyz[yy2[x],0] , 1000.0*Gxyz[yy2[x],1] , \
                s=msize , c=mcolor , marker=mshape , edgecolors=medge , zorder=mzorder , \
                vmin=0.0 , vmax=vlim.value , cmap='cubehelix' , label='_nolabel' )
        ccc = axs[0,1].scatter( 1000.0*Gxyz[yy2[x],2] , 1000.0*Gxyz[yy2[x],1] , \
                s=msize , c=mcolor , marker=mshape , edgecolors=medge , zorder=mzorder , \
                vmin=0.0 , vmax=vlim.value , cmap='cubehelix' , label='_nolabel' )
        ccc = axs[1,0].scatter( 1000.0*Gxyz[yy2[x],0] , 1000.0*Gxyz[yy2[x],2] , \
                s=msize , c=mcolor , marker=mshape , edgecolors=medge , zorder=mzorder , \
                vmin=0.0 , vmax=vlim.value , cmap='cubehelix' , label='_nolabel' )

    temp1 = axs[0,0].scatter([] , [] , c='white' , edgecolors='black', marker='o' , s=12**2 , label = 'RUWE < 1.2')
    temp2 = axs[0,0].scatter([] , [] , c='white' , edgecolors='black', marker='s' , s=12**2 , label = 'RUWE >= 1.2')
    temp3 = axs[0,0].scatter([] , [] , c='white' , edgecolors='blue' , marker='o' , s=12**2 , label = 'RV Comoving')
    temp4 = axs[0,0].scatter([] , [] , c='black' , marker='+' , s=12**2 , label = 'RV Outlier')

    axs[0,0].plot( 1000.0*Pxyz[0] , 1000.0*Pxyz[1] , 'rx' , markersize=18 , mew=3 , markeredgecolor='red')
    axs[0,1].plot( 1000.0*Pxyz[2] , 1000.0*Pxyz[1] , 'rx' , markersize=18 , mew=3 , markeredgecolor='red')
    axs[1,0].plot( 1000.0*Pxyz[0] , 1000.0*Pxyz[2] , 'rx' , markersize=18 , mew=3 , markeredgecolor='red' , zorder=1 , label = targname)

    axs[0,0].set_xlim( [1000.0*Pxyz[0]-(search_radius+1.0) , 1000.0*Pxyz[0]+(search_radius+1.0)] )
    axs[0,0].set_ylim( [1000.0*Pxyz[1]-(search_radius+1.0) , 1000.0*Pxyz[1]+(search_radius+1.0)] )
    axs[0,1].set_xlim( [1000.0*Pxyz[2]-(search_radius+1.0) , 1000.0*Pxyz[2]+(search_radius+1.0)] )
    axs[0,1].set_ylim( [1000.0*Pxyz[1]-(search_radius+1.0) , 1000.0*Pxyz[1]+(search_radius+1.0)] )
    axs[1,0].set_xlim( [1000.0*Pxyz[0]-(search_radius+1.0) , 1000.0*Pxyz[0]+(search_radius+1.0)] )
    axs[1,0].set_ylim( [1000.0*Pxyz[2]-(search_radius+1.0) , 1000.0*Pxyz[2]+(search_radius+1.0)] )
    
    axs[0,0].set_xlabel(r'$X$ (pc)',fontsize=20,labelpad=10)
    axs[0,0].set_ylabel(r'$Y$ (pc)',fontsize=20,labelpad=10)

    axs[1,0].set_xlabel(r'$X$ (pc)',fontsize=20,labelpad=10)
    axs[1,0].set_ylabel(r'$Z$ (pc)',fontsize=20,labelpad=10)

    axs[0,1].set_xlabel(r'$Z$ (pc)',fontsize=20,labelpad=10)
    axs[0,1].set_ylabel(r'$Y$ (pc)',fontsize=20,labelpad=10)

    axs[0,0].xaxis.set_ticks_position('top')
    axs[0,1].xaxis.set_ticks_position('top')
    axs[0,1].yaxis.set_ticks_position('right')

    axs[0,0].xaxis.set_label_position('top')
    axs[0,1].xaxis.set_label_position('top')
    axs[0,1].yaxis.set_label_position('right')

    for aa in [0,1]:
        for bb in [0,1]:
            axs[aa,bb].tick_params(top=True,bottom=True,left=True,right=True,direction='in',labelsize=18)

    fig.delaxes(axs[1][1])
    strsize = 26
    if (len(targname) > 12.0): strsize = np.floor(24 / (len(targname)/14.5))
    fig.legend( bbox_to_anchor=(0.92,0.37) , prop={'size':strsize})

    cbaxes = fig.add_axes([0.55,0.14,0.02,0.34])
    cb = plt.colorbar( ccc , cax=cbaxes )
    cb.set_label( label='Velocity Difference (km/s)' , fontsize=24 , labelpad=20 )
    cb.ax.tick_params(labelsize=18)

    figname=outdir + targname.replace(" ", "") + "xyz.png"
    plt.savefig(figname , bbox_inches='tight', pad_inches=0.2 , dpi=200)

    if showplots == True: plt.show()
    plt.close('all')



    # Create sky map
    # Hacked from cartopy.mpl.gridliner
    _DEGREE_SYMBOL = u'\u00B0'
    def _east_west_formatted(longitude, num_format='g'):
        fmt_string = u'{longitude:{num_format}}{degree}'
        return fmt_string.format(longitude=(longitude if (longitude >= 0) else (longitude + 360)) , \
                                            num_format=num_format,degree=_DEGREE_SYMBOL)
    def _north_south_formatted(latitude, num_format='g'):
        fmt_string = u'{latitude:{num_format}}{degree}'
        return fmt_string.format(latitude=latitude, num_format=num_format,degree=_DEGREE_SYMBOL)
    LONGITUDE_FORMATTER = mticker.FuncFormatter(lambda v, pos:
                                                _east_west_formatted(v))
    LATITUDE_FORMATTER = mticker.FuncFormatter(lambda v, pos:
                                               _north_south_formatted(v))

    zz = np.where( (sep3d.value < searchradpc.value) & (Gchi2 < vlim.value) & (sep.degree > 0.00001) )
    yy = zz[0][np.argsort((-Gchi2)[zz])]

    searchcircle = Pcoord.directional_offset_by( (np.arange(0,360)*u.degree) , searchraddeg*np.ones(360))
    circleRA = searchcircle.ra.value
    circleDE = searchcircle.dec.value
    ww = np.where(circleRA > 180.0)
    circleRA[ww] = circleRA[ww] - 360.0

    RAlist = gaiacoord.ra[yy].value
    DElist = gaiacoord.dec[yy].value
    ww = np.where( RAlist > 180.0 )
    RAlist[ww] = RAlist[ww] - 360.0

    polelat = ((Pcoord.dec.value+90) if (Pcoord.dec.value<0) else (90-Pcoord.dec.value))
    polelong= (Pcoord.ra.value if (Pcoord.dec.value<0.0) else (Pcoord.ra.value+180.0))
    polelong= (polelong if polelong < 180 else polelong - 360.0)

    if verbose == True:
        print('Alignment variables: ',polelat,polelong,Pcoord.ra.value)
        print(Pcoord.dec.value+searchraddeg.value)
    rotated_pole = ccrs.RotatedPole( \
        pole_latitude=polelat , \
        pole_longitude=polelong , \
        central_rotated_longitude=90.0 )#\
    #    (Pcoord.ra.value if (Pcoord.dec.value > 0.0) else (Pcoord.ra.value+180.0)) )

    fig = plt.figure(figsize=(8,8))
    ax = fig.add_subplot(1, 1, 1, projection=rotated_pole)

    ax.gridlines(draw_labels=True,x_inline=True,y_inline=True, \
                 xformatter=LONGITUDE_FORMATTER,yformatter=LATITUDE_FORMATTER)
    ax.plot( circleRA , circleDE , c="gray" , ls="--" , transform=ccrs.Geodetic())
    
    figname=outdir + targname.replace(" ", "") + "sky.png"

    base=plt.cm.get_cmap('cubehelix')

    for x in range(0 , np.array(yy).size):
        msize  = (17-12.0*(sep3d[yy[x]].value/searchradpc.value))
        mcolor = base(Gchi2[yy[x]]/vlim.value)
        medge  = 'black'
        mzorder= 3
        if (r['ruwe'][yy[x]] < 1.2):
            mshape='o'
        if (r['ruwe'][yy[x]] >= 1.2):
            mshape='s'
        if (np.isnan(rvcut) == False): 
            if (np.isnan(RV[yy[x]])==False) & (np.abs(RV[yy[x]]-Gvrpmllpmbb[yy[x],0]) > rvcut):
                mshape='+'
                mcolor='black'
                mzorder=2
            if (np.isnan(RV[yy[x]])==False) & (np.abs(RV[yy[x]]-Gvrpmllpmbb[yy[x],0]) <= rvcut):
                medge='blue'
        ccc = ax.plot( RAlist[x] , DElist[x] , marker=mshape ,  \
                markeredgecolor=medge , ms = msize , mfc = mcolor , transform=ccrs.Geodetic() )
        
    ax.plot( (Pcoord.ra.value-360.0) , Pcoord.dec.value , \
            'rx' , markersize=18 , mew=3 , transform=ccrs.Geodetic())

    plt.savefig(figname , bbox_inches='tight', pad_inches=0.2 , dpi=200)
    
    if showplots == True: plt.show()
    plt.close('all')

    ## Query GALEX and 2MASS data

    zz = np.where( (sep3d.value < searchradpc.value) & (Gchi2 < vlim.value) )
    yy = zz[0][np.argsort((-Gchi2)[zz])]
    
    NUVmag = np.empty(np.array(r['ra']).size)
    NUVerr = np.empty(np.array(r['ra']).size)
    NUVmag[:] = np.nan
    NUVerr[:] = np.nan

    print('Searching on neighbors in GALEX')
    ##suppress the stupid noresultswarning from the catalogs package
    warnings.filterwarnings("ignore",category=NoResultsWarning)

    for x in range(0 , np.array(yy).size):
        querystring=((str(gaiacoord.ra[yy[x]].value) if (gaiacoord.ra[yy[x]].value > 0) \
                      else str(gaiacoord.ra[yy[x]].value+360.0)) + " " + str(gaiacoord.dec[yy[x]].value))
        print('GALEX query ',x,' of ',np.array(yy).size, end='\r')
        if verbose == True: print('GALEX query ',x,' of ',np.array(yy).size)
        if verbose == True: print(querystring)
        if (DoGALEX == True): 
            galex = Catalogs.query_object(querystring , catalog="Galex" , radius=0.0028 , TIMEOUT=600)
            if ((np.where(galex['nuv_magerr'] > 0.0)[0]).size > 0):
                ww = np.where( (galex['nuv_magerr'] == min(galex['nuv_magerr'][np.where(galex['nuv_magerr'] > 0.0)])))
                NUVmag[yy[x]] = galex['nuv_mag'][ww][0]
                NUVerr[yy[x]] = galex['nuv_magerr'][ww][0]
                if verbose == True: print(galex['distance_arcmin','ra','nuv_mag','nuv_magerr'][ww])

        
    Jmag = np.empty(np.array(r['ra']).size)
    Jerr = np.empty(np.array(r['ra']).size)
    Jmag[:] = np.nan
    Jerr[:] = np.nan

    print('Searching on neighbors in 2MASS')

    for x in range(0 , np.array(yy).size):
        if ( np.isnan(NUVmag[yy[x]]) == False ):
            querycoord = SkyCoord((str(gaiacoord.ra[yy[x]].value) if (gaiacoord.ra[yy[x]].value > 0) else \
                     str(gaiacoord.ra[yy[x]].value+360.0)) , str(gaiacoord.dec[yy[x]].value) , \
                     unit=(u.deg,u.deg) , frame='icrs')
            print('2MASS query ',x,' of ',np.array(yy).size, end='\r')
            if verbose == True: print('2MASS query ',x,' of ',np.array(yy).size)
            if verbose == True: print(querycoord)
            tmass = []
            if (DoGALEX == True): 
                tmass = Irsa.query_region(querycoord , catalog='fp_psc' , radius='0d0m10s' )
                if ((np.where(tmass['j_m'] > -10.0)[0]).size > 0):
                    ww = np.where( (tmass['j_m'] == min(tmass['j_m'][np.where(tmass['j_m'] > 0.0)])))
                    Jmag[yy[x]] = tmass['j_m'][ww][0]
                    Jerr[yy[x]] = tmass['j_cmsig'][ww][0]
                    if verbose == True: print(tmass['j_m','j_cmsig'][ww])
        


    # Create GALEX plots
    mamajek = np.loadtxt(datapath+'/sptGBpRp.txt')
    f = interp1d( mamajek[:,2] , mamajek[:,0] , kind='cubic')

    zz2 = np.where( (sep3d.value < searchradpc.value) & (Gchi2 < vlim.value) )
    yy2 = zz[0][np.argsort(sep3d[zz])]
    zz = np.where( (sep3d.value < searchradpc.value) & (Gchi2 < vlim.value) & (sep.degree > 0.00001) )
    yy = zz[0][np.argsort((-Gchi2)[zz])]

    fnuvj = (3631.0 * 10**6 * 10**(-0.4 * NUVmag)) / (1594.0 * 10**6 * 10**(-0.4 * Jmag))
    spt = f(r['bp_rp'].filled(np.nan))
    sptstring = ["nan" for x in range(np.array(r['bp_rp']).size)]
    for x in range(0 , np.array(zz2).size):
        if (round(spt[yy2[x]],1) >= 17.0) and (round(spt[yy2[x]],1) < 27.0):
            sptstring[yy2[x]] = 'M' + ('% 3.1f' % (round(spt[yy2[x]],1)-17.0)).strip()
        if (round(spt[yy2[x]],1) >= 16.0) and (round(spt[yy2[x]],1) < 17.0):
            sptstring[yy2[x]] = 'K' + ('% 3.1f' % (round(spt[yy2[x]],1)-9.0)).strip()
        if (round(spt[yy2[x]],1) >= 10.0) and (round(spt[yy2[x]],1) < 16.0):
            sptstring[yy2[x]] = 'K' + ('% 3.1f' % (round(spt[yy2[x]],1)-10.0)).strip()
        if (round(spt[yy2[x]],1) >= 0.0) and (round(spt[yy2[x]],1) < 10.0):
            sptstring[yy2[x]] = 'G' + ('% 3.1f' % (round(spt[yy2[x]],1)-0.0)).strip()
        if (round(spt[yy2[x]],1) >= -10.0) and (round(spt[yy2[x]],1) < 0.0):
            sptstring[yy2[x]] = 'F' + ('% 3.1f' % (round(spt[yy2[x]],1)+10.0)).strip()
        if (round(spt[yy2[x]],1) >= -20.0) and (round(spt[yy2[x]],1) < -10.0):
            sptstring[yy2[x]] = 'A' + ('% 3.1f' % (round(spt[yy2[x]],1)+20.0)).strip()       
        if (round(spt[yy2[x]],1) >= -30.0) and (round(spt[yy2[x]],1) < -20.0):
            sptstring[yy2[x]] = 'B' + ('% 3.1f' % (round(spt[yy2[x]],1)+30.0)).strip()  
    


    figname=outdir + targname.replace(" ", "") + "galex.png"
    if verbose == True: print(figname)
    ##Muck with the axis to get two x axes

    fig,ax1 = plt.subplots(figsize=(12,8))
    ax1.set_yscale('log')
    ax1.axis([5.0 , 24.0 , 0.000004 , 0.02])
    ax2 = ax1.twiny()
    ax2.set_xlim(ax1.get_xlim())
    ax1.set_xticks(np.array([5.0 , 10.0 , 15.0 , 17.0 , 22.0 , 24.0]))
    ax1.set_xticklabels(['G5','K0','K5','M0','M5','M7'])
    ax1.set_xlabel('SpT' , fontsize=20, labelpad=15)
    ax1.tick_params(axis='both',which='major',labelsize=16)
    ax2.set_xticks(np.array([5.0 , 10.0 , 15.0 , 17.0 , 22.0 , 24.0]))
    ax2.set_xticklabels(['0.85','0.98','1.45','1.84','3.36','4.75'])
    ax2.set_xlabel(r'$B_p-R_p$ (mag)' , fontsize=20, labelpad=15)
    ax2.tick_params(axis='both',which='major',labelsize=16)
    ax1.set_ylabel(r'$F_{NUV}/F_{J}$' , fontsize=22, labelpad=0)

    ##Hyades
    hyades = readsav(datapath +'/HYsaved.sav')
    hyadesfnuvj = (3631.0 * 10**6 * 10**(-0.4 * hyades['clnuv'])) / (1594.0 * 10**6 * 10**(-0.4 * hyades['clJ']))
    ax1.plot(hyades['clspt'] , hyadesfnuvj , 'x' , markersize=4 , mew=1 , markeredgecolor='black' , zorder=1 , label='Hyades' )

    for x in range(0 , np.array(yy).size):
        msize  = (17-12.0*(sep3d[yy[x]].value/searchradpc.value))**2
        mcolor = Gchi2[yy[x]]
        medge  = 'black'
        mzorder= 3
        if (r['ruwe'][yy[x]] < 1.2):
            mshape='o'
        if (r['ruwe'][yy[x]] >= 1.2):
            mshape='s'
        if (np.isnan(rvcut) == False): 
            if (np.isnan(RV[yy[x]])==False) & (np.abs(RV[yy[x]]-Gvrpmllpmbb[yy[x],0]) > rvcut):
                mshape='+'
                mcolor='black'
                mzorder=2
            if (np.isnan(RV[yy[x]])==False) & (np.abs(RV[yy[x]]-Gvrpmllpmbb[yy[x],0]) <= rvcut):
                medge='blue'
        ccc = ax1.scatter( spt[yy[x]] , fnuvj[yy[x]] , \
                s=msize , c=mcolor , marker=mshape , edgecolors=medge , zorder=mzorder , \
                vmin=0.0 , vmax=vlim.value , cmap='cubehelix' , label='_nolabel' )

    temp1 = ax1.scatter([] , [] , c='white' , edgecolors='black', marker='o' , s=12**2 , label = 'RUWE < 1.2')
    temp2 = ax1.scatter([] , [] , c='white' , edgecolors='black', marker='s' , s=12**2 , label = 'RUWE >= 1.2')
    temp3 = ax1.scatter([] , [] , c='white' , edgecolors='blue' , marker='o' , s=12**2 , label = 'RV Comoving')
    temp4 = ax1.scatter([] , [] , c='black' , marker='+' , s=12**2 , label = 'RV Outlier')



    # Plot science target
    if (spt[yy[0]] > 5): ax1.plot(spt[yy[0]] , fnuvj[yy[0]] , 'rx' , markersize=18 , mew=3 , markeredgecolor='red' , zorder=3 , label=targname )

    ax1.legend(fontsize=16 , loc='lower left')
    cb = fig.colorbar(ccc , ax=ax1)
    cb.set_label(label='Velocity Offset (km/s)',fontsize=13)
    if (DoGALEX == True): plt.savefig(figname , bbox_inches='tight', pad_inches=0.2 , dpi=200)
    if showplots == True: plt.show()
    plt.close('all')
    
    
    # Query CatWISE for W1+W2 and AllWISE for W3+W4

    zz = np.where( (sep3d.value < searchradpc.value) & (Gchi2 < vlim.value) )
    yy = zz[0][np.argsort((-Gchi2)[zz])]

    WISEmag = np.empty([np.array(r['ra']).size,4])
    WISEerr = np.empty([np.array(r['ra']).size,4])
    WISEmag[:] = np.nan
    WISEerr[:] = np.nan

    print('Searching on neighbors in WISE')
    ##there's an annoying nan warning here, hide it for now as it's not a problem
    warnings.filterwarnings("ignore",category=UserWarning)

    for x in range(0 , np.array(yy).size):
        querycoord = SkyCoord((str(gaiacoord.ra[yy[x]].value) if (gaiacoord.ra[yy[x]].value > 0) else \
                     str(gaiacoord.ra[yy[x]].value+360.0)) , str(gaiacoord.dec[yy[x]].value) , \
                     unit=(u.deg,u.deg) , frame='icrs')
        print('WISE query ',x,' of ',np.array(yy).size, end='\r')
        if verbose == True: print('WISE query ',x,' of ',np.array(yy).size)
        if verbose == True: print(querycoord)
    
        wisecat = []
        if (DoWISE == True): 
            wisecat = Irsa.query_region(querycoord,catalog='catwise_2020' , radius='0d0m10s')
            if ((np.where(wisecat['w1mpro'] > -10.0)[0]).size > 0):
                ww = np.where( (wisecat['w1mpro'] == min( wisecat['w1mpro'][np.where(wisecat['w1mpro'] > -10.0)]) ))
                WISEmag[yy[x],0] = wisecat['w1mpro'][ww][0]
                WISEerr[yy[x],0] = wisecat['w1sigmpro'][ww][0]
            if ((np.where(wisecat['w2mpro'] > -10.0)[0]).size > 0):
                ww = np.where( (wisecat['w2mpro'] == min( wisecat['w2mpro'][np.where(wisecat['w2mpro'] > -10.0)]) ))
                WISEmag[yy[x],1] = wisecat['w2mpro'][ww][0]
                WISEerr[yy[x],1] = wisecat['w2sigmpro'][ww][0]
 
        if (DoWISE == True): 
            wisecat = Irsa.query_region(querycoord,catalog='allwise_p3as_psd' , radius='0d0m10s')
            if ((np.where(wisecat['w1mpro'] > -10.0)[0]).size > 0):
                ww = np.where( (wisecat['w1mpro'] == min( wisecat['w1mpro'][np.where(wisecat['w1mpro'] > -10.0)]) ))
                if (np.isnan(WISEmag[yy[x],0]) == True) | (wisecat['w1mpro'][ww][0] < 11.0):				# Note, only if CatWISE absent/saturated
                    WISEmag[yy[x],0] = wisecat['w1mpro'][ww][0]
                    WISEerr[yy[x],0] = wisecat['w1sigmpro'][ww][0]
            if ((np.where(wisecat['w2mpro'] > -10.0)[0]).size > 0):
                ww = np.where( (wisecat['w2mpro'] == min( wisecat['w2mpro'][np.where(wisecat['w2mpro'] > -10.0)]) ))
                if (np.isnan(WISEmag[yy[x],1]) == True) | (wisecat['w2mpro'][ww][0] < 11.0):				# Note, only if CatWISE absent/saturated
                    WISEmag[yy[x],1] = wisecat['w2mpro'][ww][0]
                    WISEerr[yy[x],1] = wisecat['w2sigmpro'][ww][0]
            if ((np.where(wisecat['w3mpro'] > -10.0)[0]).size > 0):
                ww = np.where( (wisecat['w3mpro'] == min( wisecat['w3mpro'][np.where(wisecat['w3mpro'] > -10.0)]) ))
                WISEmag[yy[x],2] = wisecat['w3mpro'][ww][0]
                WISEerr[yy[x],2] = wisecat['w3sigmpro'][ww][0]
            if ((np.where(wisecat['w4mpro'] > -10.0)[0]).size > 0):
                ww = np.where( (wisecat['w4mpro'] == min( wisecat['w4mpro'][np.where(wisecat['w4mpro'] > -10.0)]) ))
                WISEmag[yy[x],3] = wisecat['w4mpro'][ww][0]
                WISEerr[yy[x],3] = wisecat['w4sigmpro'][ww][0]
        
        if verbose == True: print(yy[x],WISEmag[yy[x],:],WISEerr[yy[x],:])

    # Create WISE plots

    W13 = WISEmag[:,0]-WISEmag[:,2]
    W13err = ( WISEerr[:,0]**2 + WISEerr[:,2]**2 )**0.5

    zz = np.argwhere( np.isnan(W13err) )
    W13[zz] = np.nan
    W13err[zz] = np.nan

    zz = np.where( (W13err > 0.15) )
    W13[zz] = np.nan
    W13err[zz] = np.nan
    warnings.filterwarnings("default",category=UserWarning)




    zz2 = np.where( (sep3d.value < searchradpc.value) & (Gchi2 < vlim.value))
    yy2 = zz[0][np.argsort(sep3d[zz])]
    zz = np.where( (sep3d.value < searchradpc.value) & (Gchi2 < vlim.value) & (sep.degree > 0.00001) )
    yy = zz[0][np.argsort((-Gchi2)[zz])]

    figname=outdir + targname.replace(" ", "") + "wise.png"
    if verbose == True: print(figname)
    plt.figure(figsize=(12,8))

    if (verbose == True) & ((np.where(np.isfinite(W13+W13err))[0]).size > 0): print('Max y value: ' , (max((W13+W13err)[np.isfinite(W13+W13err)])+0.1) )
    plt.axis([ 5.0 , 24.0 , \
              max( [(min(np.append((W13-W13err)[ np.isfinite(W13-W13err) ],-0.1))-0.1) , -0.3]) , \
              max( [(max(np.append((W13+W13err)[ np.isfinite(W13+W13err) ],+0.0))+0.2) , +0.6]) ])

    ax1 = plt.gca()
    ax2 = ax1.twiny()
    ax2.set_xlim(5.0,24.0)

    ax1.set_xticks(np.array([5.0 , 10.0 , 15.0 , 17.0 , 22.0 , 24.0]))
    ax1.set_xticklabels(['G5','K0','K5','M0','M5','M7'])
    ax1.set_xlabel('SpT' , fontsize=20, labelpad=15)
    ax1.tick_params(axis='both',which='major',labelsize=16)

    ax2.set_xticks(np.array([5.0 , 10.0 , 15.0 , 17.0 , 22.0 , 24.0]))
    ax2.set_xticklabels(['0.85','0.98','1.45','1.84','3.36','4.75'])
    ax2.set_xlabel(r'$B_p-R_p$ (mag)' , fontsize=20, labelpad=15)
    ax2.tick_params(axis='both',which='major',labelsize=16)

    ax1.set_ylabel(r'$W1-W3$ (mag)' , fontsize=22, labelpad=0)

    # Plot field sequence from Tuc-Hor (Kraus et al. 2014)
    fldspt = [ 5 , 7 , 10 , 12 , 15 , 17 , 20 , 22 , 24 ]
    fldW13 = [ 0 , 0 ,  0 , .02, .06, .12, .27, .40, .60]
    plt.plot(fldspt , fldW13  , zorder=0 , label='Photosphere')

    # Plot neighbors
    ax1.errorbar( spt[yy] , W13[yy] , yerr=W13err[yy] , fmt='none' , ecolor='k')


    for x in range(0 , np.array(yy).size):
        msize  = (17-12.0*(sep3d[yy[x]].value/searchradpc.value))**2
        mcolor = Gchi2[yy[x]]
        medge  = 'black'
        mzorder= 3
        if (r['ruwe'][yy[x]] < 1.2):
            mshape='o'
        if (r['ruwe'][yy[x]] >= 1.2):
            mshape='s'
        if (np.isnan(rvcut) == False): 
            if (np.isnan(RV[yy[x]])==False) & (np.abs(RV[yy[x]]-Gvrpmllpmbb[yy[x],0]) > rvcut):
                mshape='+'
                mcolor='black'
                mzorder=2
            if (np.isnan(RV[yy[x]])==False) & (np.abs(RV[yy[x]]-Gvrpmllpmbb[yy[x],0]) <= rvcut):
                medge='blue'
        ccc = ax1.scatter( spt[yy[x]] , W13[yy[x]] , \
                s=msize , c=mcolor , marker=mshape , edgecolors=medge , zorder=mzorder , \
                vmin=0.0 , vmax=vlim.value , cmap='cubehelix' , label='_nolabel' )

    temp1 = ax1.scatter([] , [] , c='white' , edgecolors='black', marker='o' , s=12**2 , label = 'RUWE < 1.2')
    temp2 = ax1.scatter([] , [] , c='white' , edgecolors='black', marker='s' , s=12**2 , label = 'RUWE >= 1.2')
    temp3 = ax1.scatter([] , [] , c='white' , edgecolors='blue' , marker='o' , s=12**2 , label = 'RV Comoving')
    temp4 = ax1.scatter([] , [] , c='black' , marker='+' , s=12**2 , label = 'RV Outlier')


    # Plot science target
    if (spt[yy2[0]] > 5):
        plt.plot(spt[yy2[0]] , W13[yy2[0]] , 'rx' , markersize=18 , mew=3 , markeredgecolor='red' , zorder=3 , label=targname )

    plt.legend(fontsize=16 , loc='upper left')
    cb = plt.colorbar(ccc , ax=ax1)
    cb.set_label(label='Velocity Offset (km/s)',fontsize=14)
    if (DoWISE == True): plt.savefig(figname , bbox_inches='tight', pad_inches=0.2 , dpi=200)
    if showplots == True: plt.show()
    plt.close('all')

    # Cross-reference with ROSAT

    v = Vizier(columns=["**", "+_R"] , catalog='J/A+A/588/A103/cat2rxs' )

    zz = np.where( (sep3d.value < searchradpc.value) & (Gchi2 < vlim.value) )
    yy = zz[0][np.argsort(sep3d[zz])]

    ROSATflux = np.empty([np.array(r['ra']).size])
    ROSATflux[:] = np.nan

    print('Searching on neighbors in ROSAT')
    for x in range(0 , np.array(yy).size):
        querycoord = SkyCoord((str(gaiacoord.ra[yy[x]].value) if (gaiacoord.ra[yy[x]].value > 0) else \
                     str(gaiacoord.ra[yy[x]].value+360.0)) , str(gaiacoord.dec[yy[x]].value) , \
                     unit=(u.deg,u.deg) , frame='icrs')
        print('ROSAT query ',x,' of ',np.array(yy).size, end='\r')
        if verbose == True: print('ROSAT query ',x,' of ',np.array(yy).size)
        if verbose == True: print(querycoord)
        if (DoROSAT == True): 
            rosatcat = v.query_region(querycoord , radius='0d1m0s' )
            if (len(rosatcat) > 0):
                rosatcat = rosatcat['J/A+A/588/A103/cat2rxs']
                if verbose == True: print(rosatcat)
                if ((np.where(rosatcat['CRate'] > -999)[0]).size > 0):
                    ww = np.where( (rosatcat['CRate'] == max(rosatcat['CRate'][np.where(rosatcat['CRate'] > -999)])))
                    ROSATflux[yy[x]] = rosatcat['CRate'][ww][0]
                if verbose == True: print(x,yy[x],ROSATflux[yy[x]])


    # Create output table with results
    print('Creating Output Tables with Results')
    if verbose == True: 
        print('Reminder, there were this many input entries: ',len(Gxyz[:,0]))
        print('The search radius in velocity space is: ',vlim)
        print()

    zz = np.where( (sep3d.value < searchradpc.value) & (Gchi2 < vlim.value) )
    sortlist = np.argsort(sep3d[zz])
    yy = zz[0][sortlist]

    fmt1 = "%11.7f %11.7f %6.3f %6.3f %11.3f %8.4f %8.4f %8.2f %8.2f %8.2f %8.3f %4s %8.6f %6.2f %7.3f %7.3f %35s"
    fmt2 = "%11.7f %11.7f %6.3f %6.3f %11.3f %8.4f %8.4f %8.2f %8.2f %8.2f %8.3f %4s %8.6f %6.2f %7.3f %7.3f %35s"
    filename=outdir + targname.replace(" ", "") + ".txt"
    
    warnings.filterwarnings("ignore",category=UserWarning)
    if verbose == True: 
        print('Also creating SIMBAD query table')
        print(filename)
        print('RA            DEC        Gmag   Bp-Rp  Voff(km/s) Sep(deg)   3D(pc) Vr(pred)  Vr(obs)    Vrerr Plx(mas)  SpT    FnuvJ  W1-W3    RUWE  XCrate RVsrc')
    with open(filename,'w') as file1:
        file1.write('RA            DEC        Gmag   Bp-Rp  Voff(km/s) Sep(deg)   3D(pc) Vr(pred)  Vr(obs)    Vrerr Plx(mas)  SpT    FnuvJ  W1-W3    RUWE  XCrate RVsrc \n')
    for x in range(0 , np.array(zz).size):
            if verbose == True:
                print(fmt1 % (gaiacoord.ra[yy[x]].value,gaiacoord.dec[yy[x]].value, \
                  r['phot_g_mean_mag'][yy[x]], r['bp_rp'][yy[x]] , \
                  Gchi2[yy[x]] , sep[yy[x]].value , sep3d[yy[x]].value , \
                  Gvrpmllpmbb[yy[x],0] , RV[yy[x]] , RVerr[yy[x]] , \
                  r['parallax'][yy[x]], \
                  sptstring[yy[x]] , fnuvj[yy[x]] , W13[yy[x]] , r['ruwe'][yy[x]] , ROSATflux[yy[x]] , RVsrc[yy[x]]) )
            with open(filename,'a') as file1:
                  file1.write(fmt2 % (gaiacoord.ra[yy[x]].value,gaiacoord.dec[yy[x]].value, \
                      r['phot_g_mean_mag'][yy[x]], r['bp_rp'][yy[x]] , \
                      Gchi2[yy[x]],sep[yy[x]].value,sep3d[yy[x]].value , \
                      Gvrpmllpmbb[yy[x],0] , RV[yy[x]] , RVerr[yy[x]] , \
                      r['parallax'][yy[x]], \
                      sptstring[yy[x]] , fnuvj[yy[x]] , W13[yy[x]] , r['ruwe'][yy[x]] , ROSATflux[yy[x]] , RVsrc[yy[x]]) )
                  file1.write("\n")

    filename=outdir + targname.replace(" ", "") + ".csv"
    with open(filename,mode='w') as result_file:
        wr = csv.writer(result_file)
        wr.writerow(['RA','DEC','Gmag','Bp-Rp','Voff(km/s)','Sep(deg)','3D(pc)','Vr(pred)','Vr(obs)','Vrerr','Plx(mas)','SpT','FnuvJ','W1-W3','RUWE','XCrate','RVsrc'])
        for x in range(0 , np.array(zz).size):
            wr.writerow(( "{0:.7f}".format(gaiacoord.ra[yy[x]].value) , "{0:.7f}".format(gaiacoord.dec[yy[x]].value) , \
                      "{0:.3f}".format(r['phot_g_mean_mag'][yy[x]]), "{0:.3f}".format(r['bp_rp'][yy[x]]) , \
                      "{0:.3f}".format(Gchi2[yy[x]]) , "{0:.4f}".format(sep[yy[x]].value) , "{0:.4f}".format(sep3d[yy[x]].value) , \
                      "{0:.2f}".format(Gvrpmllpmbb[yy[x],0]) , "{0:.2f}".format(RV[yy[x]]) , "{0:.2f}".format(RVerr[yy[x]]) , \
                      "{0:.3f}".format(r['parallax'][yy[x]]), \
                      sptstring[yy[x]] , "{0:.6f}".format(fnuvj[yy[x]]) , "{0:.2f}".format(W13[yy[x]]) , \
                      "{0:.3f}".format(r['ruwe'][yy[x]]) , "{0:.3f}".format(ROSATflux[yy[x]]) , RVsrc[yy[x]].strip()) )

    if verbose == True: print('All output can be found in ' + outdir)



    return outdir
