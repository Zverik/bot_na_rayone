import sqlite3
import csv
import sys
from raybot import config


def run_export():
    if len(sys.argv) < 3:
        print('Usage: {} export_tags <file.csv>'.format(sys.argv[0]))
        sys.exit(1)

    conn = sqlite3.connect(config.DATABASE)
    cur = conn.execute(
        "select id, name, tag, '', description, comment, address "
        "from poi where tag is null or tag not in ('building', 'entrance')")
    with open(sys.argv[2], 'w') as f:
        w = csv.writer(f)
        w.writerow('id name tag type description comment address'.split())
        for row in cur:
            row = list(row)
            row[3] = config.TAGS.get(row[2], [''])[0]
            w.writerow(row)
    conn.close()


def run_import():
    if len(sys.argv) < 3:
        print('Usage: {} import_tags <file.csv> [<new_tags.yml>]'.format(sys.argv[0]))
        sys.exit(1)

    conn = sqlite3.connect(config.DATABASE)
    cur = conn.execute("select id, tag from poi")
    poi_tags = {row[0]: row[1] for row in cur}
    new_tags = {}
    with open(sys.argv[2], 'r') as f:
        for row in csv.DictReader(f):
            if not row['id'].isdecimal():
                continue
            poi_id = int(row['id'])
            tag = row['tag'].strip()
            if not tag:
                continue
            if poi_id not in poi_tags:
                continue
            if tag != poi_tags[poi_id]:
                conn.execute("update poi set tag = ? where id = ?", (tag, poi_id))
            if tag not in config.TAGS:
                if tag not in new_tags or not new_tags[tag]:
                    new_tags[tag] = row['type'].strip()

    if len(sys.argv) > 3:
        outfile = open(sys.argv[3], 'w')
    else:
        outfile = sys.stdout
    print('tags:', file=outfile)
    for k, v in new_tags.items():
        print(f'  {k}: [{v}]', file=outfile)
    if len(sys.argv) > 3:
        outfile.close()

    conn.commit()
    conn.close()
