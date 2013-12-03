from gi.repository import GLib
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
import tinycss


BUS = dbus.SessionBus(mainloop=DBusGMainLoop())
BROWSER_BUS_NAME = 'org.mozilla.mozcompat.browser%i'
BROWSER_OBJ_PATH = '/org/mozilla/mozcompat'
BROWSER_INTERFACE = 'org.mozilla.mozcompat'
BASEPATH = os.path.abspath(os.path.dirname(os.path.abspath(__file__)))
VIEW_CMD = "python " + BASEPATH + "/view.py %s %s %i"


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
        subprocess.Popen([VIEW_CMD % (uri, "ios", self._pid)], shell=True)
        subprocess.Popen([VIEW_CMD % (uri, "fos", self._pid)], shell=True)

    def _check_source_is_similar(self, tab1, tab2):
        diff = difflib.SequenceMatcher(None, tab1["src"], tab2["src"])
        ratio = diff.quick_ratio()
        return ratio

    def _have_equal_redirects(self, tab1, tab2):
        return tab1["redirects"] == tab2["redirects"]

    def _same_styles(self, tab1, tab2):
        try:
            return self._find_css_problems(tab1["css"])
        except:
            return ["ERROR PARSING CSS"]

    def _find_css_problems(self, sheets):
        issues = []
        parser = tinycss.make_parser()
        for key, value in sheets.iteritems():
            parsed_sheet = parser.parse_stylesheet_bytes(unicode(value))
            for rule in parsed_sheet.rules:
                if rule.at_keyword is None:
                    for dec in rule.declarations:
                        # We need to check if there is an unprefixed equivalent
                        # among the other declarations in this rule..
                        if '-webkit-' in dec.name:
                            # remove -webkit- prefix
                            property_name = dec.name[8:]
                            has_equivalents = False
                            for subtest_dec in rule.declarations:
                                if subtest_dec.name in (property_name,
                                                        '-moz-%s' %
                                                        property_name):
                                    has_equivalents = True
                            if has_equivalents:
                                continue
                            issues.append(dec.name +
                                          ' used without equivalents in ' +
                                          key + ':' + str(dec.line) +
                                          ':' + str(dec.column) +
                                          ', value: ' +
                                          dec.value.as_css())
        return issues

    def _analyze_results(self):
        ios = self._results["ios"]
        fos = self._results["fos"]
        src_diff = self._check_source_is_similar(fos, ios)
        style_issues = self._same_styles(fos, ios)
        plugin_results = {"ios": ios["plugin_results"],
                    "fos": fos["plugin_results"]}
        results = {
            "timestamp": time.time(),
            "issues": {
                "style": style_issues,
                "src": src_diff,
                "redirects": {
                    "ios": ios["redirects"],
                    "fos": fos["redirects"]
                },
                "plugin_results": plugin_results
            },
            "uri": self._uri,
            "pass": src_diff >= 0.9 and
            not style_issues and fos["redirects"] == ios["redirects"]
        }

        print "\n=========\n%s\n=========" % self._uri
        print json.dumps(results, sort_keys=True,
                         indent=4, separators=(',', ': '))
        print "========="
        print "PASS:", results["pass"]
        print "=========\n"
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
