#!/usr/bin/env python
import sys
import time
import os
import pika
import subprocess

BASEPATH = os.path.abspath(os.path.dirname(os.path.abspath(__file__)))
BROWSER_CMD = "/usr/bin/python " + BASEPATH + "/browser.py %s"

connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
channel = connection.channel()
channel.queue_declare(queue='mozcompat')
queue = []
browsers = {}


def callback(channel, method, properties, body):
    queue.append(body)


if len(sys.argv) == 2 and sys.argv[1] == "listen":
    while True:
        time.sleep(1)
        values = [(key, value) for key, value in browsers.items()]

        for key, value in values:
            if value.poll() is not None:
                del browsers[key]

        if not queue or len(browsers) > 5:
            continue

        uri = queue.pop(0)
        if uri in browsers:
            continue

        channel.basic_consume(callback, queue='mozcompat', no_ack=True)
        browser = subprocess.Popen(BROWSER_CMD % (uri), shell=True)
        browsers[uri] = browser
        print len(queue), len(browsers)

elif len(sys.argv) == 3 and sys.argv[1] == "push":
    channel.basic_publish(exchange='',
                          routing_key='mozcompat', body=sys.argv[2])

else:
    print "WRONG BLA BLA"
