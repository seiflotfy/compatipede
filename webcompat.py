#!/usr/bin/env python
import sys
import time
import os
import pika
import subprocess
import urllib2
import json

RWCY_URL = "http://arewecompatibleyet.com/data/masterbugtable.js"
RWCY_PREFIX =\
    """/* This file is generated by preproc/buildlists.py - do not edit */
var masterBugTable ="""

BASEPATH = os.path.abspath(os.path.dirname(os.path.abspath(__file__)))
BROWSER_CMD = BASEPATH + "/xvfb-run.sh -w 0 python " + BASEPATH + "/browser.py %s"

browsers = {}
connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
channel = connection.channel()
channel.queue_declare(queue='mozcompat')
channel.basic_qos(prefetch_count=1)

i = 0

def callback(channel, method, properties, body):
    global i
    i += 1
    print "RECEIVED", i, body
    if not body in browsers:
        browsers[body] = subprocess.Popen(BROWSER_CMD % (body), shell=True)
    while not is_clean():
        time.sleep(3)


def is_clean():
    values = [(key, value) for key, value in browsers.items()]
    for key, value in values:
        if value.poll() is not None:
            del browsers[key]
    return len(browsers) < 5


if len(sys.argv) == 2 and sys.argv[1] == "listen":
    channel.basic_consume(callback, queue='mozcompat', no_ack=True)
    channel.start_consuming()

elif (len(sys.argv) == 2 or len(sys.argv) == 3) and sys.argv[1] == "rwcy":
    response = urllib2.urlopen(RWCY_URL)
    js_str = response.read()[len(RWCY_PREFIX):].strip()
    js = json.loads(js_str)
    # the "masterbugtable" JSON data structure: the hostIndex has one property for each host which has either open or closed bugs in bugzilla
    # In addition, the lists object contains local top lists - for example js["lists"]["no70"]["data"] is an array of (roughly) the top 70 sites in Norway
    # If we want to do a test run of *all* URLs in the system, including local lists, we should go through all these lists and add properties to masterbugtable's hostIndex
    for key in js["lists"].keys():
        for site in js["lists"][key]["data"]:
            if not (site in js["hostIndex"]):
                js["hostIndex"][site] = 1
    start_from = 0
    if len(sys.argv) == 3:
        start_from = int(sys.argv[2])
        print 'rwcy lists from index %i' % start_from
    counter = -1
    print "%i sites to run through, starting from %i" % (len(js["hostIndex"].keys()), start_from)
    for key in js["hostIndex"].keys():
        counter += 1
        if key[-1] == "." or counter < start_from:
            continue
        channel.basic_publish(exchange='', routing_key='mozcompat', body=key)

elif len(sys.argv) == 3:
    if sys.argv[1] == "push":
        channel.basic_publish(exchange='', routing_key='mozcompat',
                              body=sys.argv[2])
    elif sys.argv[1] == "pushall":
        f = open(sys.argv[2], "r")
        sites = f.readlines()
        for site in sites:
            channel.basic_publish(exchange='', routing_key='mozcompat',
                                  body=site)

else:
    print "WRONG BLA BLA"
