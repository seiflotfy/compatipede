Compatipede
=========

Compatipede is a website compatability check framework/infrastructure

The General idea is to have several webcompat processes running listening to
a RabbitMQ service, from which they are fed with URLs.

A URL is then opened once using the Firefox UserAgent and another time using the
WebKit UserAgent and checked for compatibility:
- Equal redirects
- CSS style compatability
- Source code compatability
- Other custom tests

Resuls of each run are written to a MongoDB


How to setup
============
Automating Compatibility

For now this only runs on Linux machines.

The requirments for this service to run are:

gir1.2-webkit-3.0
gir1.2-soup-2.4
xvfb
gobject-introspection
python-dbus
dbus-x11
rabbitmq-server


sudo apt-get install gir1.2-webkit-3.0 gir1.2-soup-2.4 xvfb gobject-introspection python-dbus dbus-x11 rabbitmq-server
It is recommended to run it on Ubuntu 13.04 or higher.

In addition, the following Python modules must be available:
tinycss
pika
pymongo

They can all be installed with pip


How to run it:
==============

python webcompat.py listen

sets up a process that will handle a queue of URLs, run tests and store data.
To add URLs to the queue, do this in a separate terminal window:

python webcompat.py push http://example.com
