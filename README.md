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

It is recommended to run it on Ubuntu 13.04 or higher.
sudo apt-get install gir1.2-webkit-3.0 gir1.2-soup-2.4 xvfb gobject-introspection python-dbus dbus-x11


To run it:

python browser.py <url>


e.g:

python browser.py google.com
