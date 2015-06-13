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
import pdb
import tldextract
import requests

BUS = dbus.SessionBus(mainloop=DBusGMainLoop())
BROWSER_BUS_NAME = 'org.mozilla.mozcompat.browser%i'
BROWSER_OBJ_PATH = '/org/mozilla/mozcompat'
BROWSER_INTERFACE = 'org.mozilla.mozcompat'
BASEPATH = os.path.abspath(os.path.dirname(os.path.abspath(__file__)))
VIEW_CMD = "python " + BASEPATH + "/view.py %s %s %i"
DB_SERVER = "http://compatentomology.com.paas.allizom.org/data/"

# CSS errors are abundant..
# many of them are relatively harmless. We use a list of properties and a regexp for values to filter out
# the CSS issues we're interested in tracking..
LOG_CSS_PROPS = ["flex", "box-flex", "box", "box-align", "flex-direction", "box-pack", "box-ordinal-group", "appearance"]
LOG_CSS_VALUES = re.compile("(-webkit-gradient|-webkit-linear|-webkit-radial|-webkit-flex|-webkit-box|flexbox|inline-box|inline-flexbox)")

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

    def _normalize_domain(self_, domain):
            tmp = tldextract.extract(domain)
            # we remove "meaningless-ish" prefixes only
            if not tmp.subdomain in ['www', '', 'm']:
                tmp = '%s.%s.%s' % (tmp.subdomain, tmp.domain, tmp.suffix)
            else:
                tmp = '%s.%s' % (tmp.domain, tmp.suffix)
            return tmp

    def _save_data_to_db(self, domain_name, url, testdata_fx, testdata_wk):
        destination_url = '%s%s' % (DB_SERVER, domain_name)
        file_desc = testdata_fx['file_desc']
        file_desc.update(testdata_wk['file_desc'])
        multiple_files = []
        del testdata_fx['file_desc']
        del testdata_wk['file_desc']
        multiple_files = []
        for filename in file_desc:
            multiple_files.append(('screenshot',(os.path.basename(filename),open(file_desc[filename]['full_path'], 'rb'), 'image/png')))
            del file_desc[filename]['full_path'] # don't leak local directory paths onto the internet..
        post_data = {"data": testdata_fx}
        post_data["data"].update(testdata_wk)
        post_data["data"] = json.dumps(post_data["data"])
        post_data['initial_url'] = url
        post_data['file_desc'] = json.dumps(file_desc)
        #print(post_data)
        #print('about to send data to %s' % destination_url)
        req = requests.post(destination_url, files=multiple_files, data=post_data)
        print(req.text)


    def _check_source_is_similar(self, tab1, tab2):
        diff = difflib.SequenceMatcher(None, tab1["src"], tab2["src"])
        ratio = diff.quick_ratio()
        return ratio

    def _have_equal_redirects(self, tab1, tab2):
        return tab1["redirects"] == tab2["redirects"]

    def _find_css_problems(self, sheets):
        issues_json = []
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
                        name = dec.name
                        if '-webkit-' in name:
                                name = name[8:]
                        if name in LOG_CSS_PROPS or re.search(LOG_CSS_VALUES, dec.value.as_css()):
                                issues_json.append({"file": key, "selector": issue["sel"], "property":dec.name, "value":dec.value.as_css()})
                        else:
                                print('ignored %s ' % dec.name)

        except Exception, e:
            print e
            return ["ERROR PARSING CSS"]
        return issues_json
    
    def _process_rule(self, rule, look_for_decl):
            if rule.at_keyword is None or rule.at_keyword == '@page':
                self._process_concrete_rule(rule, look_for_decl)
            elif rule.at_keyword == '@media':
                #print rule.rules
                for subrule in rule.rules:
                    #print 'subrule'
                    #print subrule
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
            if '-webkit-' in value and '-webkit-' in dec.name:
                # *both* property name and property value is -webkit- prefixed
                # this needs special casing so we don't look for "equivalents" like "-webkit-transition:transform" and "transition:-webkit-transform" :-)
                look_for_decl.append({"name":dec.name[8:], "value": self._css_function_name(value)[8:], "dec":dec, "sel":rule.selector.as_css()})
            elif '-webkit-' in value:
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
        # some data massage.. plugin result structure is sort of over-complicated
        fxdata = {fos["ua"]:{fos["engine"]:{"redirects":fos["redirects"], "final_url":fos["final_url"], "css_problems":style_issues["fos"], "js_problems":[], "plugin_results": self._filter_plugin_results(plugin_results["fos"]), "state":results["pass"], "failing_because":results["status_determined_by"]}}}
        wkdata = {ios["ua"]:{ios["engine"]:{"redirects":ios["redirects"], "final_url":ios["final_url"], "css_problems":style_issues["ios"], "js_problems":[], "plugin_results":self._filter_plugin_results(plugin_results["ios"]), "state":results["pass"], "failing_because":results["status_determined_by"]}}}
        # we need file_desc..
        fxdata['file_desc'] = {os.path.basename(fos['screenshot']):{"engine":fos["engine"], "ua":fos["ua"], "full_path":fos["screenshot"]}}
        wkdata['file_desc'] = {os.path.basename(ios['screenshot']):{"engine":ios["engine"], "ua":ios["ua"], "full_path":ios["screenshot"]}}
        self._save_data_to_db(self._normalize_domain(self._uri), self._uri, fxdata, wkdata)
        mainloop.quit()

    def _filter_plugin_results(self, old_plugin_results):
        new_plugin_results = {}
        if "mobile-signs-statistics" in old_plugin_results:
                new_plugin_results.update(old_plugin_results["mobile-signs-statistics"]["result"])
        for property in old_plugin_results:
                if property == "mobile-signs-statistics":
                        continue
                if type(old_plugin_results[property]) == dict and "result" in old_plugin_results[property]:
                        new_plugin_results[property] = old_plugin_results[property]["result"]
                else:
                        new_plugin_results = old_plugin_results[property]
        return new_plugin_results

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
