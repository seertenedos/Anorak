#!/usr/bin/python

import os
import sys
import datetime
import time
import pytz
import ConfigParser
import lib.web as web
import lib.anidb as anidb
from optparse import OptionParser
from anorak.downloader import *
from anorak import metadata, model, process, search

urls = (
	'/', 'Index',
	'/anime/(\d+)', 'Anime',
	'/settings', 'Settings',
	'/search', 'Search',
	'/add/(\d+)', 'Add',
	'/remove/(\d+)', 'Remove',
	'/refresh/(\d+)', 'Refresh',
	'/process', 'Process',
	'/shutdown', 'Shutdown'
)

searchForm = web.form.Form(
        web.form.Textbox('query',
        web.form.notnull,
        size=15,
        height="100%",
        description="",
        id="search"),
        web.form.Button('Search', 
        id="search_button"),
    )

def setupDatabase():
    import os
    if not os.path.exists('anorak.db'):
        import sqlite3
        conn = sqlite3.connect('anorak.db')
        c = conn.cursor()
        schema = open('schema.sql', 'r').read()
        c.executescript(schema)
        conn.commit()
        c.close()

def getConfig():
    try:
        file = open("anorak.cfg", "r")
        settings.readfp(file)
        file.close()
    except IOError, e:
        print "Creating configuration file"
        setupConfig()

def setupConfig():
    # Setup the default settings and create the sections
    if not settings.has_section("Anorak"):
        settings.add_section("Anorak")
        settings.add_section("SABnzbd")
        settings.add_section("Plex")
        settings.set("Anorak", "port", 26463)
        settings.set("Anorak", "searchFrequency", 30)
        settings.set("Anorak", "titleLang", "en")
        settings.set("Anorak", "timezone", "US/Pacific")
        settings.set("SABnzbd", "url", "localhost:8080")
        settings.set("SABnzbd", "key", "")
        settings.set("SABnzbd", "category", "")
        settings.set("SABnzbd", "username", "")
        settings.set("SABnzbd", "password", "")
        settings.set("Plex", "url", "localhost:32400")
        settings.set("Plex", "enabled", False)
        file = open("anorak.cfg","w")
        settings.write(file)
        file.close()
        # Weirdness, settings must be reloaded from file or else ConfigParser throws a hissy fit
        file = open("anorak.cfg", "r")
        settings.readfp(file)
        file.close()

### Templates
t_globals = {
	'datestr': web.datestr,
    'str': str,
    'len': len,
    'datetime': datetime,
    'searchForm': searchForm,
    'createTitleListing': metadata.createTitleListing
}

#web.config.debug = False

render = web.template.render('templates', base='base', globals=t_globals)

anidb.set_client('anorakk', 1)

settings = ConfigParser.ConfigParser()

getConfig()
setupDatabase()

class Index:
    
    def GET(self):
        """ List anime """
        animes = model.get_animes()
        return render.index(animes, getAiring)

class Anime:

    def episodeTryForm(self,episode=None):
        return web.form.Form(
            web.form.Hidden('episode', value=episode),
            web.form.Hidden('form', value="tryEpisode"),
        )

    def episodeSkipForm(self,episode=None):
        return web.form.Form(
            web.form.Hidden('episode', value=episode),
            web.form.Hidden('form', value="skipEpisode"),
        )

    def editorForm(self,anime):
        return web.form.Form(
            web.form.Textbox('location', web.form.notnull,
            size=30,
            value=anime.location,
            description="Location:"),

            web.form.Textbox('alternativeTitle',
            size=30,
            value=anime.alternativeTitle,
            description="Name override (for searching only):"),

            web.form.Textbox('releaseGroup',
            size=30,
            value=anime.subber,
            description="Release Group:"),

            web.form.Textbox('airTime', web.form.notnull,
            size=30,
            description="Enter the JST airtime of show (HH:MM)",
            value=anime.airTime),

            web.form.Dropdown('quality',
            [('0', 'None'), ('720', '720p'), ('480', '480p'), ('1080', '1080p')],
            value=str(anime.quality),
            description="Force a quality. Leave 'None' if your release group doesn't have more than one quality."),

            web.form.Hidden('form', value="editor"),

            web.form.Button('Update'),
        )
    
    def GET(self, id):
        """ List anime episodes """
        anime = model.get_anime(id)
        episodes = model.get_episodes(id)
        editorForm = self.editorForm(anime)
        return render.anime(anime, episodes, self.episodeTryForm, self.episodeSkipForm, 
                            editorForm, search.computeAirdate)
        
    def POST(self, id):
        i = web.input()

        # assuming that the name of the hidden field is "form"
        if i.form == "editor":
            return self.POST_editor(id)
        elif i.form == "skipEpisode":
            return self.POST_skip(id)
        else:
            return self.POST_snatch(id)

    def POST_snatch(self, id):
        anime = model.get_anime(id)
        downloader = Downloader()
        downloader.anime = anime
        downloader.episode = web.input().episode
        if (downloader.download()):
            model.snatched_episode(id, web.input().episode)
            return "Snatched episode %s successfully" % web.input().episode
        else:
            return "Couldn't snatch episode %s" % web.input().episode

    def POST_skip(self, id):
        anime = model.get_anime(id)
        ep = model.get_episode(id, web.input().episode)
        if ep.wanted == 1:
           model.skipped_episode(id, web.input().episode)
           return "Skipped episode %s successfully" % web.input().episode
        else:
           model.wanted_episode(id, web.input().episode)
           return "Added episode %s successfully" % web.input().episode

    def POST_editor(self, id):
        anime = model.get_anime(id)
        episodes = model.get_episodes(id)
        editorForm = self.editorForm(anime)
        if not editorForm.validates():
            return render.anime(anime,episodes, self.episodeTryForm,
                                self.episodeSkipForm, editorForm, search.computeAirdate)
        model.update_anime(id, web.input().alternativeTitle, web.input().releaseGroup, 
                           web.input().location, web.input().airTime, int(web.input().quality))
        return render.anime(anime,episodes, self.episodeTryForm,
                            self.episodeSkipForm, editorForm, search.computeAirdate)
        
class Add:
    
    form = web.form.Form(
        web.form.Dropdown('quality',
        [(0, 'None'), (720, '720p'), (480, '480p'), (1080, '1080p')],
        description="Force a quality. Leave 'None' if your release group doesn't have more than one quality."),

        web.form.Textbox('subber', web.form.notnull,
        size=30,
        description="Enter the release group"),

        web.form.Textbox('location', web.form.notnull,
        size=30,
        description="Enter the file path for storing episodes"),

        web.form.Textbox('airTime', web.form.notnull,
        size=30,
        description="Enter the JST Air Time of show (HH:MM)",
        value="00:00"),

        web.form.Button('Complete Add'),
    )
    
    anime = None
    
    def GET(self, id):
        """ Show the groups doing releases (UDP only feature, we're using TCP) """
        form = self.form()
        anime = anidb.query(anidb.QUERY_ANIME, int(id))
        return render.add(form, anime)
    
    def POST(self, id):
        form = self.form()
        anime = anidb.query(anidb.QUERY_ANIME, int(id))
        if not form.validates():
            return render.add(form, anime)
        metadata.newAnime(anime, form.d.subber, form.d.location, form.d.airTime, form.d.quality)
        raise web.seeother('/anime/%s' % int(id))
        
class Remove:
    
    def GET(self, id):
        model.remove_anime(id)
        raise web.seeother('/')

class Refresh:

    def GET(self, id):
        metadata.refreshForAnime(int(id))
        raise web.seeother('/anime/%s' % id)
        
class Process:
    
    def GET(self):
        query = web.input()
        try:
            nzbName = query.nzbName
        except:
            nzbName = None
        if (process.processEpisode(query.dir, nzbName)):
            return "Successfully processed episode."
        return "Episode failed to process."

class Search:
    
    def GET(self):
        """ Search for Anime and add it """
        return render.search(None)
        
    def POST(self):
        if not searchForm.validates():
            return render.search(None)
        results = anidb.search(searchForm.d.query)
        return render.search(results)
        
class Settings:
    
    sabnzbdForm = web.form.Form(
        web.form.Textbox('url', web.form.notnull,
        size=30,
        value=settings.get("SABnzbd", "url"),
        description="SABnzbd URL:"),

        web.form.Textbox('username',
        size=30,
        value=settings.get("SABnzbd", "username"),
        description="SABnzbd Username:"),

        web.form.Password('password',
        size=30,
        value=settings.get("SABnzbd", "password"),
        description="SABnzbd Password:"),

        web.form.Textbox('key', web.form.notnull,
        size=30,
        value=settings.get("SABnzbd", "key"),
        description="SABnzbd API key:"),

        web.form.Textbox('category',
        size=30,
        value=settings.get("SABnzbd", "category"),
        description="SABnzbd Category:"),

        web.form.Hidden('form', value="sabnzbd"),

        web.form.Button('Update'),
    )

    settingsForm = web.form.Form(
        web.form.Textbox('port', web.form.notnull,
        size=30,
        value=str(settings.get("Anorak", "port")),
        description="Port Number:"),

        web.form.Textbox('searchFrequency', web.form.notnull,
        size=30,
        value=str(settings.get("Anorak", "searchFrequency")),
        description="Search Frequency:"),

        web.form.Dropdown('titleLang',
        ["ar", "bg", "cs", "da", "de", "en", "es", "fa", "fi", "fr", "he", "hu", "id", 
         "it", "ja", "ko", "lt", "nl", "no", "pl", "pt", "ro", "ru", "sv", "ta", "ur"],
        value=str(settings.get("Anorak", "titleLang")),
        description="Official Title Language:"),

        web.form.Dropdown('timezone',
        pytz.common_timezones,
        value=str(settings.get("Anorak", "timezone")),
        description="Local Timezone:"),

        web.form.Hidden('form', value="settings"),

        web.form.Button('Update'),
    )

    plexForm = web.form.Form(
        web.form.Checkbox('enabled',
        checked=settings.getboolean("Plex", "enabled"),
        description="Plex Enabled:"),

        web.form.Textbox('url', web.form.notnull,
        size=30,
        value=str(settings.get("Plex", "url")),
        description="Plex URL:"),

        web.form.Hidden('form', value="plex"),

        web.form.Button('Update'),
    )
    
    def GET(self):
        return render.settings(self.settingsForm, self.sabnzbdForm, self.plexForm)
    
    def POST(self):
        i = web.input()

        # determine which form to process based on the hidden value "form"
        if i.form == "settings":
            return self.POST_settings()
        if i.form == "sabnzbd":
            return self.POST_sabnzbd()
        if i.form == "plex":
            return self.POST_plex()

    def POST_settings(self):
        if not self.settingsForm.validates():
            return render.settings(self.settingsForm, self.sabnzbdForm, self.plexForm)
        settings.set("Anorak", "searchFrequency", self.settingsForm.d.searchFrequency)
        settings.set("Anorak", "port", self.settingsForm.d.port)
        settings.set("Anorak", "timezone", self.settingsForm.d.timezone)
        settings.set("Anorak", "titleLang", self.settingsForm.d.titleLang)
        file = open("anorak.cfg","w")
        settings.write(file)
        file.close()
        return render.settings(self.settingsForm, self.sabnzbdForm, self.plexForm)

    def POST_sabnzbd(self):
        if not self.sabnzbdForm.validates():
            return render.settings(self.settingsForm, self.sabnzbdForm, self.plexForm)
        settings.set("SABnzbd", "url", self.sabnzbdForm.d.url)
        settings.set("SABnzbd", "username", self.sabnzbdForm.d.username)
        settings.set("SABnzbd", "password", self.sabnzbdForm.d.password)
        settings.set("SABnzbd", "key", self.sabnzbdForm.d.key)
        settings.set("SABnzbd", "category", self.sabnzbdForm.d.category)
        file = open("anorak.cfg","w")
        settings.write(file)
        file.close()
        return render.settings(self.settingsForm, self.sabnzbdForm, self.plexForm)

    def POST_plex(self):
        if not self.plexForm.validates():
            return render.settings(self.settingsForm, self.sabnzbdForm, self.plexForm)
        settings.set("Plex", "url", self.plexForm.d.url)
        settings.set("Plex", "enabled", self.plexForm.d.enabled)
        file = open("anorak.cfg","w")
        settings.write(file)
        file.close()
        return render.settings(self.settingsForm, self.sabnzbdForm, self.plexForm)

class Shutdown(object):
    def GET(self):
        os._exit(0)

class NullDevice:
    def write(self, s):
        pass

def getAiring(anime):
    for episode in model.get_episodes(anime.id):
        if episode.wanted == 1:
            return search.computeAirdate(episode.airdate, anime.airTime).strftime("%Y-%m-%d %H:%M")
    return "N/A"

def daemonize():
    """Become a daemon"""
    if os.fork():
        os._exit(0)

    # decouple from parent environment
    os.setsid()
    os.umask(0)

    sys.stdin.close()
    sys.stdout = NullDevice()
    sys.stderr = NullDevice()


app = web.application(urls, globals())
search = search.SearchThread()

if __name__ == '__main__':
    port = settings.get("Anorak", "port")
    optionParser = OptionParser()
    optionParser.add_option('-d', '--daemon', action = "store_true",
                 dest = 'daemon', help = "Run the server as a daemon")
    options, args = optionParser.parse_args()
    if options.daemon:
        if not sys.platform == 'win32':
            daemonize()
        else:
            print "Daemon mode not supported under Windows, starting normally."
    sys.argv[1:] = [port]
    search.start()
    app.run()
