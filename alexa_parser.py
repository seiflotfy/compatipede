import csv
import requests
import zipfile
import os
import pika
from os.path import expanduser


BASEPATH = os.path.abspath(os.path.dirname(os.path.abspath(__file__)))
ALEXA_FILE = BASEPATH + "/alexa.zip"


connection = pika.BlockingConnection(pika.ConnectionParameters('109.90.189.171'))
channel = connection.channel()
channel.queue_declare(queue='mozcompat')


r = requests.get('http://s3.amazonaws.com/alexa-static/top-1m.csv.zip')
with open(ALEXA_FILE, 'wb') as f:
    f.write(r.content)

with open(ALEXA_FILE, 'rb') as f:
    z = zipfile.ZipFile(f)
    for name in z.namelist():
        outpath = BASEPATH
        z.extract(name, outpath)

with open(BASEPATH + '/top-1m.csv', 'rb') as f:
    for site in [line.split(',')[1] for line in f.read().split('\n')[:10]]:
        site = "http://%s" % site
        print site
        channel.basic_publish(exchange='', routing_key='mozcompat', body=site)

