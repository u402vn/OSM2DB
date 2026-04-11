import sqlite3
from time import sleep
import xml.etree.ElementTree as ET
from datetime import datetime
import requests
import math

# https://api.openstreetmap.org/api/0.6/map?bbox=11.54,48.14,11.543,48.145
# The API is limited to bounding boxes of about 0.5 degree by 0.5 degree and you should avoid using it for larger areas if possible.


def prepareDb(dbFile: str):
    conn = sqlite3.connect(dbFile)
    cursor = conn.cursor()

    print(f'{datetime.now().strftime("%H:%M:%S")} Create tables')

    cursor.execute('''CREATE TABLE IF NOT EXISTS node (
        nodeid INTEGER PRIMARY KEY,
        uid TEXT,
        user TEXT,
        timestamp TEXT,
        lat REAL,
        lon REAL
    )
    ''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS nodetag (
        nodeid INTEGER,
        k TEXT,
        v TEXT,
        FOREIGN KEY (nodeid) REFERENCES node(nodeid),

        UNIQUE (nodeid, k, v)
    )
    ''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS way (
        wayid INTEGER PRIMARY KEY,
        uid TEXT,
        user TEXT,
        timestamp TEXT,

        minLat REAL,
        minLon REAL,
        maxLat REAL,
        maxLon REAL
    )
    ''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS waytag (
        wayid INTEGER,
        k TEXT,
        v TEXT,
        FOREIGN KEY (wayid) REFERENCES way(wayid),

        UNIQUE (wayid, k, v)
    )
    ''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS node_way (
        wayid INTEGER,
        nodeid INTEGER,
        internalOrder INTEGER,
        FOREIGN KEY (wayid) REFERENCES way(wayid),
        FOREIGN KEY (nodeid) REFERENCES node(nodeid),

        UNIQUE (wayid, nodeid)
    )
    ''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS relation (
        relationid INTEGER PRIMARY KEY,
        uid TEXT,
        user TEXT,
        timestamp TEXT,

        minLat REAL,
        minLon REAL,
        maxLat REAL,
        maxLon REAL
    )
    ''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS relationtag (
        relationid INTEGER,
        k TEXT,
        v TEXT,
        FOREIGN KEY (relationid) REFERENCES relation(relationid),

        UNIQUE (relationid, k, v)
    )
    ''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS node_relation (
        nodeid INTEGER,
        relationid INTEGER,
        role TEXT,
        internalOrder INTEGER,
        FOREIGN KEY (relationid) REFERENCES relation(relationid),
        FOREIGN KEY (nodeid) REFERENCES node(nodeid),

        UNIQUE (relationid, nodeid, role)
    )
    ''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS way_relation (
        wayid INTEGER,
        relationid INTEGER,
        role TEXT,
        internalOrder INTEGER,
        FOREIGN KEY (wayid) REFERENCES way(wayid),
        FOREIGN KEY (relationid) REFERENCES relation(relationid),

        UNIQUE (relationid, wayid, role)
    )
    ''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS relation_relation (
        relationid2 INTEGER,
        relationid INTEGER,    
        role TEXT,
        internalOrder INTEGER,
        FOREIGN KEY (relationid) REFERENCES relation(relationid),
        FOREIGN KEY (relationid2) REFERENCES relation(relationid),

        UNIQUE (relationid, relationid2, role)
    )
    ''')



def importXml2Db(xmlFile: str, dbFile: str):

    conn = sqlite3.connect(dbFile)
    cursor = conn.cursor()

    context = ET.iterparse(xmlFile, events=("start", "end"))

    nodeIndexCreated = False
    nodeid = 0
    wayid = 0
    relationid = 0

    nodeCount = 0

    for event, elem in context:
        if event == 'end' and elem.tag in ['node', 'way', 'ralation']:
            nodeid = 0
            wayid = 0
            relationid = 0
            elem.clear()
        if event == 'start':
            if elem.tag == 'node':
                nodeid = int(elem.attrib['id'])
                uid = elem.attrib['uid']
                user = elem.attrib['user']
                timestamp = elem.attrib['timestamp']
                lat = elem.attrib['lat']
                lon = elem.attrib['lon']
                cursor.execute("INSERT OR IGNORE INTO node(nodeid, uid, user, timestamp, lat, lon) VALUES (?, ?, ?, ?, ?, ?)", (nodeid, uid, user, timestamp, lat, lon))
            elif elem.tag == 'way':
                internalOrder = 0
                wayid = int(elem.attrib['id'])
                uid = elem.attrib['uid']
                user = elem.attrib['user']
                timestamp = elem.attrib['timestamp']
                cursor.execute("INSERT OR IGNORE INTO way(wayid, uid, user, timestamp) VALUES (?, ?, ?, ?)", (wayid, uid, user, timestamp))
            elif elem.tag == 'relation':
                internalOrder = 0
                relationid = int(elem.attrib['id'])
                uid = elem.attrib['uid']
                user = elem.attrib['user']
                timestamp = elem.attrib['timestamp']
                cursor.execute("INSERT OR IGNORE INTO relation(relationid, uid, user, timestamp) VALUES (?, ?, ?, ?)", (relationid, uid, user, timestamp))
            elif elem.tag == 'nd':
                internalOrder += 1
                nodeid_ref = int(elem.attrib['ref'])
                cursor.execute("INSERT OR IGNORE INTO node_way(wayid, nodeid, internalOrder) VALUES (?, ?, ?)", (wayid, nodeid_ref, internalOrder))
            elif elem.tag == 'tag':
                k = elem.attrib['k']
                v = elem.attrib['v']
                if nodeid:
                    cursor.execute("INSERT OR IGNORE INTO nodetag(nodeid, k, v) VALUES (?, ?, ?)", (nodeid, k, v))
                elif wayid:
                    cursor.execute("INSERT OR IGNORE INTO waytag(wayid, k, v) VALUES (?, ?, ?)", (wayid, k, v))
                elif relationid:
                    cursor.execute("INSERT OR IGNORE INTO relationtag(relationid, k, v) VALUES (?, ?, ?)", (relationid, k, v))
            elif elem.tag == 'member':
                internalOrder += 1
                memberType = elem.attrib['type']
                id_ref = int(elem.attrib['ref'])
                role = elem.attrib['role']
                if relationid > 0:
                    if memberType == 'node':
                        cursor.execute("INSERT OR IGNORE INTO node_relation(nodeid, relationid, role, internalOrder) VALUES (?, ?, ?, ?)", (id_ref, relationid, role, internalOrder))
                    elif memberType == 'way':
                        cursor.execute("INSERT OR IGNORE INTO way_relation(wayid, relationid, role, internalOrder) VALUES (?, ?, ?, ?)", (id_ref, relationid, role, internalOrder))
                    elif memberType == 'relation':
                        cursor.execute("INSERT OR IGNORE INTO relation_relation(relationid2, relationid, role, internalOrder) VALUES (?, ?, ?, ?)", (id_ref, relationid, role, internalOrder))                    
                    else:
                        print('Type is not defined')
                else:
                    print('Node is not defined')
        elif event == 'end':
            if elem.tag == 'way':
                if nodeIndexCreated:
                    print(f'{datetime.now().strftime("%H:%M:%S")} Create index for node (lat, lon)')
                    cursor.execute('''create index node_lat_lon_idx on node (lat, lon)''')
                    conn.commit()
                    nodeIndexCreated = False

        elem.clear()
        nodeCount += 1
        if nodeCount % 100000 == 0:
            conn.commit()
            print(f'{datetime.now().strftime("%H:%M:%S")} Processeed {nodeCount} elements')

    conn.commit()
    print(f'{datetime.now().strftime("%H:%M:%S")} Processeed {nodeCount} elements')


def postprocessDb(dbFile: str):
    conn = sqlite3.connect(dbFile)
    cursor = conn.cursor()

    print(f'{datetime.now().strftime("%H:%M:%S")} Update way bounding rectangles')
    cursor.execute('''
    UPDATE way AS w
    SET
        minLat = sub.min_lat,
        minLon = sub.min_lon,
        maxLat = sub.max_lat,
        maxLon = sub.max_lon
    FROM (
        SELECT
            nw.wayid,
            MIN(n.lat) AS min_lat,
            MIN(n.lon) AS min_lon,
            MAX(n.lat) AS max_lat,
            MAX(n.lon) AS max_lon
        FROM node n
        INNER JOIN node_way nw ON nw.nodeid = n.nodeid
        GROUP BY nw.wayid
    ) AS sub
    WHERE w.wayid = sub.wayid;
    ''')
    conn.commit()


    print(f'{datetime.now().strftime("%H:%M:%S")} Create index for way (minLat, minLon, maxLat, maxLon)')
    cursor.execute('''create index way_bounds_lat_lon_idx on way (minLat, minLon, maxLat, maxLon)''')
    conn.commit()

    print(f'{datetime.now().strftime("%H:%M:%S")} Update relation bounding rectangles')
    for _ in range(3):
        cursor.execute('''
            UPDATE relation AS r
            SET
                minLat = sub.min_lat,
                minLon = sub.min_lon,
                maxLat = sub.max_lat,
                maxLon = sub.max_lon
            FROM (
	            SELECT
	                coords.relationid,
	                MIN(coords.lat) AS min_lat,
	                MIN(coords.lon) AS min_lon,
	                MAX(coords.lat) AS max_lat,
	                MAX(coords.lon) AS max_lon
	            FROM
	            (
		            select nr.relationid, n.lat, n.lon  from node_relation nr, node n where nr.nodeid = n.nodeid
		            union
		            select wr.relationid, w.minLat, w.minLon from way_relation wr, way w where wr.wayid = w.wayid
		            union
		            select wr.relationid, w.maxLat, w.maxLon from way_relation wr, way w where wr.wayid = w.wayid
		            union
		            select r.relationid, r.minLat, r.minLon from relation_relation rr, relation r where rr.relationid2 = r.relationid
		            union
		            select r.relationid, r.maxLat, r.maxLon from relation_relation rr, relation r where rr.relationid2 = r.relationid
	            ) coords
	            group by coords.relationid
            ) as sub
            WHERE r.relationid = sub.relationid and
            ( (r.minLat is null) or (r.minLat <> sub.min_lat)) and
            ( (r.minLon is null) or (r.minLon <> sub.min_lon)) and
            ( (r.maxLat is null) or (r.maxLat <> sub.max_lat)) and
            ( (r.maxLon is null) or (r.maxLon <> sub.max_lon));
        ''')
    conn.commit()


    print(f'{datetime.now().strftime("%H:%M:%S")} Create index for relation (minLat, minLon, maxLat, maxLon)')
    cursor.execute('''create index relation_bounds_lat_lon_idx on way (minLat, minLon, maxLat, maxLon)''')
    conn.commit()


    print(f'{datetime.now().strftime("%H:%M:%S")} Vacuum')
    cursor.execute('''VACUUM''')
    conn.commit()

    print(f'{datetime.now().strftime("%H:%M:%S")} completed')



def downloadOSMXml(xmlFolder: str, dbFile: str, fromLat: float, fromLon: float, toLat: float, toLon: float):   
    step = 0.10

    fromLat = math.floor(fromLat / step) * step
    fromLon = math.floor(fromLon / step) * step
    toLat = math.ceil(toLat / step) * step
    toLon = math.ceil(toLon / step) * step

    maxStep = 0.3
    minStep = 0.000001
    latStep = step 
    lonStep = step
    currentLat = fromLat
    requestNo = 0

    def __fixLonStep(k: float):
        nonlocal lonStep
        lonStep = lonStep * k
        lonStep = min(max(lonStep, minStep), maxStep)
        if k < 1:
            sleep(1)


    

    while currentLat <= toLat:
        currentLon = fromLon
        while currentLon <= toLon:
            requestNo += 1
            if requestNo % 2 == 0:
                url = f"""https://api.openstreetmap.org/api/0.6/map?bbox={currentLon},{currentLat},{currentLon + lonStep},{currentLat + latStep}"""
            else:
                url = f"""https://www.openstreetmap.org/api/0.6/map?bbox={currentLon},{currentLat},{currentLon + lonStep},{currentLat + latStep}"""
            fileName = f"""{xmlFolder}/osm_{currentLat},{currentLon},{currentLat + latStep},{currentLon + lonStep}.xml"""
            print(f"""{datetime.now().strftime("%H:%M:%S")} - Download #{requestNo} -  {fileName}""")

            try:
                response = requests.get(url, timeout=15)
            except requests.exceptions.RequestException as e:
                print('Ошибка:', e)
                __fixLonStep(0.7)
                continue

            sleep(1)

            if response.status_code == 509:
                retryAfter = response.headers['retry-after']
                retryAfter = int(retryAfter) if retryAfter else 5
                print(f"""{datetime.now().strftime("%H:%M:%S")}  - Pause {retryAfter} seconds""")
                sleep(retryAfter + 1)
            elif response.status_code == 200:
                with open(fileName, 'wb') as file:
                    file.write(response.content)
                    print(f"""{datetime.now().strftime("%H:%M:%S")}  - File Download completed""")
                
                importXml2Db(fileName, dbFile)

                currentLon += lonStep
                __fixLonStep(1.1)
            else:
                print(f"""{datetime.now().strftime("%H:%M:%S")}  - Download canceled""")
                __fixLonStep(0.7)
            
        currentLat += latStep

print('Downloading completed')

    

    



def main():
    dbFile = 'bssr.db'
    xmlFolder = '..\\\OSM_XML'
    prepareDb(dbFile)

    downloadOSMXml(xmlFolder = xmlFolder, dbFile = dbFile, fromLon = 23.160656, toLon = 32.887369, fromLat = 51.213667, toLat = 56.218835)
    #importXml2Db('..\\planet_27.206,53.788_27.888,54.042.osm', 'osm_minks3.db')
    postprocessDb(dbFile)

if __name__ == '__main__':
	main()