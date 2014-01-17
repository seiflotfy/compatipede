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
import re

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

    def _find_css_problems(self, sheets):
        issues = []
        try:
            parser = tinycss.make_parser()
            for key, value in sheets.iteritems():
                parsed_sheet = parser.parse_stylesheet_bytes(value.encode('utf8'))
                for rule in parsed_sheet.rules:
                    look_for_decl = []
                    # process_rule will go through rule.declarations and fill look_for_decl with a list of potential problems
                    self._process_rule(rule, look_for_decl)
                    # having gone through all declarations in the rule, we now have a list of
                    # "equivalent" rule names or name:value sets - so we go through the declarations
                    # again - and check if the "equivalents" are present
                    look_for_decl[:] = [x for x in look_for_decl if not self._found_in_rule(rule, x)] # replace list by return of list comprehension
                    # the idea is that if all "problems" had equivalents present,
                    # the look_for_decl list will now be empty
                    for issue in look_for_decl:
                        dec = issue["dec"];
                        issues.append(dec.name +
                                      ' used without equivalents for '+issue["sel"]+' in ' +
                                      key + ':' + str(dec.line) +
                                      ':' + str(dec.column) +
                                      ', value: ' +
                                      dec.value.as_css())

        except Exception, e:
            print e
            return ["ERROR PARSING CSS"]
        return issues
    
    def _process_rule(self, rule, look_for_decl):
            if rule.at_keyword is None or rule.at_keyword == '@page':
                self._process_concrete_rule(rule, look_for_decl)
            elif rule.at_keyword == '@media':
                print rule.rules
                for subrule in rule.rules:
                    print 'subrule'
                    print subrule
                    self._process_rule(subrule, look_for_decl)
            else:
                print 'unknown at_keyword: "'+str(rule.at_keyword)+'"'
                
    def _css_function_name(self, css_str):
        return re.split("( |\(|\t)", css_str.strip())[0]

    def _process_concrete_rule(self, rule, look_for_decl):
        name_mappings = { '-webkit-box-flex':'flex', '-webkit-box-align':'align-items', '-webkit-box-pack':'justify-content', '-webkit-box-orient':'flex-direction', '-webkit-box-ordinal-group':'order' }
        value_mappings = { '-webkit-box':'flex', '-webkit-gradient':'linear-gradient' }
        for dec in rule.declarations:
            # We need to check if there is an unprefixed equivalent
            # among the other declarations in this rule..
            value = dec.value.as_css()
            if '-webkit-' in value:
                value = self._css_function_name(value)
                #value = value.strip().split(' ',1)[0] # we want only the keyword, not the rest (for complex values like -webkit-gradient)
                if value in value_mappings:
                    look_for_decl.append({"name":dec.name, "value":value_mappings[value], "dec":dec, "sel":rule.selector.as_css()})
                else:
                    value = value[8:] # just strip out -webkit- and look for the rest
                    look_for_decl.append({"name":dec.name, "value":value, "dec":dec, "sel":rule.selector.as_css()})
            elif dec.name == 'display' and (value in ('box', 'flexbox', '-ms-flexbox')): # special check for flexbox
                look_for_decl.append({"name":dec.name, "value":"flex", "dec":dec, "sel":rule.selector.as_css()})
            elif dec.name in name_mappings:
                look_for_decl.append({"name": name_mappings[dec.name], "dec":dec, "sel":rule.selector.as_css()})
            elif '-webkit-' in dec.name:
                # remove -webkit- prefix
                look_for_decl.append({"name" : dec.name[8:], "dec":dec, "sel":rule.selector.as_css()})
        
    def _found_in_rule(self, rule, look_for):
        if rule.at_keyword is None or rule.at_keyword == '@page':
            for subtest_dec in rule.declarations:
                if 'name' in look_for and 'value' in look_for:
                    if subtest_dec.name == look_for["name"] and self._css_function_name(subtest_dec.value.as_css()) in (look_for["value"], '-moz-'+look_for["value"]):
                        return True # found!
                elif 'value' in look_for:
                     if look_for["value"] in self._css_function_name(subtest_dec.value.as_css()):
                        return True # found!
                elif 'name' in look_for:
                    if subtest_dec.name in (look_for["name"], '-moz-'+look_for["name"]):
                        return True # found!
            return False
        elif rule.at_keyword == '@media':
            found = False
            for subrule in rule.rules:
                found = found or self._found_in_rule(subrule, look_for)
            return found
            
    def _analyze_results(self):
        ios = self._results["ios"]
        fos = self._results["fos"]
        src_diff = self._check_source_is_similar(fos, ios)
        style_issues = {"ios": self._find_css_problems(ios["css"]), "fos": self._find_css_problems(fos["css"]) }
        plugin_results = {"ios": ios["plugin_results"],
                    "fos": fos["plugin_results"]}
        results = {
            "timestamp": time.time(),
            "issues": {
                "style_issues": style_issues,
                "src": src_diff,
                "redirects": {
                    "ios": ios["redirects"],
                    "fos": fos["redirects"]
                },
                "plugin_results": plugin_results
            },
            "uri": self._uri,
            "pass": True,
            "status_determined_by":[]
        }
        # Now we determine an overall pass/fail status for this site, and record why
        if "overall_status" in plugin_results["ios"]:
            results["pass"] =  plugin_results["ios"]["overall_status"]
            results["status_determined_by"] = plugin_results["ios"]["status_determinators"]
        elif "overall_status" in plugin_results["fos"]:
            results["pass"] =  plugin_results["fos"]["overall_status"]
            results["status_determined_by"] = plugin_results["fos"]["status_determinators"]
        if src_diff < 0.9:
            results["pass"] = False
            results["status_determined_by"].append('src_diff')
        if not fos["redirects"] == ios["redirects"]:
            results["pass"] = False
            results["status_determined_by"].append('redirects')
        if len(style_issues["fos"])>0:
            results["pass"] = False
            results["status_determined_by"].append('style_issues')
        if 'wml' in self._results:
            results["pass"] = False;
            results["wml"] = True;
            results["status_determined_by"].append('wml')
            
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
