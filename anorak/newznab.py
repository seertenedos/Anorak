# This plugin is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This plugin is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see http://www.gnu.org/licenses/.

import lib.anidb.requests as requests
import re
import xml.etree.ElementTree as ET

class Download:
    def __init__(self):
        self.url = None
        self.name = None
        self.size = None
        self.external_id = None

def search(group, anime, episode, quality):
    payload = {
	"cat": "5070",
	"apikey": "_API_KEY_",
	"t": "tvsearch",
	"max": 100
    }
    downloads = []
    if quality != 0:
        payload['q'] = "%s %s %s %sp" % (group, anime, episode, quality)
    else:
        payload['q'] = "%s %s %s" % (group, anime, episode)

    r = requests.get("http://_HOST_/api", params=payload)
    print("newznab final search for term %s url %s" % (payload['q'], r.url))
    try:
        xml = ET.fromstring(r.text)
        items = xml.findall("channel/item")
    except Exception:
        print("Error trying to load newznab feed")

    for item in items:
        title = item.find("title").text
        if "- {:>02}".format(episode) not in title:
		continue
        url = item.find("link").text
        ex_id = 0
        curSize = int(item.find("enclosure").attrib["length"])
        print("Found on newznab; name:[%s] size:[%s] id:[%s] url:[%s]" % (title, curSize, ex_id, url))
        d = Download()
        d.url = url
        d.name = title
        d.size = curSize
        d.external_id = ex_id
        downloads.append(d)

    return downloads
