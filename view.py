import cairo
import os
import json
import re
import sys
import time
import dbus

from gi.repository import GLib
from gi.repository import Gtk
from gi.repository import WebKit
from dbus.mainloop.glib import DBusGMainLoop

from abpy import Filter
from utils import IOS_UA, FOS_UA
from utils import SIMPLFY_SCRIPT, IOS_SPOOF_SCRIPT, FOS_SPOOF_SCRIPT, is_host_and_path_same
from pluginshandler import load_plugins, filter_and_inject_plugins, handle_console_message, get_plugin_results


BUS = dbus.SessionBus(mainloop=DBusGMainLoop())
BROWSER_BUS_NAME = 'org.mozilla.mozcompat.browser%i'
BROWSER_OBJ_PATH = '/org/mozilla/mozcompat'
BROWSER_INTERFACE = 'org.mozilla.mozcompat'

adblock = Filter()

if not os.path.exists('screenshots'):
    os.makedirs('screenshots')


class Tab(WebKit.WebView):

    def __init__(self, uri, tab_type="ios", port=None):
        WebKit.WebView.__init__(self)
        self.window = window = Gtk.Window()
        window.set_size_request(540, 960)
        scrolled_window = Gtk.ScrolledWindow()
        window.add(scrolled_window)
        scrolled_window.add(self)
        window.show_all()
        self._start_time = time.time()
        self._port = port

        self._filter = adblock
        if not re.match('^https?://', uri):
            uri = "http://%s" % uri
        self._uri = uri
        self._user_agent = FOS_UA if tab_type == "fos" else IOS_UA

        self._tab_type = tab_type
        self._resources = set([])
        self._css = {}
        self._settings = self.get_settings()
        self._redirects = []
        self._js_injected_frames = {}
        self._settings.set_property("enable-private-browsing", True)

        self.connect('resource-request-starting',
                     self._on_resource_request_starting)
        self.connect('resource-load-finished',
                     self._on_resource_load_finished)
        self.connect('resource-response-received',
                     self._on_resource_response_received)
        self.connect('resource-load-failed',
                     self._on_resource_load_failed)
        self.connect('resource-content-length-received',
                     self._on_resource_content_length_received)
        self.connect('onload_event',
                     self._on_onload_event)
        self.connect('console_message',
                     self._on_console_message)


        self.set_user_agent(self._user_agent)
        self.load_uri(uri)
        self.set_title("%s %s" % (tab_type, uri))
        GLib.timeout_add(1000, self._tear_down)

    @property
    def document(self):
        return self.get_dom_document()

    @property
    def source(self):
        return self.document.get_document_element().get_outer_html()

    @property
    def style_sheets(self):
        return self._css

    @property
    def redirects(self):
        return self._redirects

    @property
    def ready(self):
        return self.get_load_status() == WebKit.LoadStatus.FINISHED\
            and len(self._resources) == 0

    @property
    def frames(self):
        self._subframes = filter(lambda f: f.get_parent() is not None,
                                 self._subframes)
        return set([self.get_main_frame()] + self._subframes)

    def send_results(self):
        results = {"type": self._tab_type,
                   "css": self.style_sheets,
                   "redirects": self._redirects,
                   "src": self.source,
                   "plugin_results": get_plugin_results()}
        json_body = json.dumps(results)
        obj = BUS.get_object(BROWSER_BUS_NAME % self._port, BROWSER_OBJ_PATH)
        iface = dbus.Interface(obj, BROWSER_INTERFACE)
        iface.push_result(json_body)

    def _tear_down(self):
        if self.ready or time.time() - self._start_time >= 15:
            #self.take_screenshot()
            self.simplfy()
            if self._port:
                self.send_results()
            mainloop.quit()
            return False
        return True

    def _on_resource_response_received(self, view, frame, resource, response):
        self._resources.add(resource.get_uri())

    def _on_resource_content_length_received(self, view, frame, resource, length):
        try:
            # Unfortunately resource.get_mime_type() still returns None at this point - we can dig deeper though..
            # possibly frame.get_data_source().get_main_resource().get_mime_type() might be an alternative?
            content_type = frame.get_data_source().get_main_resource().get_mime_type()
        except:
            content_type = ''
        if content_type =='text/html': # and frame.get_parent() == None:
            #Wow, here comes The Content!
            # Well, at least this is a text/html response sent to the main window.
            # Could be a sub-resource with wrong content-type set

            # at this point, a HTML page is being delivered but its JS has not run yet
            # This seems like a good place to do spoofing and injectionTime:start plugins
            if not frame in self._js_injected_frames:
                if self._tab_type is 'fos':
                    self.execute_script(FOS_SPOOF_SCRIPT)
                else:
                    self.execute_script(IOS_SPOOF_SCRIPT)
                # This is also a good place to inject JS for any 'start' plug-ins
                filter_and_inject_plugins(self, frame.get_uri(), 'start')
                self._js_injected_frames[frame] = True

    def _on_resource_load_failed(self, view, frame, resource, error):
        self._resources.remove(resource.get_uri())

    def _on_resource_load_finished(self, view, frame, resource):
        if resource.get_mime_type() == "text/css":
            self._css[resource.get_uri()] = resource.get_data().str
        self._resources.remove(resource.get_uri())


    def _on_resource_request_starting(self, view, frame, resource,
                                      request, response):
        self._resources.add(resource.get_uri())
        if self._filter.match(request.get_uri()):
            request.set_uri("about:blank")
        elif response:
            msg = response.get_message()
            temp_uri_list = self._get_ignore_redirects_list()
            if msg and msg.get_property("status-code") / 100 == 3 and\
                    any([response.get_uri() in u
                         for u in self._redirects + temp_uri_list]):
                self._redirects.append(request.get_uri())

    def _on_onload_event(self, view, frame):
        # Check if the URL in the main frame is the one we initially requested
        current_uri = self.get_main_frame().get_uri()
        if not is_host_and_path_same(current_uri,  self._uri):
            # If this redirect isn't already recorded, there is something fishy in the state of our redirect tracking..
            # JS navigation, probably..
            temp_uri_list = self._get_ignore_redirects_list()
            if current_uri not in temp_uri_list and current_uri not in self._redirects:
                self._redirects.append(current_uri)
        # Let's see if we have any plugins that want to run at onload time..
        filter_and_inject_plugins(self, frame.get_uri(), 'load')

    def _on_console_message(self, view, message, line, id):
        handle_console_message(self, message)

    def _get_ignore_redirects_list(self):
        temp_uri_list = [self._uri]
        if self._uri.endswith("/"):
            temp_uri_list.append(self._uri[:-1])
        else:
            temp_uri_list.append("%s/" % self._uri)
        return temp_uri_list

    def close(self):
        self.window.destroy()

    def set_title(self, title):
        self.window.set_title(title)

    def simplfy(self):
        self.execute_script(SIMPLFY_SCRIPT)

    def set_user_agent(self, user_agent):
        self._settings.set_property('user-agent', user_agent)

    def take_screenshot(self, width=-1, height=-1):
        path = "./screenshots/%s--%s" % (self._uri.split("//")[1],
                                         self._tab_type)
        print path
        dview = self.get_dom_document().get_default_view()
        width = dview.get_inner_width() if width == -1 else width
        height = dview.get_outer_height() if height == -1 else height
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
        self.draw(cairo.Context(surf))
        surf.write_to_png(path)

if __name__ == "__main__":
    uri = sys.argv[1]
    ua = sys.argv[2]
    port = int(sys.argv[3]) if len(sys.argv[3]) > 3 else None
    mainloop = GLib.MainLoop()
    load_plugins()
    root_view = Tab(uri, ua, port)
    mainloop.run()
