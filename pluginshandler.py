import os
import json
import glob
import re
import json
from urlparse import urlparse

plugin_result_data = {}
all_plugins = {}


def load_plugins():
    for fn in glob.glob('plugins' + os.sep + '*.json'):
        f = open(fn)
        data = json.load(f)
        if data["name"] in all_plugins:
            # We do NOT want several plugins w/same name
            raise 'Plugin names must be unique. "' + data["name"] + '" already used'
        else:
            all_plugins[data["name"]] = data
        f.close()


def filter_and_inject_plugins(tab, uri, timing):
    if not uri:
        return
    url = urlparse(uri)
    for name in all_plugins:
        plugin = all_plugins[name]

        if plugin["injectionTime"] != timing:
            continue

        if "site" in plugin:
            if plugin["site"] != '' and plugin["site"] != url[1]:
                continue
        if plugin["dataSource"] == "returnValue":
            # Annoying limitation: tab.execute_script() is a void method
            # We use a stupid hack to get the return value anyway..
            old_title = tab.get_title()
            tab.execute_script('document.title = ' + plugin["javascript"])
            if tab.get_title() != old_title:
                if not name in plugin_result_data:
                    plugin_result_data[name] = tab.get_title()
                    if "dataType" in plugin and plugin["dataType"] == 'json':
                        plugin_result_data[name] = json.loads(plugin_result_data[name])
                tab.set_title(old_title)
        else:
            tab.execute_script(plugin["javascript"])

def run_resource_scan_plugins(resource_code, resource_uri):
    print( "will run resource scan on %d bytes - %s" % (len(resource_code), resource_uri))
    for name in all_plugins:
        plugin = all_plugins[name]
        if plugin["injectionTime"] != 'resource_scan':
            continue
        if not ('regexp' in plugin or 'uri_regexp' in plugin):
            raise 'resource_scan plugins must have a regexp set'
        if 'comment' in plugin:
            comment = '%s (%s)' % (plugin['comment'], resource_uri)
        else:
            comment = 'matched resource (%s)' % resource_uri
        if 'regexp' in plugin:
            rx = re.compile(plugin['regexp'])
            match_against_str = resource_code
        else:
            rx = re.compile(plugin['uri_regexp'])
            match_against_str = resource_uri
            print('will match %s against %s' %(plugin['uri_regexp'], resource_uri))
        if re.search(rx, match_against_str):
            print('initial match!')
            # we have a match. If there is a regexp-not it must also
            # *not* match this regexp to be a true match
            if 'regexp-not' in plugin:
                rx = re.compile(plugin['regexp-not'])
                if re.search(rx, match_against_str):
                    print('2nd match!')
                    # regexp-not is typically used to find indication of a newer-than-problematic
                    # version. Since it matched, this plugin should not flag a problem after all.
                    pass
                else:
                    plugin_result_data[name] = comment
            else:
                plugin_result_data[name] = comment

def handle_console_message(tab, message):
    for name in all_plugins:
        plugin = all_plugins[name]
        if plugin["dataSource"] == "console":
            found = re.search(plugin["dataRegexp"], message)
            if found is not None:
                if not name in plugin_result_data:
                    plugin_result_data[name] = found.group(0)
                    if "dataType" in plugin and plugin["dataType"] == 'json':
                        plugin_result_data[name] = json.loads(plugin_result_data[name])


def get_plugin_results():
    # method returns { "pluginFoo": {"result": "foobar"}, "overall_status": True, "status_determinators": ["pluginFoo"] }
    # The pluginFoo property will only be present if that plugin matched the content.
    # The "overall_status", "status_determinators" properties are optional too
    return_obj = {}
    # Plugin matches can optionally override overall pass/fail
    status_determinators = []
    status = None
    for name in plugin_result_data :
        return_obj[name] = {"result": plugin_result_data[name]}
        # plugins that say "fail" will override those that say "pass" if conflicting
        # this is handed by the "status is not False" condition here:
        if "markMatchesAs" in all_plugins[name] and (status is not False):
            status = all_plugins[name]["markMatchesAs"] == 'pass' # 'True' if status should be set to Pass, 'False' otherwise
            status_determinators.append(name) # keep track of what factors changed the status output
    if status is not None:
        return_obj["overall_status"] = status
        return_obj["status_determinators"] = status_determinators
    return return_obj


def _make_results_obj(bug, targetSite):
    return {"results": [], "bug": bug, "targetSite": targetSite}
