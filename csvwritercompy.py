# -*- coding: utf-8 -*-

#TODO: all constants at top
#TODO: vertical line
'''
fits files must be named pscxxxxxx.f.fits
and FILTERS must be such that filter number f corresponds with filter filters[f]
alertstable_vs and alertstablevs.lasthalf must be in directory for sn locations
sdssTableGroupIndex.py, sdss_queries.dat

'''

import numpy as np
import pandas as pd
import os
import glob
import random
import csv
import sep
import ast
import matplotlib.pyplot as plt
from astropy.visualization import astropy_mpl_style
plt.style.use(astropy_mpl_style)
from matplotlib.patches import Ellipse, RegularPolygon
from astropy.io import fits
from astropy.wcs import WCS

from astropy import units as u
from astropy.coordinates import SkyCoord
from astroquery.sdss import SDSS
from astropy.cosmology import Planck13 as cosmo
from astropy.table import Table, vstack
from sdssTableGroupIndex import sdssTableGroupIndex

ERRORFILE = 'errorfile.txt'
SOURCEDIR = os.getcwd() #"/mnt/d/Summer 2019 Astro" #"C:/Users/Faith/Desktop/noey2019summer/ps1hosts"
DESTDIR = os.getcwd()
FILLER_VAL = None
THRESHOLD = 0.9
MINAREA = 5
DEBLEND_CONT = 0.01 # for sep.extract. 1.0 to turn off deblending, 0.005 is default
SUBTRACT_BACKGROUND = True
MINDIST = 0.0005*u.deg #dist. an sdss object must be within to identify as
FILTERS = [None, None, None, 'modelMag_g', 'modelMag_r', 'modelMag_i', 'modelMag_z']
LIKELIHOOD_THRESH = 0.2
TYPES = ['SNIIn', 'SNIa', 'SNII', 'SNIbc', 'SLSNe']
TYPE_COLORS = {'SNIIn':'co', 'SNIa':'ro', 'SNII': 'bo', 'SNIbc':'go', 'SLSNe': 'mo'}
# meds used for m_0 if no sdss stars in image, or if m_0 is an outlier
# meaning outside of upper/lower bounds
#FILTER_M0s = [None, None, None,
#              {'upper': 23.625, 'default': 23.125, 'lower': 22.625}, # filter 3
#              {'upper': 23.4, 'default': 22.9, 'lower': 22.4}, # filter 4
#              {'upper': 23.4, 'default': 22.9, 'lower': 22.4}, # filter 5
#              {'upper': 24.125, 'default': 23.625, 'lower': 23.125}] # filter 6

#update from first 120 files:
FILTER_M0s = [None, None, None,
              {'upper': 23.54, 'default': 23.04, 'lower': 22.54}, # filter 3
              {'upper': 23.49, 'default': 22.99, 'lower': 22.49}, # filter 4
              {'upper': 24.29, 'default': 23.79, 'lower': 23.29}, # filter 5
              {'upper': 24.23, 'default': 23.73, 'lower': 23.23}] # filter 6


#USAGE FLAGS:
WRITE_CSV = "\galaxiesdata.csv" # filename to write to or None
MAG_TEST_ALL = False
MAG_TEST_STDEV = False
PLOT_REDSHIFTS = False

MAGFILE = 'newmagtest.csv'
#Do not write csv an mag test simultaneously because there is only 1 writer
#TODO separate the csvwriters
#ACTUALLY< REMOVING MAG WRITER
#if MAG_TEST_ALL or MAG_TEST_STDEV:
#    WRITE_CSV = False
PRINT_DATA = False

CHECK_DISTANCE = 5 #print all files with most likely host farther than this arcsecs
PLOT_ALL = False
PLOT_ERR =  True #plots only files that give errors or low probability
PLOT_DIR = os.getcwd() + '/plots' # where to put plot images
ONLY_FLAG_ERRORS = True # catch errors, print filename, move on
FILES = 'specified' #options are 'all', 'preset random', 'new random', 'range', 'specified', 'nonsquare

#TODO delete
SPECIFIED = []
to_check = [160103, 180313, 590123, 50296, 90034, 50601]
for f in to_check:
    SPECIFIED.extend(glob.glob((SOURCEDIR + '/ps1hosts/psc*%i*.[3-6].fits' % f)))

SPECIFIED = [SOURCEDIR + '/ps1hosts/psc480552.6.fits']
RANGE = (0,40)
m0collector = [None, None, None, [], [], [], []]
BAD_COUNT = 0
'''make header'''
HEADER =['ID']
#perImageHeaders = ['KronRad', 'separation', 'x', 'y', 'RA', 'DEC', 'KronMag', 'Angle', 'Ellipticity']
perImageHeaders = ['KronRad (kpc)', 'separation (kpc)', 'area (kpc^2)', 'sep/area (kpc)',
                   'x', 'y','KronMag', 'Abs. Mag', 'Angle',
                   'Ellipticity', 'RA', 'Host RA', 'DEC', 'Host Dec',
                   'Discrepency (arcsecs)', 'Z', 'SDSS Photoz', 'pixelRank', 'chance coincidence']
for i in range(3,7):
    for val in perImageHeaders:
        HEADER.append(val + '_' + str(i))

# remove error file
if os.path.exists(ERRORFILE):
  os.remove(ERRORFILE)

# for naming plots files
namecount = 0
def namegen():
    global namecount
    namecount += 1
    return PLOT_DIR + "\galaxyimage" + str(namecount) + ".png"

class Image:    
    def __init__(self, idNumString, filterNum, event):
#TODO get all of this work out of the init?
        
#TODO unneccessary or redundant?
        self.idNumString = idNumString
        self.idNum = int(idNumString)
        self.filterNum = filterNum
        self.event = event
        filename = SOURCE_DIR + "/psc%s.%s.fits" % (idNumString, filterNum)
        w = WCS(filename)
        
        # to get image dimensions in wcs:
        maxX = image_file[0].header['NAXIS1']
        maxY = image_file[0].header['NAXIS2']
        maxRa, maxDec = w.all_pix2world(1,maxY,1)
        minRa, minDec = w.all_pix2world(maxX,1,1)

        # fix formatting
        maxRa = maxRa.item(0)*u.deg
        minRa = minRa.item(0)*u.deg
        maxDec = maxDec.item(0)*u.deg
        minDec = minDec.item(0)*u.deg

        image_file = fits.open(filename)
        
        ''' extract objects '''
        image_data = image_file[0].data

        #fix byte order
        swappedData = image_data.byteswap(True).newbyteorder()
        global bkg
        # subtracting out background
        bkg = sep.Background(swappedData)
        if SUBTRACT_BACKGROUND:
            swappedData = swappedData - bkg
        
        
        def recursiveExtraction(attemptedThresh):
          self.objects, segmap = sep.extract(swappedData, attemptedThresh,
                                          err=bkg.globalrms, #var=noise_data2 ,
                                  minarea = MINAREA, deblend_cont = DEBLEND_CONT,
                                  segmentation_map = True)

            # how to calculate kron radius and flux from
            # https://sep.readthedocs.io/en/v1.0.x/apertures.html
            kronrad, _krflag = sep.kron_radius(swappedData, self.objects['x'], self.objects['y'],
                                               self.objects['a'], self.objects['b'],
                                               self.objects['theta'], 6.0)

            # self.objects to be ignored in host detection
            self.blacklist = set()

            for i in range(len(self.objects)):
                # remove any 'nan' kronrads and blacklist the objects
                #check if ki is nan:
                if np.isnan(kronrad[i]):
                    #if an object near event (likely host) fails,
                    # redo getting objects using a higher thresh
                    if abs(self.objects['x'][i] - eventX) < 20 and \
                       abs(self.objects['y'][i] - eventY) < 20:
                           noteString = "Note: raising threshold to %s %s \n" \
                               %(attemptedThresh + 0.3, filename_d)
                           print(noteString)
                           with open(ERRORFILE, 'a+') as errorfile:
                               errorfile.write(noteString)
                           recursiveExtraction(attemptedThresh + 0.3)
                           return
                    # otherwise blacklist and give an arbitrary valid kronrad
                    self.blacklist.add(i)
                    kronrad[i] = 0.1

        ''' '''
        
        # start with default threshold, if it fails then use a higher one
        recursiveExtraction(THRESHOLD)
        flux = []
        for i in range(len(kronrad)):
            try:
                thisflux, _fluxerr, _flag = sep.sum_ellipse(swappedData, self.objects['x'][i],
                                        self.objects['y'][i], self.objects['a'][i],
                                        self.objects['b'][i], self.objects['theta'][i],
                                        2.5*kronrad[i], subpix=1)
                flux.append(thisflux)
            except:
                flux.append(0)
                self.errorProtocol("Warning: failed flux calculation on " + filename_d)
        flux = np.array(flux)

        if idNumString not in sdssTableGroupIndex:
            sdssTable = None
        else:
            sdssTable = fullSdssTable.groups[sdssTableGroupIndex[idNumString]]

        # the last argument is 1 b/c first pixel of FITS should be 1,1 not 0,0?
        self.ra, self.dec = w.all_pix2world(self.objects['x'], self.objects['y'], 1)
        self.objCoords = SkyCoord(self.ra*u.deg, self.dec*u.deg, frame='icrs') # coords of all objs

        # for collecting mags and fluxes to calculate the zero for this file
        colRealMags = []
        #colRealMags = Table([[]]*8, names=magNames)
        colFluxes = []
        self.photozs = [None]*len(self.objects)
        for i in range(len(self.objects)):
            curRa = self.ra[i]
            curDec = self.dec[i]
            if sdssTable:
                # for each object, iterate through table until finding object
                #at that location
                for j in range(len(sdssTable)):
                    # check if sdss object matching object i's location
                    if abs(sdssTable['ra'][j] - curRa)*u.deg < MINDIST\
                        and abs(sdssTable['dec'][j] - curDec)*u.deg < MINDIST:

                        # if there's a valid photz, store for future comparison
                        if sdssTable['type'][j] == 3 \
                           and sdssTable['z'][j] \
                           and not np.isnan(sdssTable['z'][j]) \
                           and sdssTable['z'][j] != -9999.0:
                               self.photozs[i] = sdssTable['z'][j]

                        # if its a star, and its not right on the event, blacklist
                        if sdssTable['type'][j] == 6 \
                            and not abs(sdssTable['ra'][j] - eventRa)*u.deg < MINDIST \
                            and not abs(sdssTable['dec'][j] - eventDec)*u.deg < MINDIST:
                            self.blacklist.add(i)

                        #if its a star brighter than 21, use its magnitude in zero point calculation
                        if sdssTable['type'][j] == 6 and sdssTable[FILTERS[filterNum]][j] < 21. \
                            and self.objects['x'][i] - 2.5 * kronrad[i] >= 0 \
                            and self.objects['x'][i] + 2.5 * kronrad[i] <= maxX \
                            and self.objects['y'][i] - 2.5 * kronrad[i] >= 0 \
                            and self.objects['y'][i] + 2.5 * kronrad[i] <= maxY:
                                colRealMags.append(sdssTable[FILTERS[filterNum]][j])
                                colFluxes.append(flux[i])
#TODO check that star is completely in frame before use
                        break

        try:
            colFluxes = np.array(colFluxes)

#            magcache = [idNum, filterNum]
            m_0s = colRealMags + 2.5 * np.log10(colFluxes/float(image_file[0].header['MJD-OBS']))
            m_0s = m_0s[~np.isnan(m_0s)] #remove nans
            if m_0s.any():
                m_0 = np.median(m_0s)
                global m0collector
                m0collector[filterNum].append(m_0)

            #no SDSS stars to calculate zero point
            else:
                    m_0 = FILTER_M0s[filterNum]['default']
                    colFluxes = np.array([])
                    colRealMags = np.array([])

            # m_0 is outlier, use default
            if m_0 > FILTER_M0s[filterNum]['upper'] or \
                m_0 < FILTER_M0s[filterNum]['lower']:
                    m_0 = FILTER_M0s[filterNum]['default']

            colMyMags = -2.5 * np.log10(colFluxes/float(image_file[0].header['MJD-OBS'])) + m_0
            self.magnitude = -2.5 * np.log10(flux/float(image_file[0].header['MJD-OBS'])) + m_0
#TODO combine?
#            if MAG_TEST_STDEV:
#                csvwriter.writerow(magcache)
#                raise AssertionError
            if MAG_TEST_ALL:
                all_myMags[filterNum].extend(colMyMags[:])
                all_realMags[filterNum].extend(colRealMags[:])
#
#                for obj in range(len(colFluxes)):
#                    csvwriter.writerow([idNum, filterNum, colMyMags[obj],
#                                        colRealMags[obj],
#                                        colMyMags[obj] - colRealMags[obj]])
#TODO remove
                for k in range(len(colMyMags)):
                    if abs(colMyMags[k] - colRealMags[k]) > 2:
                        print("outlier: " + filename_d)

            '''Chance Coincidence Calculation'''
            #size is half light radius
            size, _flag = sep.flux_radius(swappedData, self.objects['x'], self.objects['y'],
                              6.*self.objects['a'], 0.5, normflux=flux, subpix=5)

            # convert to arcsecs
            degPerPix = image_file[0].header['CDELT1']
            size = size * degPerPix *3600

            self.separation = self.objCoords.separation(eventCoords).arcsec
            
            # Observed number density of galaxies brighter than magnitude M (From Berger 2010)
            sigma = 10 ** (0.33 * (self.magnitude - 24) - 2.44) / (0.33 * np.log(10))
            # Effective radius
            R_effective = np.sqrt(np.abs(self.separation)**2 + 4 * np.abs(size) ** 2)

            # Probability of chance coincidence
            self.chanceCoincidence = 1 - np.exp(-np.pi * R_effective ** 2 * sigma)
            # exclude any blacklisted
            for i in self.blacklist:
                self.chanceCoincidence[i] = 1
            
            self.ellipticity = 1 - (self.objects['b'][bestCandidate]/self.objects['a'][bestCandidate])

            #remove mpc for dimensionless math and convert to kpc
            dA = cosmo.angular_diameter_distance(event_z)*1000/u.Mpc # in kpc.
            self.area = self.objects['npix'] * (degPerPix*(np.pi/180.)*dA)**2 #kpc^2
            dL = cosmo.luminosity_distance(event_z)*1000/u.Mpc # in kpc
            self.absMag = self.magnitude - 5*np.log10(dL) - 10
            # separation is in arcseconds
            self.separationKpc = self.separation * (1./3600.) * (np.pi/180.)*dA
            self.kronradKpc = kronrad * degPerPix*(np.pi/180.)*dA
            
            image_file.close()
   
    def attemptBestCandidate(self):
        self.bestCandidate = np.argmin(self.chanceCoincidence)
        # Correct bestCandidate choice for closer redshift if similar prob.
        self.eventz = float(zdict[self.idNumString])
#TODO change to absolute separation
        photoz_matched = False
        if self.separation[self.bestCandidate] > CHECK_DISTANCE:
            #check for an object with photoz within 10% of event redshift
            for k in range(len(self.photozs)):
                if self.photozs[k] and abs(self.photozs[k] - self.eventz)/self.eventz < 0.1:
                    self.bestCandidate = k
                    if photoz_matched:
                        self.errorProtocol("multiple matching photozs")
#TODO green circle all in plot
                        photoz_matched = True
        return photoz_matched
    
    def check_at(coords):
        #TODO
    
    def modifyFinalDataFrom(data):
        
        #TODO
    
    def getFinalData():    
        '''Get "real" host location and redshifts'''
        hostRa = hostsData[idNumString]['host_ra']
        hostDec = hostsData[idNumString]['host_dec']
        try:
            hostCoords = SkyCoord(hostRa, hostDec, unit=(u.hourangle, u.deg))
            #convert to decimal deg:
            hostRa = hostCoords.ra.deg
            hostDec = hostCoords.dec.deg
            offby = hostCoords.separation(objCoords[bestCandidate]).arcsec\
                    if hostRa else None
            hectoZ = hostsData[idNumString]['redshift']
        except ValueError:
            if len(hostRa) > 12: # hecto gave multiple host galaxies
                hostRa = "multiple"
                hostDec = "multiple"
                offby = None
                hectoZ = "multiple"
            else:
                raise
                
        pixelRank = self.getPixelRank()
        bestCandidate = self.bestCandidate
        finalProperties = [self.kronradKpc[bestCandidate],
                           self.separationKpc[bestCandidate],
                           self.area[bestCandidate],
                           self.separationKpc[bestCandidate] / self.area[bestCandidate],
                           self.objects['x'][bestCandidate] - self.event['x'],
                           self.objects['y'][bestCandidate] - self.event['y'],
                           self.magnitude[bestCandidate],
                           self.absMag[bestCandidate],
                           self.objects['theta'][bestCandidate],
                           self.ellipticity,
                           self.ra[bestCandidate], hostRa,
                           self.dec[bestCandidate], hostDec,
                           offby, self.eventz, self.photozs[bestCandidate], pixelRank,
                           self.chanceCoincidence[bestCandidate]]
        return finalProperties
    
    def plot(self, myVmin=None, myVmax=None, target=None):
        green = target if target else [self.bestCandidate]
        # make the destination directory if it does not exist
        if not os.path.isdir(PLOT_DIR):
            os.mkdir(PLOT_DIR)
        to_circle = range(len(self.objects))
    
        fig, ax = plt.subplots()
    
        if myVmax == None or myVmin == None:
            _im = ax.imshow(self.swappedData, interpolation='nearest', cmap='gray')
        else:
            _im = ax.imshow(self.swappedData, interpolation='nearest', cmap='gray',
                            vmin = myVmin, vmax = myVmax)
        # triangle on event location
        p = RegularPolygon((int(self.event['x']), int(self.event['y'])), 3, radius=3)
        p.set_edgecolor('purple')
        p.set_facecolor('purple')
        ax.add_artist(p)
    
        # plot an ellipse for each object
        for i in to_circle:
            e = Ellipse(xy=(self.objects['x'][i], objects['y'][i]),
                        width=6*self.objects['a'][i],
                        height=6*self.objects['b'][i],
                        angle=self.objects['theta'][i] * 180. / np.pi)
    # TODO check if above angle conversion is correct. Where from?
            e.set_facecolor('none')
            if i in green:
                e.set_edgecolor('green')
            elif i in self.blacklist:
                e.set_edgecolor('blue')
            else:
                e.set_edgecolor('red')
            ax.add_artist(e)
        plt.savefig(namegen(), dpi=150)
        plt.show()
        plt.close()

    def getPixelRank(self):
        global a
        global pixels
        global location
        target = self.bestCandidate
        a = np.where(self.segmap == target+1)
        pixels = []
        for k in range(len(a[0])):
            pixels.append((a[0][k], a[1][k])) #list of tuples of coords
        pixels.append((int(event['x']), int(event['y']))) #in case event is outside host object
        def sortkey(x):
            a, b = x
            return swappedData[a][b]
        pixels.sort(key = sortkey)
        location = pixels.index((int(event['x']), int(event['y'])))
        return float(location)/float(len(pixels))
    
    
    def errorProtocol(self, e, target=None):
            curFile = self.idNum + '.' + self.filterNum
            errorString = str(namecount) + '\n' + str(e) + " " + curFile + '\n'
            print(errorString)
            with open(ERRORFILE, 'a+') as errorfile:
                errorfile.write(errorString)

            chosen = target if target else self.bestCandidate
    
            if PLOT_ERR:
                self.plot(myVmin = 0, myVmax = 1000, target=chosen)
                self.plot()
            if ONLY_FLAG_ERRORS or e=='far' or e=='unlikely':
                return
            else:
                print("raising")
                raise


def extraction(filenames):
    all_redshifts = {}
    all_kronMags = {}
    all_kronRads = {}
    for snType in TYPES:
        all_redshifts[snType] = []
        all_kronMags[snType] = []
        all_kronRads[snType] = []

    ''' load event redshifts' dictionary '''
#TODO combine with plotRedshifts method
    zdict = {}
    zfile = open('new_ps1z.dat', 'r')
    zfile.readline() #get rid of heade

#100014, 300220, and 380108 have not in zdict
# 100014, 150381, 360140 have not in sdss
        
    for line in zfile:
        parts = line.split()
        eventId = parts[0][3:]
        redshift = float(parts[1])
        zdict[eventId] = redshift

    zfile.close()
    #not in zdict, looked up from ps1 website 
    #http://telescopes.rc.fas.harvard.edu/ps1/2014/alerts/
    zdict['100014'] = 0.357
    zdict['300220'] = 0.094
    zdict['380108'] = 0.159

    '''load event type dictionary'''
    typeDict = {}
    typefile = open('ps1confirmed_only_sne_without_outlier.txt', 'r')
    typefile.readline() #get rid of header
    for line in typefile:
        parts = line.split()
        eventId = parts[0][3:]
        eventType = parts[1]
        typeDict[eventId] = eventType
    typefile.close()

    '''load event location dictionary'''
    db = pd.read_table('alertstable_v3',sep=None,index_col = False,
                   engine='python')
    db2 = pd.read_table('alertstable_v3.lasthalf',sep=None,index_col = False,
                    engine='python')
    db = db.append(db2,ignore_index=True)

    '''load prerun sdss queries'''
    fullSdssTable = Table.read('sdss_queries.dat', format='ascii')
    fullSdssTable = fullSdssTable.group_by('idnum')
    
    '''load real host data'''
    with open('hosts.dat', 'r') as hostsfile:
        hostsData = hostsfile.read()
    # convert to dictionary from dictionary string
    hostsData = ast.literal_eval(hostsData)

    if WRITE_CSV:
        #create destination directory if it does not exist
        if not os.path.isdir(DESTDIR):
            os.mkdir(DESTDIR)
        destfile = open(DESTDIR + WRITE_CSV, "w+")
        csvwriter = csv.writer(destfile)
        csvwriter.writerow(HEADER)
    if PRINT_DATA:
        print(HEADER)

    cache = []

#    if MAG_TEST_ALL or MAG_TEST_STDEV:
#        magdestfile = open(MAGFILE, "w+")
#        csvwriter = csv.writer(magdestfile)

    for filename in filenames:
        ''' clean up and set up '''
        #clear bestCandidate to avoid bad plotting
        bestCandidate = None

        # to extract transient and filter number from filename of the form
        # */psc190369.6.fits
        dotSplit = filename.split('.')
        # transient identifier is everything after the last 'c' but before
        # the second to last dot
        idNumString = dotSplit[-3].split('c')[-1] #used for getting hectospec data
        idNum  = int(idNumString)
        # filter number is between second to last dot and last dot
        
        # find pixel coordinates of event
        e = db.where(db['eventID'] == idNum).dropna()
        eRa = e['ra'].values[0] #values gives np arrays
        eDec = e['dec'].values[0] #'hh:mm:ss.sss'

        event = {}
        event['coords'] = SkyCoord(eRa, eDec, unit=(u.hourangle, u.deg))
        event['ra'] = event['coords'].ra.deg
        event['dec'] = event['coords'].dec.deg
#TODO: ircs or fk5

        # get event pixel coords
        w = WCS(filename)
        event['x'], event['y'] = w.all_world2pix(event['ra'], event['dec'], 1)
        
        images = []
        good_locations = []
        bad_locations = []
        good_photozs = []
        bad_photozs = []
        for x in range(3,7):
            images[x] = Image(idNumString, x, event)
            photozMatched = images[x].attemptBestCandidate()
#TODO switch to absolute distance? take into account size? make sure we aren't correcting big galaxies
            if images[x].objCoords[x.bestCandidate].separation(event['coords']) < MINDIST:
                good_locations.append(x)
            else:
                bad_locations.append(x)
            if photozMatched:
                good_photozs.append(x)
            else:
                bad_photozs = []
        
        '''choose candidates'''        
        if good_locations:
            filter_to_use = good_locations[0]
            goodCoords = images[filter_to_use].objCoords[images[filter_to_use].bestCandidate]
#TODO do I use object at event coords or good coords?
            for x in bad_locations:
                images[x].bestCandidate = images[x].check_at(event['coords'])
        elif good_photozs:
            filter_to_use = good_photozs[0]
            goodCoords = images[filter_to_use].objCoords[images[filter_to_use].bestCandidate]
            #use object at that location in all images
            for x in range(3,7):
                images[x].bestCandidate = images[x].check_at(goodCoords)
        else:
            images[3].errorProtocol("UNABLE TO FIND GOOD CANDIDATE FOR THIS EVENT")
            global BAD_COUNT
            BAD_COUNT += 1
            continue
        
        cache = [None]*6
        # get final data from the known good filter first
        cache[filter_to_use] = images[filter_to_use].getFinalData(images[filter_to_use].bestCandidate)
        for i in range(3,7):
            if i == filter_to_use: #alread done above
                pass
            elif images[i].bestCandidate == None:
                cache[i] = modifyFinalDataFrom(cache[filter_to_use])
            else:
                cache[i] = images[i].getFinalData()
                
        csvwriter.writerow(cache[3].extend(cache[4].extend(cache[5].extend(cache[6]))))

        if PLOT_ALL:
            for image in images[3:]:
                image.plot()
                image.plot(myVmin = 0, myVmax = 1000)
                
        
        
        
        
        
        
            newFluxParams =  (swappedData,
                               self.objects['x'][bestCandidate],
                               self.objects['y'][bestCandidate],
                               self.objects['a'][bestCandidate],
                               self.objects['b'][bestCandidate],
                               self.objects['theta'][bestCandidate], 2.5*kronradKpc[bestCandidate])
            #TODO remove any unnecessary
            badImageDict = {'filterNum': filterNum, 'objects': objects,
                            'kronradKpc': kronradKpc, 'separationKpc': separationKpc,
                            'area': area,
                            'magnitude': magnitude, 'absMag': absMag,
                            'objCoords': objCoords, 'photozs': photozs,
                            'm_0': m_0, 'swappedData': swappedData,
                            'segmap': segmap, 'old_best': bestCandidate,
                            'chanceCoincidence': chanceCoincidence,
                            'newFluxParams': newFluxParams,
                            'finalProperties':finalProperties}
            BAD_IMAGES.append(badImageDict)

            cache.extend(finalProperties)
                
            # check if all images are in the same place
            first_location = BAD_IMAGES[0]
            for im in BAD_IMAGES:
#TODO 
                '''
                1. if all are in same place, do nothing.
                2. if one is in event location, use it, correct others
                3. elif one has good photoz use it, flag photoz chosen
                4. else use one with best chance coincidence and error flag
'''
#TODO in earlier photoz checking, see if multiple have good photozs and flag 


                errstring = "correcting " + idNumString + '.' + str(filterNum) + '\n'
                print(errstring)
                with open(ERRORFILE, 'a+') as errorfile:
                    errorfile.write(errstring)
                finalProperties, newFluxParams = GOOD_IMAGE
                #TODO check indices are correct
                goodCoords = SkyCoord(finalProperties[10], #new ra[bestCandidate]
                                      finalProperties[12], unit=u.deg) #(ra,dec)
                for imageDict in BAD_IMAGES:
                    fixed = False
                    for k in range(len(imageDict['objCoords'])):
                        # look for an object at the new good location
                        if imageDict['objCoords'][k].separation(goodCoords) < MINDIST:
                            newBestCandidate = k
                            newEllipticity = 1 - (imageDict['objects']['b'][newBestCandidate]/
                                                imageDict['objects']['a'][newBestCandidate])
                            newOffby = hostCoords.separation(imageDict['objCoords'][newBestCandidate]).arcsec
                            newPixelRank = getPixelRank()

                            newProperties = [imageDict['kronradKpc'][newBestCandidate],
                                            imageDict['separationKpc'][newBestCandidate],
                                            imageDict['area'][newBestCandidate],
                                            imageDict['separationKpc'][newBestCandidate] /\
                                            imageDict['area'][newBestCandidate],
                                            imageDict['objects']['x'][newBestCandidate] - eventX,
                                            imageDict['objects']['y'][newBestCandidate] - eventY,
                                            imageDict['magnitude'][newBestCandidate],
                                            imageDict['absMag'][newBestCandidate],
                                            imageDict['objects']['theta'][newBestCandidate],
                                            newEllipticity,
                                            imageDict['objCoords'][newBestCandidate].ra.deg,
                                            hostRa,
                                            imageDict['objCoords'][newBestCandidate].dec.deg,
                                            hostDec, newOffby,
                                            eventz, imageDict['photozs'][newBestCandidate],
                                            newPixelRank,
                                            imageDict['chanceCoincidence'][newBestCandidate]]
                            fixed = True
                            break
                    if not fixed: # no objects in center detected in bad image, use data from good image
                        # but update magnitude
                        newFlux, _fluxerr, _flag = sep.sum_ellipse(*newFluxParams, subpix=1)
                        newMagnitude = -2.5 * np.log10(newFlux/float(image_file[0].header['MJD-OBS'])) + imageDict['m_0']
#TODO just save the old pixel rank
                        newPixelRank = getPixelRank(imageDict['swappedData'],
                            eventX, eventY, imageDict['segmap'], imageDict['old_best'])
                        newAbsMag = newMagnitude - 5*np.log10(dL) - 10
                                    # Observed number density of galaxies brighter than magnitude M (From Berger 2010)

#TODO check correctness
                        newProperties = finalProperties[:] #copy list
                        oldMagnitude = newProperties[6]
                        newProperties[6] = newMagnitude
                        newProperties[7] = newAbsMag
                        newProperties[17] = newPixelRank
                        oldChanceCoincidence = newProperties[18]
                        #adjust chanceCoincidence for change in magnitude
                        newProperties[18] = 1 - (1 - oldChanceCoincidence)**(10**(0.33*(newMagnitude - oldMagnitude)))
#TODO make sure above math is correct
                    #TODO fix out of bounds possibility
                    numColumnsOnLeft = 1 + (imageDict['filterNum'] - 3)*len(perImageHeaders)
                    # repair cache
                    cache = cache[:numColumnsOnLeft] + newProperties\
                            + cache[numColumnsOnLeft + len(perImageHeaders):]
                    BAD_IMAGES.remove(imageDict)

            if chanceCoincidence[bestCandidate] > LIKELIHOOD_THRESH:
                self.errorProtocol("unlikely")

            ''' end getData block'''
            #collect data for redshift plot
            if PLOT_REDSHIFTS and filterNum == 6:
                raise Exception("needs fixing, indices are wrong here")
                thisType = typeDict[idNumString]
                all_redshifts[thisType].append(cache[-2])
                all_kronMags[thisType].append(cache[-10])
                all_kronRads[thisType].append(cache[-14])


            lastIdNum = idNum
            lastFilter = filterNum

#TODO remove
        except AssertionError:
            print("here")
            if MAG_TEST_ALL or MAG_TEST_STDEV:
                continue
            else:
                raise
        except Exception as e:
            self.errorProtocol(e)
    if PLOT_REDSHIFTS:
        #TYPE_COLORS = {'SNIIn':'co', 'SNIa':'ro', 'SNII': 'bo', 'SNIbc':'go', 'SLSNe': 'mo'}

        # plot magnitude vs. redshift
        for snType in TYPES:
            plt.plot(all_redshifts[snType], all_kronMags[snType], TYPE_COLORS[snType])

        plt.xlabel('Redshifts')
        plt.ylabel('Magnitudes')
        plt.savefig('redshifts_vs_magnitudes', dpi=150)
        plt.show()
        plt.close()

        areas = {}
        # plot magnitude vs. area
        for snType in TYPES:
            all_kronMags[snType] = np.array(all_kronMags[snType])
            all_kronRads[snType] = np.array(all_kronRads[snType])
            areas[snType] = np.pi * all_kronRads[snType]**2
            plt.plot(all_redshifts[snType], areas[snType], TYPE_COLORS[snType])

        plt.xlabel('Redshifts')
        plt.ylabel('Surface Areas')
        plt.savefig('redshifts_vs_areas', dpi=150)
        plt.show()
        plt.close()

        surface_brightness = {}
        # plot magnitude vs. surface brightness
        for snType in TYPES:
            surface_brightness[snType] = all_kronMags[snType]/areas[snType]
            plt.plot(all_redshifts[snType], surface_brightness[snType], TYPE_COLORS[snType])

        plt.xlabel('Redshifts')
        plt.ylabel('Surface Brightness')
        plt.savefig('redshifts_vs_brightness', dpi=150)
        plt.show()
        plt.close()

    if MAG_TEST_ALL or MAG_TEST_STDEV:
#        all_myMags2 = np.array(all_myMags)
#        all_realMags2 = np.array(all_realMags)
#        #magdestfile.close()
#        plt.plot(all_myMags2, all_realMags2 - all_myMags2, 'bo')
#        plt.xlabel('My magnitudes')
#        plt.ylabel('Difference')#'SDSS magnitudes')
#        plt.savefig('magplot_mymags_vs_dif_leaving_outliers_newDefault', dpi=150)
#        plt.show()
#        plt.close()
#
#        plt.plot(all_realMags2, all_realMags2 - all_myMags2, 'bo')
#        plt.xlabel('SDSS magnitudes')
#        plt.ylabel('Difference')#'SDSS magnitudes')
#        plt.savefig('magplot_sdssmags_vs_dif_leaving_outliers_newDefault', dpi=150)
#        plt.show()
#        plt.close()
#
#        plt.plot(all_myMags2, all_realMags2, 'bo')
#        plt.xlabel('My magnitudes')
#        plt.ylabel('SDSS Magnitudes')#'SDSS magnitudes')
#        plt.savefig('magplot_sdssmags_vs_mymags_leaving_outliers_newDefault', dpi=150)
#        plt.show()
#        plt.close()
#
#        # plot again w/o median points
#        all_myMags3 = []
#        all_realMags3 = []
#        for l in range(len(all_myMags2)):
#            if all_myMags2[l] != all_realMags2[l]:
#                all_myMags3.append(all_myMags2[l])
#                all_realMags3.append(all_realMags2[l])
#
#        all_myMags4 = np.array(all_myMags3)
#        all_realMags4 = np.array(all_realMags3)
        global all_realMagsFiltered
        global all_myMagsFiltered
        all_realMagsFiltered = [[], [], [], [], [], [], []]
        all_myMagsFiltered = [[], [], [], [], [], [], []]
        for x in range(3,7):
            for l in range(len(all_myMags)):
                if all_myMags[l] != all_realMags[l]:
                    all_myMagsFiltered.append(all_myMags[l])
                    all_realMagsFiltered.append(all_realMags[l])

            all_realMagsFiltered = np.array(all_realMagsFiltered)
            all_myMagsFiltered = np.array(all_myMagsFiltered)
            print(x)

        plt.plot(all_myMagsFiltered[3], all_realMagsFiltered[3] - all_myMagsFiltered[3], 'bo',
                 all_myMagsFiltered[4], all_realMagsFiltered[4] - all_myMagsFiltered[4], 'go',
                 all_myMagsFiltered[5], all_realMagsFiltered[5] - all_myMagsFiltered[5], 'ro',
                 all_myMagsFiltered[6], all_realMagsFiltered[6] - all_myMagsFiltered[6], 'yo',)
        plt.xlabel('My magnitudes')
        plt.ylabel('Difference')#'SDSS magnitudes')
        plt.savefig('deletable', dpi=150)
        plt.show()
        plt.close()
            #magplot_mymags_vs_dif_nonzero_outliersCoerced_noGalaxies_noDim
#            plt.plot(all_realMagsFiltered, all_realMagsFiltered - all_myMagsFiltered, 'bo')
#            plt.xlabel('SDSS magnitudes')
#            plt.ylabel('Difference')#'SDSS magnitudes')
#            plt.savefig('magplot_sdssmags_vs_dif_nonzero_leaving_outliers_newDefault'+str(x), dpi=150)
#            plt.show()
#            plt.close()
#
#            plt.plot(all_myMagsFiltered, all_realMagsFiltered, 'bo')
#            plt.xlabel('My magnitudes')
#            plt.ylabel('SDSS Magnitudes')#'SDSS magnitudes')
#            plt.savefig('magplot_sdssmags_vs_mymags_nonzero_leaving_outliers_newDefault'+str(x), dpi=150)
#            plt.show()
#            plt.close()
#
    # write last data
    cache.extend([FILLER_VAL]*(1+4*len(perImageHeaders)-len(cache)))
    if WRITE_CSV:
        csvwriter.writerow(cache)
        destfile.close()
    if PRINT_DATA:
        print(cache)

def main():
#TODO remove
    import time
    start = time.time()
    #figure out which files to use based on value specified at top
    if FILES == 'all' or FILES =='range' or FILES =='new random':
        #CHANGED now only looks for .3 files, assuming the rest are there
        filenames = sorted(glob.glob(SOURCEDIR + '/ps1hosts/psc*.3.fits'))
        if FILES == 'range':
            extraction(filenames[RANGE[0]:RANGE[1]])
        elif FILES == 'new random':
            randFiles = []
            for i in range(20):
                randFiles.append(filenames[int(len(filenames)*random.random())])
            extraction(randFiles)
        elif FILES =='all':
            extraction(filenames)
    elif FILES == 'preset random':
        from presetrandomfiles import fileset
        extraction(fileset[:60])
    elif FILES == 'nonsquare':
        from nonsquare import fileset
        extraction(fileset)
    elif FILES == 'specified':
        extraction(SPECIFIED)
    else:
        raise Exception('invalid FILE specification')
    end = time.time()
    print(end - start)

if __name__ == "__main__":
     main()
     
'''
            global objects
            global bestCandidate
            global magnitude
            global sdssTable
            global chanceCoincidence
            global separation
            global filename_d
            global filename
            global blacklist
            global swappedData
            global image_file
            global ra
            global dec
            global hostRa
            global hostDec
            global eventRa
            global eventDec
            global colRealMags
            global colMyMags
            global colFluxes
            global zdict
            global all_myMags
            global all_realMags
            global BAD_IMAGES
            global GOOD_IMAGE
            global m_0s
            global m_0
            global size
            global R_effective
            global hostsData
            global all_myMagsFiltered
            global all_realMagsFiltered
            global all_redshifts
            global all_kronMags
            global all_kronRads
            global kronrad
            global flux
            global z
            global photozs
            global eventz

            global segmap

    # My stupid workaround for debugging, so I can access the variables from the console
    global objects
    global bestCandidate
    global magnitude
    global sdssTable
    global chanceCoincidence
    global separation
    global filename
    global blacklist
    global swappedData
    global image_file
    global ra
    global dec
    global hostRa
    global hostDec
    global eventRa
    global eventDec
    global colRealMags
    global colMyMags
    global colFluxes
    global zdict
    global all_myMags
    global all_realMags
    global BAD_IMAGES
    global GOOD_IMAGE
    global m_0s
    global m_0
    global size
    global R_effective
    global hostsData
    global all_myMagsFiltered
    global all_realMagsFiltered
    global all_redshifts
    global all_kronMags
    global all_kronRads
    global kronrad
    global flux
    global z
    global photozs
    global eventX
    global eventY
    global idNum
    global filterNum
    global filename_d
'''
