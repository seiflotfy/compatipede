mozcompat
=========

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

To run it:

python webcompat.py listen

sets up a process that will handle a queue of URLs, run tests and store data.
To add URLs to the queue, do this in a separate terminal window:

python webcompat.py push http://example.com
