from gi.repository import Soup, GLib

import difflib
import json
import subprocess
import sys


class Browser(Soup.Server):
    def __init__(self, uri):
        Soup.Server.__init__(self)
        self._uri = uri
        self.add_handler("/report", self._handle_register, None)
        self.run_async()
        self._results = {}
        subprocess.Popen(["python view.py %s ios %i" % (uri, self.get_port())],
                         shell=True)
        subprocess.Popen(["python view.py %s fos %i" % (uri, self.get_port())],
                         shell=True)

    def _check_source_is_similar(self, tab1, tab2):
        diff = difflib.SequenceMatcher(None, tab1["src"], tab2["src"]).ratio
        return diff >= 0.9

    def _have_equal_redirects(self, tab1, tab2):
        return tab1["redirects"] == tab2["redirects"]

    def _same_styles(self, tab1, tab2):
        return tab1["css"]== tab2["css"]

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

    def _handle_register(self, server, msg, path, query, client, data):
        res = json.loads(msg.request_body.data)
        self._results[res["type"]] = res
        if len(self._results) == 2:
            self._analyze_results()
            mainloop.quit()


if __name__ == "__main__":
    browser = Browser(sys.argv[1])
    mainloop = GLib.MainLoop()
    mainloop.run()
