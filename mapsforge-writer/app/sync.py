import re
import json
import requests
import os.path
import curses
import hashlib
import time
import datetime
import shp2osm
from bs4 import BeautifulSoup

class SyncerBase:

    APP_PATH = os.path.realpath(os.path.dirname(__file__)) + '/'
    LOCAL_PATH = os.path.expanduser("~/osm-data/")
    CHUNK_SIZE = 4096 * 16

    def _download(self, url, save_path):
        msg = ''
        r = requests.get(url, stream=True)

        with open(save_path, 'wb') as f:
            done = 0
            total = int(r.headers['content-length'])
            print('Download ' + os.path.basename(save_path), end='')

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

class OSMSyncer(SyncerBase):

    BASE_URL = 'http://download.geofabrik.de/asia/'

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
            url = self.BASE_URL + self.__latest_filename()
            save_path = self.LOCAL_PATH + self.__latest_filename()
            self._download(url, save_path)
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

class LandPolygonsSyncer(SyncerBase):

    '''
    A tool to sync land polygons in the world from:
      http://openstreetmapdata.com/data/land-polygons
    This file is too large (about 500MB), don't update it frequently.
    '''

    LAND_POLYGONS_URL = 'http://data.openstreetmapdata.com/land-polygons-split-4326.zip'
    TOLERATIVE_DAYS = 100
    ZIP_WORLD = ''
    SHP_WORLD = ''
    SHP_CLIPPED = ''
    OSM_CLIPPED = ''

    def __init__(self):
        self.ZIP_WORLD = self.LOCAL_PATH + 'land-polygons-split-4326.zip'
        self.SHP_WORLD = self.LOCAL_PATH + 'land-polygons-split-4326/land_polygons.shp'
        self.SHP_CLIPPED = self.LOCAL_PATH + 'land-polygons-taiwan/land_polygons.shp'
        self.OSM_CLIPPED = self.LOCAL_PATH + 'land-polygons-taiwan/land_polygons.osm'

    def __update(self):
        RFC_FORMAT = '%a, %d %b %Y %H:%M:%S GMT'

        local_mtime = 0
        if os.path.isfile(self.SHP_WORLD):
            local_mtime = os.path.getmtime(self.SHP_WORLD)

        r = requests.head(self.LAND_POLYGONS_URL)
        '''
        print(r.headers['etag'])
        print(r.headers['last-modified'])
        print(r.headers['content-length'])
        '''

        dt_remote = datetime.datetime.strptime(r.headers['last-modified'], RFC_FORMAT)
        dt_local = datetime.datetime.fromtimestamp(local_mtime)
        dt_diff = dt_remote - dt_local

        if dt_diff.days > self.TOLERATIVE_DAYS:
            print('The file is old over {} days.'.format(self.TOLERATIVE_DAYS))

            # Download
            self._download(self.LAND_POLYGONS_URL, self.ZIP_WORLD)

            # Unzip
            COMMAND = 'unzip {} -d {}'
            os.system(COMMAND.format(self.ZIP_WORLD, self.LOCAL_PATH))

            # Set mtime for shp file.
            #mtime = time.mktime(dt_remote.timetuple())
            #print(self.SHP_WORLD)
            #os.utime(self.SHP_WORLD, (mtime, mtime))
        else:
            print('The file is new enough.')

        return True

    def __clip(self):
        dir = os.path.dirname(self.SHP_CLIPPED)
        if not os.path.isdir(dir):
            os.mkdir(dir)

        BBOX_CLIPPED = '118.150901 20.627996 123.031181 26.703049'
        COMMAND = 'ogr2ogr -overwrite -progress -skipfailures -clipsrc {} {} {}'
        os.system(COMMAND.format(BBOX_CLIPPED, self.SHP_CLIPPED, self.SHP_WORLD))

    def __convert_to_osm(self):
        shp2osm.run(self.SHP_CLIPPED, output_location=self.OSM_CLIPPED)

    def sync(self):
        if self.__update():
            self.__clip()
            self.__convert_to_osm()

class MapsforgeSyncer(SyncerBase):

    SUB_POLYGONS = ''
    PBF_LATEST = ''
    PBF_MERGED = ''
    MAP_BBOX = '20.627996,118.150901,26.703049,123.031181'
    MAP_MERGED = ''
    MAP_CONF = ''

    def __init__(self):
        self.MAP_CONF = self.APP_PATH + 'taiwan-tag-mapping.xml'
        self.SUB_POLYGONS = self.LOCAL_PATH + 'land-polygons-taiwan/land_polygons.osm'

    def __set_filename(self):
        # Scan the latest PBF.
        items = os.listdir(self.LOCAL_PATH)
        file_pat = re.compile('taiwan-(\d{6}).osm.pbf')
        date_str = ''
        for i in items:
            m = file_pat.match(i)
            if m and m[1] > date_str:
                date_str = m[1]

        self.PBF_LATEST = self.LOCAL_PATH + 'taiwan-{}.osm.pbf'.format(date_str)
        self.PBF_MERGED = self.LOCAL_PATH + 'taiwan-merged-{}.osm.pbf'.format(date_str)
        self.MAP_MERGED = self.LOCAL_PATH + 'taiwan-merged-{}.map'.format(date_str)

    def __merge(self):
        # !!! Don't change the order of parameters, or some errors occur.
        COMMAND = 'osmosis --rb file={} --rx file={} --s --m --wb file={} omitmetadata=true'
        os.system(COMMAND.format(self.PBF_LATEST, self.SUB_POLYGONS, self.PBF_MERGED))

    def __convert_to_map(self):
        COMMAND = 'osmosis --rb file={} --mapfile-writer file={} bbox={} tag-conf-file={} type=hd'
        os.system(COMMAND.format(self.PBF_MERGED, self.MAP_MERGED, self.MAP_BBOX, self.MAP_CONF))

    def sync(self):
        print('Sync OSM data ...')
        oss = OSMSyncer()
        oss.sync()
        self.__set_filename()

        print('Sync land polygons ...')
        lps = LandPolygonsSyncer()
        lps.sync()

        print('Generate map file ...')
        self.__merge()
        self.__convert_to_map()

def main():
    msr = MapsforgeSyncer()
    msr.sync()

if __name__ == '__main__':
    main()
