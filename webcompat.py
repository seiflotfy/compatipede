#!/usr/bin/env python
import sys
import time
import os
import pika
import subprocess

BASEPATH = os.path.abspath(os.path.dirname(os.path.abspath(__file__)))
BROWSER_CMD = "/usr/bin/python " + BASEPATH + "/browser.py %s"

browsers = {}
connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
channel = connection.channel()
channel.queue_declare(queue='mozcompat')
channel.basic_qos(prefetch_count=1)


def callback(channel, method, properties, body):
    if not body in browsers:
        browsers[body] = subprocess.Popen(BROWSER_CMD % (body), shell=True)
    while not is_clean():
        time.sleep(1)


def is_clean():
    values = [(key, value) for key, value in browsers.items()]
    for key, value in values:
        if value.poll() is not None:
            del browsers[key]
    return len(browsers) < 5


if len(sys.argv) == 2 and sys.argv[1] == "listen":
    channel.basic_consume(callback, queue='mozcompat', no_ack=True)
    channel.start_consuming()

elif len(sys.argv) == 3 and sys.argv[1] == "push":
    channel.basic_publish(exchange='',
                          routing_key='mozcompat', body=sys.argv[2])

else:
    print "WRONG BLA BLA"