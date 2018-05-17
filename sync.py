import re
import json
import requests
import os.path
import curses
import hashlib
import shp2osm
from bs4 import BeautifulSoup

class GeoFabrikSync:

    BASE_URL = 'http://download.geofabrik.de/asia/'
    LOCAL_PATH = os.path.expanduser("~/osm-data/")
    CHUNK_SIZE = 4096 * 16

    local_filename = ''
    local_checksum = ''
    latest_filename = ''
    latest_checksum = ''

    def __init__(self):
        if os.path.isfile(self.LOCAL_PATH + 'sync.json'):
            with open(self.LOCAL_PATH + 'sync.json', 'r') as f:
                sync_info = json.load(f)
                self.local_filename = sync_info['filename']
                self.local_checksum = sync_info['checksum']

    def __local_filename(self):
        return self.local_filename

    def __local_checksum(self):
        return self.local_checksum

    def __local_exists(self):
        return os.path.isfile(self.LOCAL_PATH + self.__local_filename())

    def __latest_filename(self):
        if self.latest_filename is '':
            # Load http://download.geofabrik.de/asia/
            r = requests.get(self.BASE_URL)
            html = r.content.decode(r.encoding)

            # Parse file list. Then get the last file of Taiwan.
            p = re.compile('^taiwan-\d{6}\.osm\.pbf$')
            soup = BeautifulSoup(html, 'html.parser')
            all_node = soup.select('tr > td:nth-of-type(2) > a')
            for node in all_node:
                mapfile = node.get_text()
                if p.match(mapfile):
                    self.latest_filename = mapfile
            del soup

        return self.latest_filename

    def __latest_checksum(self):
        if self.latest_checksum is '':
            url = self.BASE_URL + self.__latest_filename() + '.md5'
            r = requests.get(url)
            txt = r.content.decode('ascii') # r.encoding is None, don't decode by that.
            checksum_end = txt.find(' ')
            self.latest_checksum = txt[0:checksum_end]

        return self.latest_checksum

    def __download(self):
        msg = ''
        url = self.BASE_URL + self.__latest_filename()
        r = requests.get(url, stream=True)

        with open(self.LOCAL_PATH + self.__latest_filename(), 'wb') as f:
            done = 0
            total = int(r.headers['content-length'])
            print('Download ' + self.__latest_filename(), end='')

            for chunk in r.iter_content(chunk_size=self.CHUNK_SIZE):
                if chunk:
                    done = done + len(chunk)
                    f.write(chunk)
                    msg = '\b' * len(msg)
                    print(msg, end='')
                    msg = ' ... {}% ({}/{})'.format(int(done*100/total), done, total)
                    print(msg, end='', flush=True)

        msg = '\b' * len(msg) + ' ' * len(msg) + '\b' * len(msg)
        print(msg, end='')
        print(' ... OK!', flush=True)

    def __evaluated_checksum(self):
        checksum = ''

        with open(self.LOCAL_PATH + self.__latest_filename(), 'rb') as f:
            h = hashlib.new('md5')
            chunk = f.read(self.CHUNK_SIZE)
            while chunk:
                h.update(chunk)
                chunk = f.read(self.CHUNK_SIZE)
            checksum = h.hexdigest()

        return checksum

    def __save(self):
        with open(self.LOCAL_PATH + 'sync.json', 'w') as f:
            sync_info = {
                'filename': self.__latest_filename(),
                'checksum': self.__latest_checksum(),
            }
            json.dump(sync_info, f, indent=2, sort_keys=True)

    def sync(self):
        success = True
        is_latest = False
        if self.__local_exists():
            if self.__local_checksum() == self.__latest_checksum():
                if self.__local_checksum() == self.__evaluated_checksum():
                    is_latest = True

        if not is_latest:
            self.__download()
            checksum = self.__evaluated_checksum()
            if checksum == self.__latest_checksum():
                print('Checksum is correct. ({})'.format(checksum))
                self.__save()
            else:
                print('Checksum is not correct !!!')
                print('* Remote checksum: {}'.format(self.__latest_checksum()))
                print('* Evaluated checksum: {}'.format(checksum))
                success = False
        else:
            print('"{}" is the latest map.'.format(self.__local_filename()))

class Coastline:

    LOCAL_PATH = os.path.expanduser("~/osm-data/")

    def __init__(self):
        pass

    def __update(self):
        # TODO: update coastline shape file
        # http://openstreetmapdata.com/data/coastlines
        # The file is too large, don't update it frequently.
        OSM_CLIPPED = self.LOCAL_PATH + 'taiwan-coastline/taiwan-coastline.osm'
        return not os.path.isfile(OSM_CLIPPED)

    def __clip(self):
        SHP_WORLD = self.LOCAL_PATH + 'land-polygons-split-4326/land_polygons.shp'
        SHP_CLIPPED = self.LOCAL_PATH + 'taiwan-coastline/taiwan-coastline.shp'
        BBOX_CLIPPED = '118.150901 20.627996 123.031181 26.703049'
        COMMAND = 'ogr2ogr -overwrite -progress -skipfailures -clipsrc {} {} {}'
        os.system(COMMAND.format(BBOX_CLIPPED, SHP_WORLD, SHP_CLIPPED))

    def __convert_to_osm(self):
        SHP_CLIPPED = self.LOCAL_PATH + 'taiwan-coastline/taiwan-coastline.shp'
        OSM_CLIPPED = self.LOCAL_PATH + 'taiwan-coastline/taiwan-coastline.osm'
        shp2osm.run(SHP_CLIPPED, output_location=OSM_CLIPPED)

    def sync(self):
        if self.__update():
            self.__clip()
            self.__convert_to_osm()

class MapsforgeMap:

    LOCAL_PATH = os.path.expanduser("~/osm-data/")

    def __init__(self):
        pass

    def __merge(self):
        OSM_CLIPPED = self.LOCAL_PATH + 'taiwan-coastline/taiwan-coastline.osm'
        PBF_LATEST = self.LOCAL_PATH + 'taiwan-180516.osm.pbf'
        PBF_MERGED = self.LOCAL_PATH + 'taiwan-merged.osm.pbf'

        # !!! Don't change the order of parameters, or some errors occur.
        COMMAND = 'osmosis --rb file={} --rx file={} --s --m --wb file={} omitmetadata=true'
        os.system(COMMAND.format(PBF_LATEST, OSM_CLIPPED, PBF_MERGED))

    def __convert_to_map(self):
        PBF_MERGED = self.LOCAL_PATH + 'taiwan-merged.osm.pbf'
        MAP_MERGED = self.LOCAL_PATH + 'taiwan-merged.osm.pbf'
        MAP_BBOX = '20.627996,118.150901,26.703049,123.031181'
        MAP_CONF = self.LOCAL_PATH + 'taiwan-tag-mapping.xml'
        COMMAND = 'osmosis --rb file={} --mapfile-writer file={} bbox={} tag-conf-file={}'
        os.system(COMMAND.format(PBF_MERGED, MAP_MERGED, MAP_BBOX, MAP_CONF))

    def create(self):
        self.__merge()
        self.__convert_to_map()

def main():
    gfs = GeoFabrikSync()
    gfs.sync()

    cl = Coastline()
    cl.sync()

    mm = MapsforgeMap()
    mm.create()

if __name__ == '__main__':
    main()
