import os
import shutil
from anorak import notify, regex, model, settings

def processEpisode(dirName, nzbName=None):
    print dirName
    success = False
    for root, dirs, files in os.walk(dirName):
        for file in files:
            x, ext = os.path.splitext(file)
            if ext in [ '.mkv', '.avi', '.mp4']:
                if(processFileAgainstDatabase(dirName, file, ext)):
                    success = True
    if (success):
        shutil.rmtree(dirName)
#        if (settings.getSettings().get("Plex", "enabled")):
#            notify.update_plex()
#        if (settings.getSettings().get("XBMC", "enabled")):
#            notify.update_xbmc()
    return success

            
def processFileAgainstDatabase(dirName, file, ext):
    regexParser = regex.NameParser()
    anime = regexParser.parse(file)
    if not anime == None:
        if anime.series_name and anime.ab_episode_numbers:
            print "Found %s episode %s from %s" % (anime.series_name, anime.ab_episode_numbers[0], anime.release_group)
            anime_from_database = model.get_anime_by_title(anime.series_name)
            if not anime_from_database == None:
                print "Anime matched database, moving"
                model.downloaded_episode(anime_from_database.id, anime.ab_episode_numbers[0])
                if not os.path.exists(anime_from_database.location):
                    os.makedirs(anime_from_database.location)
                    with open(anime_from_database.location + "/tvshow.nfo", 'w') as f:
                       f.write("http://anidb.net/perl-bin/animedb.pl?show=anime&aid={}\n".format(anime_from_database.id))
                episode = model.get_episode(anime_from_database.id, anime.ab_episode_numbers[0])
                new_filename = "{0} - {1} - {2}{3}".format(anime_from_database.title, anime.ab_episode_numbers[0], episode.title, ext)
                shutil.move(os.path.join(dirName,file), os.path.join(anime_from_database.location, new_filename))
                return True
            else:
                print "Anime not in database, bailing"
                return False
