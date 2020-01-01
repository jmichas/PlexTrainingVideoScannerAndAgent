# Version Date: 2017-08-15
# By Jason Michas original code borrowed from Mitchell Arends ExtendedPersonalMedia-Agent.bundle

import datetime, os, sys, time, re, locale, ConfigParser, urllib2, urllib
from string import Template
from xml.dom import minidom


# Series agent name
SERIES_AGENT_NAME = 'Training Video Agent'

def logDebug(methodName, message, *args):
    if bool(Prefs['logger.debug.enabled']):
        Log(methodName + ' :: ' + message, *args)

def log(methodName, message, *args):
    Log(methodName + ' :: ' + message, *args)

# Only use unicode if it's supported, which it is on Windows and OS X,
# but not Linux. This allows things to work with non-ASCII characters
# without having to go through a bunch of work to ensure the Linux
# filesystem is UTF-8 "clean".
#
def unicodize(s):
    filename = s

    logDebug('unicodize', 'before unicodizing: %s', str(filename))
    if os.path.supports_unicode_filenames:
        try: filename = unicode(s.decode('utf-8'))
        except: pass
    logDebug('unicodize', 'after unicodizing: %s', str(filename))
    return filename

def findFile(filePaths, fileNames):
    '''
    Find one of the specified file names in the list starting at the lowest directory passed in and
    walking up the directory tree until the root directory is found or one of the files in the list is found
    '''
    for filePath in filePaths:
        rootDirFound = False
        parentDir = filePath

        # Get the parent directory for the file
        if os.path.isfile(filePath):
            parentDir = os.path.dirname(parentDir)

        # iterate over the directory
        while not rootDirFound:
            logDebug('findFile', 'looking in parent directory %s', parentDir)
            # create the file path
            for fileName in fileNames:
                pathToFind = os.path.normpath(os.path.normcase(os.path.join(parentDir, fileName)))
                logDebug('findFile', 'determining whether file %s exists', pathToFind)
                if os.path.exists(pathToFind) and os.path.isfile(pathToFind):
                    logDebug('findFile', 'file %s exists', pathToFind)
                    return pathToFind
                else:
                    logDebug('findFile', 'file %s does not exist', pathToFind)

            # go up a directory
            logDebug('findFile', 'going up a directory')
            newDir = os.path.abspath(os.path.dirname( parentDir ))

            logDebug('findFile', 'new directory path %s', newDir)
            # if the new directory and parent directory are the same then we have reached the top directory - stop looking for the file
            if newDir == parentDir:
                logDebug('findFile', 'root directory %s found - stopping directory traversal', newDir)
                rootDirFound = True
            else:
                parentDir = newDir

    return None

def isSubdir(path, directory):
    '''
    Returns true if *path* in a subdirectory of *directory*.
    '''
    if len(path) > len(directory):
        sep = os.path.sep.encode('ascii') if isinstance(directory, bytes) else os.path.sep
        dirComp = directory.rstrip(sep) + sep
        logDebug('isSubdir','comparing [%s] to [%s]', path, dirComp)
        if path.startswith(dirComp):
            logDebug('isSubdir', 'path is a subdirectory')
            return True
    return False

def loadTextFromFile(filePath):
    '''
    Load the text text from the specified file
    '''
    textUnicode = None
    # If the file exists read in its contents
    if os.path.exists(filePath) is True:
        text = None
        logDebug('loadTextFromFile', 'file exists - reading contents')
        try:
            # Read the text from the file
            text = Core.storage.load(filePath, False)
        except Exception as e:
            logDebug('loadTextFromFile', 'error occurred reading contents of file %s : %s', filePath, e)

        # try to decode the contents
        try:
            # decode using the system default
            logDebug('loadTextFromFile', 'decoding string using utf-8 - not ignoring errors')
            textUnicode = unicode(text, 'utf-8')
        except Exception as e:
            logDebug('loadTextFromFile', 'could not decode contents of summary file %s : %s', filePath, e)
            # decode using utf-8 and ignore errors
            logDebug('loadTextFromFile', 'decoding string using utf-8 - ignoring errors')
            textUnicode = unicode(text, 'utf-8', errors='ignore')

    return textUnicode

def findSeasonSummary(filePaths, fileNames):
    seasonSummary = None
    logDebug('findSeasonSummary', 'looking for files with names %s in path list %s', str(fileNames), str(filePaths))
    filePath = findFile(filePaths, fileNames)
    if filePath != None:
        log('findSeasonSummary', 'found season summary file %s', filePath)
        seasonSummary = loadTextFromFile(filePath)
    else:
        log('findSeasonSummary', 'season summary file not found')

    return seasonSummary

def findShowSummary(filePaths, fileNames):
    showSummary = None
    logDebug('findShowSummary', 'looking for files with names %s in path list %s', str(fileNames), str(filePaths))
    filePath = findFile(filePaths, fileNames)
    if filePath != None:
        log('findShowSummary', 'found show summary file %s', filePath)
        showSummary = loadTextFromFile(filePath)
    else:
        log('findShowSummary', 'show summary file not found')

    return showSummary

class BaseMediaParser(object):
    '''
        Parses the file name and determines the type of tile that was found
    '''

    fileNameRegex = r'^(?P<fileWithoutExt>.*)\..+$'

    # Episode name REGEX
    partRegexes = [
                    r'(?P<episodeTitle>.+)(\.[ ]*|-[ ]*)(part[0-9]+|pt[0-9]+)',
                    r'(?P<episodeTitle>.+)([ ]+)(part[0-9]+|pt[0-9]+)'
                    ]

    def __init__(self):
        self.showSummary = None
        self.seasonSummary = None
        self.episodeTitle = None
        self.episodeSummary = None
        self.episodeReleaseDate = None
        self.seasonTitle = None

    def stripPart(self, episodeTitle):
        processed = episodeTitle
        # Test whether it contains part
        for partRegex in self.partRegexes:
            match = re.search(partRegex, processed)
            if match:
                logDebug('stripPart', 'episode title %s contains part', processed)
                processed = match.group('episodeTitle').strip()
                logDebug('stripPart', 'stripped episode title: %s', processed)
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

        camelCaseMatches = camel_case_split(processed)
        #matchCount = int(len(list(camelCaseMatches)))
        matchCount = len(camelCaseMatches)
        logDebug('matchCount', str(len(camelCaseMatches)))

        if matchCount > 1:
            idx = 1
            processed = ''
            for cmatch in camelCaseMatches:
                processed = processed + cmatch
                logDebug('matchCount', 'idx: %s, matchCount: %s', idx, matchCount)
                if idx < matchCount:
                    processed = processed + ' '
                idx = idx + 1

        logDebug('scrubString', 'original: [%s] scrubbed: [%s]', string, processed)
        return processed

    def setValues(self, match):
        # set the episode title
        #self.episodeTitle = self.scrub(self.stripPart(match.group('episodeTitle').strip()))
        self.showTitle = self.scrub(match.group('showTitle').strip())
        self.seasonNumber = int(match.group('seasonNumber').strip())
        self.seasonTitle = self.scrub(match.group('seasonTitle').strip())
        self.episodeNumber = int(match.group('episodeNumber').strip())
        self.episodeTitle = self.scrub(self.stripPart(match.group('episodeTitle').strip()))
        # set the episode release date
        # if episodeMonth and episodeDay is present in the regex then the episode release date is in the file name and will be used
        if 'episodeMonth' in match.groupdict() and 'episodeDay' in match.groupdict():
            logDebug('setValues', 'episodeMonth found in the regular expression - extracting release date from the file name')
            self.seasonNumber = None
            if 'seasonNumber' in match.groupdict():
                self.seasonNumber = int(match.group('seasonNumber').strip())
            self.episodeYear = None
            if 'episodeYear' in match.groupdict():
                self.episodeYear = int(match.group('episodeYear').strip())
            # if the regex did not contain a year use the season number
            if self.episodeYear is None and self.seasonNumber is not None and self.seasonNumber >= 1000:
                self.episodeYear = self.seasonNumber
            self.episodeMonth = int(match.group('episodeMonth').strip())
            self.episodeDay = int(match.group('episodeDay').strip())
            # Create the date
            logDebug('setValues', 'year %s month %s day %s', self.episodeYear, self.episodeMonth, self.episodeDay)
            self.episodeReleaseDate = datetime.datetime(self.episodeYear, self.episodeMonth, self.episodeDay)
            logDebug('setValues', 'episode date: %s', str(self.episodeReleaseDate))

        # set the episode summary
        # get the summary file path
        # find out what file format is being used
        match = re.search(self.fileNameRegex, self.mediaFile)
        if match:
            fileWithoutExt = match.group('fileWithoutExt').strip()
            logDebug('setValues', 'file name without extension %s', fileWithoutExt)
            summaryFilePath = fileWithoutExt + '.summary'
            logDebug('setValues', 'looking for summary file %s', summaryFilePath)
            # If the summary file exist read in the contents
            if os.path.exists(summaryFilePath) is True:
                logDebug('setValues', 'episode summary file %s exists', summaryFilePath)
                self.episodeSummary = loadTextFromFile(summaryFilePath)
            else:
                logDebug('setValues', 'episode summary file does not exist')

    def getSupportedRegexes(self):
        return []

    def containsMatch(self, mediaFile):
        logDebug('contains match __init__', "=====================")
        retVal = False
        # Iterate over the list of regular expressions
        for regex in self.getSupportedRegexes():
            # Find out what file format is being used
            match = re.search(regex, mediaFile, re.IGNORECASE)
            if match:
                retVal = True
                break

        return retVal


    def parse(self, mediaFile):
        self.mediaFile = mediaFile

        # Iterate over the list of regular expressions
        for regex in self.getSupportedRegexes():
            # Find out what file format is being used
            match = re.search(regex, mediaFile, re.IGNORECASE)
            logDebug('parse', 'regex %s - matches: %s', regex, match)
            if match:
                logDebug('parse', 'found matches')
                self.setValues(match)
                break

    def getEpisodeTitle(self):
        return self.episodeTitle

    def getEpisodeSummary(self):
        return self.episodeSummary

    def getEpisodeReleaseDate(self):
        return self.episodeReleaseDate

    def getSeasonTitle(self):
        return self.seasonTitle


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
        # set the common values
        BaseMediaParser.setValues(self, match)


def Start():
     log('Start', 'starting agents %s, %s', SERIES_AGENT_NAME)
     pass

def get_universal_plex_token():
    return str(Prefs['user.plex.token'])
    # pref_path = os.path.join(Core.app_support_path, "Preferences.xml")
    # if os.path.exists(pref_path):
    #     try:
    #         global_prefs = Core.storage.load(pref_path)
    #         return XML.ElementFromString(global_prefs).xpath('//Preferences/@PlexOnlineToken')[0]
    #     except:
    #         Log.Warn("Couldn't determine Plex Token")
    # else:
    #     Log("Did NOT find Preferences file - please check logfile and hierarchy. Aborting!")

def camel_case_split(identifier):
    matches = re.finditer('.+?(?:(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])|$)', identifier)
    return [m.group(0) for m in matches]

class TrainingVideoAgentTVShows(Agent.TV_Shows):
    name = SERIES_AGENT_NAME
    languages = Locale.Language.All()
    accepts_from = ['com.plexapp.agents.localmedia']

    def search(self, results, media, lang):
        logDebug('search', 'media id: %s', media.id)
        logDebug('search', 'media file name: %s', str(media.filename))
        logDebug('search', 'media primary metadata: %s', str(media.primary_metadata))
        logDebug('search', 'media primary agent: %s', str(media.primary_agent))
        logDebug('search', 'media title: %s', str(media.title))
        logDebug('search', 'media show: %s', str(media.show))
        logDebug('search', 'media name: %s', str(media.name))
        logDebug('search', 'media season: %s', str(media.season))
        logDebug('search', 'media episode: %s', str(media.episode))

        # Compute the GUID based on the media hash.
        try:
            part = media.items[0].parts[0]
            # Get the modification time to use as the year.
            filename = unicodize(part.file)
            log('search', 'part file name: %s', filename)
        except:
            log('search', 'part does not exist')

        results.Append(MetadataSearchResult(id=media.id, name=media.show, year=None, lang=lang, score=100))

    def update(self, metadata, media, lang):

        plexToken = get_universal_plex_token()
        logDebug('PLEX-TOKEN', plexToken)
        if plexToken == '':
            Exception('X-Plex-Token must be set for agent/scanner')
        #test.test('Extended Personal Media - Scan')
        logDebug('update', 'meta data agent object id: %s', id(self))
        logDebug('update', 'metadata: %s', str(metadata))
        logDebug('update', 'media: %s', str(media))
        logDebug('update', 'lang: %s', str(lang))
        # set the metadata title

        logDebug('metadata', 'media.title: %s', media.title)
        #metadata.title = media.title
        self.setStudioAndUpdateShowTitle(metadata, media)
        logDebug('metadata', 'metadata.title: %s', metadata.title)
        # list of series parsers
        series_parsers = [SeriesEpisodeMediaParser()]
        showTitle = metadata.title
        # list of file paths
        showFilePaths = []
        for s in media.seasons:
            logDebug('update', 'season %s', s)
            seasonMetadata = metadata.seasons[s]
            logDebug('update', 'season metadata %s', seasonMetadata)
            #for attr, value in seasonMetadata.items():
            #    logDebug('seasonMetadata','property : %s', attr)
            logDebug('seasonMetadata','title before file loop : %s',seasonMetadata.title)
            logDebug('season', 'media.id: %s', media.id)
            logDebug('season', 'season.id: %s', media.seasons[s].id)

            seasonMetadata.title = series_parsers[0].getSeasonTitle()

            metadata.seasons[s].index = int(s)
            seasonFilePaths = []

            for e in media.seasons[s].episodes:
                logDebug('update', 'episode: %s', e)
                # Make sure metadata exists, and find sidecar media.
                episodeMetadata = metadata.seasons[s].episodes[e]
                logDebug('update', 'episode metadata: %s', episodeMetadata)
                episodeMedia = media.seasons[s].episodes[e].items[0]

                file = episodeMedia.parts[0].file
                logDebug('update', 'episode file path: %s', file)
                absFilePath = os.path.abspath(unicodize(file))
                log('update', 'absolute file path: %s', absFilePath)

                # Iterate over the list of parsers and parse the file path
                for parser in series_parsers:
                    if parser.containsMatch(absFilePath) is True:
                        logDebug('update', 'parser object id: %s', id(parser))
                        log('update', 'parser %s contains match - parsing file path', parser)
                        parser.parse(absFilePath)

                        # set the episode data
                        episodeMetadata.title = parser.getEpisodeTitle()
                        episodeMetadata.summary = parser.getEpisodeSummary()
                        episodeMetadata.originally_available_at = parser.getEpisodeReleaseDate()
                        log('update', 'episode.title: %s', episodeMetadata.title)
                        log('update', 'episode.summary: %s', episodeMetadata.summary)
                        log('update', 'episode.originally_available_at: %s', episodeMetadata.originally_available_at)

                        seasonMetadata.title = parser.getSeasonTitle()
                        seasonMetadata.summary = parser.getSeasonTitle()
                        logDebug('update', 'season.title: %s', seasonMetadata.title)
                        logDebug('update', 'season.summary: %s', seasonMetadata.summary)
                        # add the file path to the season file path list
                        seasonFilePaths = self.addFilePath(seasonFilePaths, absFilePath)
                        # add the file path to the show file path list
                        showFilePaths = self.addFilePath(showFilePaths, absFilePath)

                        break

            logDebug('seasonMetadata','title after file loop : %s',seasonMetadata.title)


            #Get the library section id from the XML metadata
            metadataCheckUrl = 'http://127.0.0.1:32400/library/metadata/'+str(media.seasons[s].id)+'?checkFiles=1&includeExtras=1&X-Plex-Token=' + plexToken
            logDebug('metadataXml','url: %s', metadataCheckUrl)

            metadataXml = urllib2.urlopen(metadataCheckUrl)
            xmldoc = minidom.parse(metadataXml)
            mediaContainer = xmldoc.getElementsByTagName('MediaContainer')[0]
            librarySectionId = mediaContainer.attributes['librarySectionID'].value
            logDebug('metadataXml','librarySectionId: %s', str(librarySectionId))

            #CALL The UI TO HACK THE SEASON TITLE
            data = {'type':'3','id':media.seasons[s].id,'title.value':seasonMetadata.title,'summary.value':'','summary.locked':'0','X-Plex-Token':plexToken}
            dataEncoded = urllib.urlencode(data)
            logDebug('UXHack','dataEncoded: %s', dataEncoded)

            urlStr = 'http://127.0.0.1:32400/library/sections/'+str(librarySectionId)+'/all?' + dataEncoded

            rdata = urllib.urlencode({'dummy':'dummy'}) #I think we need this so that urllib2 will perform a PUT, with not data it just does a GET
            logDebug('UXHack','url: %s', urlStr)
            #logDebug('UXHack','rdata: %s', rdata)
            opener = urllib2.build_opener(urllib2.HTTPHandler)
            request = urllib2.Request(urlStr,data=rdata)
            request.add_header('Content-Type', 'text/html')
            request.get_method = lambda: 'PUT'
            url = opener.open(request)

    def setStudioAndUpdateShowTitle(self,metadata,media):
        '''
        Sets the name of the studio while removing it from the shows title
        '''
        studios = [
            ['lynda com', 'Lynda.com'], # . was sanitized out in scanner
            ['lynda', 'Lynda.com'],
            ['pluralsight', 'Pluralsight.com'],
            ['udemy', 'Udemy.com']
        ]
        for s in studios:
            if s[0] in media.title.lower():
                logDebug('setStudioAndUpdateShowTitle', 'Set studio and remove ' + s[1] + ' from title')
                media.title = re.sub(s[0], '', media.title, flags=re.IGNORECASE)
                media.title = media.title.strip()
                metadata.title = media.title
                metadata.studio = s[1]
                break

    def addFilePath(self, filePaths, newFilePath):
        '''
        Adds the specified file path to the list if it is a sub-directory or a unique file path
        '''
        evalPaths = []

        newDirPath = newFilePath
        if os.path.isfile(newDirPath):
            newDirPath = os.path.dirname(newDirPath)
        # determine if the new path is a sub-path or a new path
        logDebug('addFilePath', 'verifying file path [%s] should be added', newDirPath)
        appendPath = True
        for path in filePaths:
            path = os.path.normpath(os.path.normcase(path))
            logDebug('addFilePath', 'existing path [%s]', path)
            newDirPath = os.path.normpath(os.path.normcase(newDirPath))
            logDebug('addFilePath', 'new path [%s]', newDirPath)
            if newDirPath == path:
                logDebug('addFilePath', 'paths are equivalent - keeping existing path [%s]', path)
                evalPaths.append(path)
                appendPath = False
            elif newDirPath.startswith(path):
                logDebug('addFilePath', 'path [%s] is a subdirectory of [%s] - keeping new path [%s]', newDirPath, path, newDirPath)
                evalPaths.append(newDirPath)
                appendPath = False
            else:
                logDebug('addFilePath', 'keeping existing path [%s]', newDirPath)
                evalPaths.append(path)

        # path is a new path - keep it
        if appendPath:
            logDebug('addFilePath', 'keeping new path [%s]', newDirPath)
            evalPaths.append(newDirPath)

        return evalPaths