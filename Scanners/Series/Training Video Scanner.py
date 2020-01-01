# Version Date: 2017-08-15
# By Jason Michas original code borrowed from Mitchell Arends ExtendedPersonalMedia-Agent.bundle

import re, os, os.path, datetime, ConfigParser, logging
import inspect                                                       # getfile, currentframe
import Media, VideoFiles, Stack, Utils
from mp4file import mp4file, atomsearch

# Year regular expression
YEAR_REGEX = r'^(?P<year>[0-9]{4})$'

# PMS data location
PLEX_ROOT  = os.path.abspath(os.path.join(os.path.dirname(inspect.getfile(inspect.currentframe())), "..", ".."))
if not os.path.isdir(PLEX_ROOT):
  path_location = { 'Windows': '%LOCALAPPDATA%\\Plex Media Server',
                    'MacOSX':  '$HOME/Library/Application Support/Plex Media Server',
                    'Linux':   '$PLEX_HOME/Library/Application Support/Plex Media Server' }
  PLEX_ROOT = os.path.expandvars(path_location[Platform.OS.lower()] if Platform.OS.lower() in path_location else '~')  # Platform.OS:  Windows, MacOSX, or Linux

# setup logging
LOG_FORMAT = '%(asctime)s| %(levelname)-8s| %(message)s'
loggingPath = os.path.join(PLEX_ROOT, 'Logs', 'training_video_scanner.log')
logging.basicConfig(filename=loggingPath, format=LOG_FORMAT, level=logging.DEBUG)

def log(methodName, message, *args):
    '''
        Create a log message given the message and arguments
    '''
    logMsg = message
    # Replace the arguments in the string
    if args:
        logMsg = message % args

    logMsg = methodName + ' :: ' + logMsg
    logging.debug(logMsg)

class CustomParserConfig(object):
    '''
        Finds the configuration for the specified file
    '''

    def __init__(self, filePath):
        self.filePath = filePath
        self.config = ConfigParser.SafeConfigParser()
        self.config.read(filePath)

    def fileNameRegex(self):
        return self.config.get('parser', 'file.name.regex')

class ConfigMap(object):

    def findCustomParser(self, rootDir, filePath):
        customParser = None

        configFile = self.findConfigFile(rootDir, filePath)
        if configFile is not None:
            log('__init__', 'found config file %s for media file %s', configFile, filePath)
            # Create the config
            config = CustomParserConfig(configFile)
            # and custom parser
            customParser = CustomMediaParser(config)

        return customParser

    def findConfigFile(self, rootDir, filePath):
        rootDirFound = False
        parentDir = filePath

        # iterate over the directory
        while not rootDirFound:
            # Get the parent directory for the file
            parentDir = os.path.dirname(parentDir)

            log('findConfigFile', 'looking in parent directory %s', parentDir)
            # create the file path
            configFilePath = os.path.normcase(parentDir + '/ext-media.config')
            log('findConfigFile', 'determining whether config file %s exists', configFilePath)
            if os.path.exists(configFilePath) and os.path.isfile(configFilePath):
                log('findConfigFile', 'config file %s exists', configFilePath)
                return configFilePath

            # check to see if this is the root dir
            if parentDir == rootDir:
                rootDirFound = True

class BaseMediaParser(object):
    '''
        Parses the file name and determines the type of tile that was found
    '''

    # Episode name REGEX
    partRegexes = [
                    r'(?P<episodeTitle>.+)(\.[ ]*|-[ ]*)(part[0-9]+|pt[0-9]+)',
                    r'(?P<episodeTitle>.+)([ ]+)(part[0-9]+|pt[0-9]+)'
                    ]

    def stripPart(self, episodeTitle):
        processed = episodeTitle
        # Test whether it contains part
        for partRegex in self.partRegexes:
            match = re.search(partRegex, processed)
            if match:
                log('stripPart', 'episode title %s contains part', processed)
                processed = match.group('episodeTitle').strip()
                log('stripPart', 'stripped episode title: %s', processed)
                break

        return processed

    def scrub(self, string):
        processed = ''
        matches = re.split(r'[\.\-_]+', string)
        idx = 1
        if matches is not None:
            for match in matches:
                processed = processed + match
                if idx < len(matches):
                    processed = processed + ' '
                idx = idx + 1
        else:
            processed = string

        log('scrubString', 'original: [%s] scrubbed: [%s]', string, processed)
        return processed

    def setValues(self, match):
        pass

    def getSupportedRegexes(self):
        return []

    def containsMatch(self, mediaFile):
        log('contains match scanner', "*************************")
        retVal = False
        # Iterate over the list of regular expressions
        for regex in self.getSupportedRegexes():
            # Find out what file format is being used
            match = re.search(regex, mediaFile, re.IGNORECASE)
            if match:
                retVal = True
                break

        return retVal


    def parse(self, mediaFile, lang):
        self.mediaFile = mediaFile
        self.lang = lang

        # Iterate over the list of regular expressions
        for regex in self.getSupportedRegexes():
            # Find out what file format is being used
            match = re.search(regex, mediaFile, re.IGNORECASE)
            log('parse', 'regex %s - matches: %s', regex, match)
            if match:
                log('parse', 'found matches')
                self.setValues(match)

                # Determine if the containing directory is numeric and 4 digits long - if so treat it like it's a year
                self.seasonYear = None
                #match = re.search(YEAR_REGEX, str(self.seasonNumber))
                #if match:
                    #self.seasonYear = self.seasonNumber

                break

    def getShowTitle(self):
        return self.showTitle

    def getSeasonNumber(self):
        return self.seasonNumber

    def getSeasonTitle(self):
        return self.seasonTitle

    def getSeasonYear(self):
        return self.seasonYear
        
    def getEpisodeTitle(self):
        return self.episodeTitle

    def getEpisodeNumber(self):
        return self.episodeNumber
      

class SeriesEpisodeMediaParser(BaseMediaParser):
    
    def getSupportedRegexes(self):
        return [
                #Lynda.com.Angular2.for.NET.Developers\1. 4. Course Overview\01. Using the exercise files.mp4
                r'(?P<showTitle>[^\\/]+)[\\/][sc|season|chapter]*?[ ]*?(?P<seasonNumber>[0-9]+)\.[ \d\.]+(?P<seasonTitle>[^\\/]+){0,1}[\\/](?P<showNumber>[0-9]{0})[_-]{0,1}?[\d\d]{0,1}?[_-]{0,1}?(?P<episodeNumber>\d+)\.[ _]*(?P<episodeTitle>.*)\.(?P<ext>.+)$',
                #Lynda.com.Angular2.for.NET.Developers\1. Course Overview\500547_01_02_XR15_SampleMovieDb.mp4
                r'(?P<showTitle>[^\\/]+)[\\/][sc|season|chapter]*?[ ]*?(?P<seasonNumber>[0-9]+)([-\. ]+(?P<seasonTitle>[^\\/]+)){0,1}[\\/](?P<showNumber>[0-9]+)_\d\d_(?P<episodeNumber>\d+)[ _]*\w\w\d\d[-\.]{0,1}[ _]*(?P<episodeTitle>.*)\.(?P<ext>.+)$',
                #Lynda.com.Angular2.for.NET.Developers\1. Course Overview\01_02-Using the exercise files.mp4
                r'(?P<showTitle>[^\\/]+)[\\/][sc|season|chapter]*?[ ]*?(?P<seasonNumber>[0-9]+)([-\. ]+(?P<seasonTitle>[^\\/]+)){0,1}[\\/](?P<showNumber>[0-9]*)[_-]{0,1}?[\d\d]{0,1}?[_-]{0,1}?(?P<episodeNumber>\d+)[ _-]*?[\w\w\d\d]*?[-\.]{0,1}[ _]*(?P<episodeTitle>.*)\.(?P<ext>.+)$',
                #Udemy Entrepreneurship For Noobees/01_-_Welcome_to_Entrepreneurship_for_Noobees/01_-_Introduction_and_Welcome.mp4
                r'(?P<showTitle>[^\\/]+)[\\/][sc|season|chapter]*?[ ]*?(?P<seasonNumber>[0-9]+)([-_\. ]+(?P<seasonTitle>[^\\/]+)){0,1}[\\/](?P<showNumber>[0-9]{0})(?P<episodeNumber>\d+)[ _-]*(?P<episodeTitle>.*)\.(?P<ext>.+)$'
                ] 
    
    def setValues(self, match):
        self.showTitle = self.scrub(match.group('showTitle').strip())
        self.seasonNumber = int(match.group('seasonNumber').strip())
        self.seasonTitle = self.scrub(match.group('seasonTitle').strip())
        self.episodeNumber = int(match.group('episodeNumber').strip())
        self.episodeTitle = self.scrub(self.stripPart(match.group('episodeTitle').strip()))


class CustomMediaParser(BaseMediaParser):

    def __init__(self, config):
        self.parserConfig = config

    def getSupportedRegexes(self):
        regexes = []

        # Check the config to see if a regex has been set
        configRegex = self.parserConfig.fileNameRegex()
        if configRegex is not None:
            regexes.append(configRegex)
        log('CustomMediaParser.getSupportedRegexes', 'custom file name regexes in use %s', str(regexes))
        return regexes

    def setValues(self, match):
        # Set all of the supported values
        self.showTitle = self.scrub(match.group('showTitle').strip())
        # get the season related values
        self.seasonTitle = match.group('seasonTitle').strip()
        self.seasonNumber = int(match.group('seasonNumber').strip())
        # get the episode related values
        self.episodeYear = int(match.group('episodeYear').strip())
        self.episodeMonth = int(match.group('episodeMonth').strip())
        self.episodeDay = int(match.group('episodeDay').strip())
        self.episodeNumber = int(match.group('episodeNumber').strip())
        self.episodeTitle = self.scrub(self.stripPart(match.group('episodeTitle').strip()))

        # create the episode release date
        self.episodeReleaseDate = None
        if self.episodeYear is not None and self.episodeMonth is not None and self.episodeDay is not None:
            # Create the date
            self.episodeReleaseDate = datetime.datetime(int(self.episodeYear), int(self.episodeMonth), int(self.episodeDay))

        # create the season number from the episode year
        if self.seasonNumber is None:
            self.seasonNumber = self.episodeYear

# Look for episodes.
def Scan(path, files, mediaList, subdirs, language=None, root=None):

    subdirs_to_whack = []
    for subdir in subdirs:
        excludedBasename = os.path.basename(subdir).lower()
        log('Subdir', 'basename: %s', excludedBasename)
        if str(excludedBasename) == 'exercise files':
            log('Subdir to Whack', excludedBasename)
            subdirs_to_whack.append(subdir)
        if str(excludedBasename) == 'files':
            log('Subdir to Whack', excludedBasename)
            subdirs_to_whack.append(subdir)
        if str(excludedBasename) == 'source files':
            log('Subdir to Whack', excludedBasename)
            subdirs_to_whack.append(subdir)

    subdirs_to_whack = list(set(subdirs_to_whack))
    for subdir in subdirs_to_whack:
        subdirs.remove(subdir)
        log('Subdir Ignored', os.path.basename(subdir).lower())

    # List of series parsers
    series_parsers = [SeriesEpisodeMediaParser()]
    # Stores the configuration map
    config_map = ConfigMap()

    log('Scan', 'path: %s', path)
    log('Scan', 'files: %s', files)
    log('Scan', 'mediaList: %s', mediaList)
    log('Scan', 'subdirs: %s', subdirs)
    log('Scan', 'language: %s', language)
    log('Scan', 'root: %s', root)

    # Scan for video files.
    VideoFiles.Scan(path, files, mediaList, subdirs, root)

    for idx, file in enumerate(files):
        log('Scan', 'file: %s', file)

        absFilePath = os.path.abspath(file)
        absRootDir = os.path.abspath(root)
        log('Scan', 'absolute file path: %s', absFilePath)

        parsers = []

        # Check the customParser map for this file
        customParser = config_map.findCustomParser(absRootDir, absFilePath)
        if customParser is not None:
            # If we have a custom parser use only this parser on the file
            parsers = [customParser]
        else:
            # We are using the default parsers
            parsers = series_parsers

        # Iterate over the list of parsers and parse the file path
        for parser in parsers:
            log('Scan', 'parser %s', parser)
            if parser.containsMatch(absFilePath) is True:
                log('Scan', 'parser %s contains match - parsing file path', parser)
                parser.parse(absFilePath, language)

                showTitle = parser.getShowTitle()
                log('Scan', 'show title: %s', showTitle)
                seasonNumber = parser.getSeasonNumber()
                log('Scan', 'season number: %s', seasonNumber)
                seasonTitle = parser.getSeasonTitle()
                log('Scan', 'season title: %s', seasonTitle)
                seasonYear = parser.getSeasonYear()
                log('Scan', 'season year: %s', seasonYear)
                episodeNumber = parser.getEpisodeNumber()
                log('Scan', 'episode number: %s', episodeNumber)
                episodeTitle = parser.getEpisodeTitle()
                log('Scan', 'episode title: %s', episodeTitle)

                vid = Media.Episode(showTitle, seasonNumber, episodeNumber, episodeTitle, seasonYear)
                vid.parts.append(file)
                mediaList.append(vid)
                break

    # stack files
    log('Scan', 'stack media')
    Stack.Scan(path, files, mediaList, subdirs)
    log('Scan', 'media list %s', mediaList)