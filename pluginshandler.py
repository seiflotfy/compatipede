import os
import json
import glob
import re
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
                tab.set_title(old_title)
        else:
            tab.execute_script(plugin["javascript"])


def handle_console_message(tab, message):
    for name in all_plugins:
        plugin = all_plugins[name]
        if plugin["dataSource"] == "console":
            found = re.search(plugin["dataRegexp"], message)
            if found is not None:
                if not name in plugin_result_data:
                    plugin_result_data[name] = found.group(0)


def get_plugin_results():
    return plugin_result_data


def _make_results_obj(bug, targetSite):
    return {"results": [], "bug": bug, "targetSite": targetSite}
