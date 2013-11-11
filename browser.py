from gi.repository import Soup, GLib
from dbus.mainloop.glib import DBusGMainLoop
from pymongo import Connection
import dbus
import dbus.service
import difflib
import json
import subprocess
import sys
import time
import os


BUS = dbus.SessionBus(mainloop=DBusGMainLoop())
BROWSER_BUS_NAME = 'org.mozilla.mozcompat.browser%i'
BROWSER_OBJ_PATH = '/org/mozilla/mozcompat'
BROWSER_INTERFACE = 'org.mozilla.mozcompat'


class Browser(dbus.service.Object):
    def __init__(self, uri):
        self._uri = uri
        self._results = {}
        self._client = Connection()
        self._db = self._client.mozilla.mozcompat
        self._pid = os.getpid()
        DBusGMainLoop(set_as_default=True)
        bus_name = dbus.service.BusName(BROWSER_BUS_NAME % self._pid, bus=BUS)
        dbus.service.Object.__init__(self, bus_name, BROWSER_OBJ_PATH)
        subprocess.Popen(["python view.py %s ios %i" % (uri, self._pid)],
                         shell=True)
        subprocess.Popen(["python view.py %s fos %i" % (uri, self._pid)],
                         shell=True)

    def _check_source_is_similar(self, tab1, tab2):
        diff = difflib.SequenceMatcher(None, tab1["src"], tab2["src"]).ratio
        return diff >= 0.9

    def _have_equal_redirects(self, tab1, tab2):
        return tab1["redirects"] == tab2["redirects"]

    def _same_styles(self, tab1, tab2):
        return tab1["css"] == tab2["css"]

    def _analyze_results(self):
        print "==== %s ====" % self._uri
        ios = self._results["ios"]
        fos = self._results["fos"]
        check = "PASS" if self._check_source_is_similar(ios, fos) else "FAIL"
        print "Source Compatibility:", check
        check = "PASS" if self._have_equal_redirects(ios, fos) else "FAIL"
        print "Redirects Compatibility:", check
        check = "PASS" if self._same_styles(ios, fos) else "FAIL"
        print "Styles Compatibility:", check
        results = {"timestamp": time.time(),
                   "ios": ios,
                   "fos": fos,
                   "uri": self._uri}
        self._db.insert(results)
        mainloop.quit()

    @dbus.service.method(dbus_interface=BROWSER_INTERFACE, in_signature='s')
    def push_result(self, results):
        res = json.loads(results)
        self._results[res["type"]] = res
        if len(self._results) == 2:
            GLib.idle_add(self._analyze_results)


if __name__ == "__main__":
    browser = Browser(sys.argv[1])
    mainloop = GLib.MainLoop()
    mainloop.run()
