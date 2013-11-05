import cairo
import difflib
import os
import time
import sys
import urlparse
import tinycss

from gi.repository import GLib
from gi.repository import Gtk
from gi.repository import WebKit

from abpy import Filter


adblock = Filter()

if not os.path.exists('screenshots'):
    os.makedirs('screenshots')

IOS_UA = 'Mozilla/5.0 (iPhone; U; CPU iPhone OS 4_3_2 like Mac OS X; en-us) AppleWebKit/533.17.9 (KHTML, like Gecko) Version/5.0.2 Mobile/8H7 Safari/6533.18.5'
FOS_UA = 'Mozilla/5.0 (Mobile; rv:18.0) Gecko/18.0 Firefox/18.0'

SIMPLFY_SCRIPT = """
function removeAttr(attr){
    var xpElms = document.evaluate('//*[@'+attr+']', document.documentElement, null, XPathResult.UNORDERED_NODE_SNAPSHOT_TYPE, null );
    var elm;
    for(var i=0; elm = xpElms.snapshotItem(i); i++){
        elm.removeAttribute(attr)
    }
}
removeAttr('href');
removeAttr('src');
removeAttr('value');
// remove <!-- comment --> and text nodes
var xpElms = document.evaluate('//comment()|//text()', document.documentElement, null, XPathResult.UNORDERED_NODE_SNAPSHOT_TYPE, null );
for(var i=0; elm = xpElms.snapshotItem(i); i++){
    if(!(elm.parentElement.tagName in {'SCRIPT':1,'STYLE':1}))
        elm.parentElement.removeChild(elm)
}
"""


def wait(timeout=15):
    t = time.time()
    if timeout == -1:
        timeout = sys.maxint
    while time.time() - t < timeout:
        Gtk.main_iteration_do(True)


class Tab(WebKit.WebView):

    def __init__(self, uri, user_agent="", tab_type=""):
        WebKit.WebView.__init__(self)
        self.window = window = Gtk.Window()
        window.set_size_request(540, 960)
        scrolled_window = Gtk.ScrolledWindow()
        window.add(scrolled_window)
        #window.add(self)
        scrolled_window.add(self)
        window.show_all()

        self._filter = adblock
        self._uri = uri
        self._user_agent = user_agent
        self._tab_type = tab_type
        self._doms = []
        self._subframes = []
        self._css = {}
        self._settings = self.get_settings()
        self._redirects = []
        self._settings.set_property("enable-private-browsing", True)

        self.connect('frame-created', self._on_frame_created)
        self.connect('resource-request-starting',
                     self._on_resource_request_starting)
        self.connect('resource-load-finished',
                     self._on_resource_load_finished)

        self.set_user_agent(user_agent)
        self.load_uri(uri)
        self.set_title("%s %s" % (tab_type, uri))

    @property
    def document(self):
        return self.get_dom_document()

    @property
    def doms(self):
        return [frame.get_dom_document() for frame in self.frames]

    @property
    def frames(self):
        self._subframes = filter(lambda f: f.get_parent() is not None,
                                 self._subframes)
        return set([self.get_main_frame()] + self._subframes)

    @property
    def ready(self):
        return self.get_load_status() == WebKit.LoadStatus.FINISHED\
            and self.document is not None

    @property
    def source(self):
        return self.document.get_document_element().get_outer_html()

    @property
    def documents(self):
        return self.get_dom_document()

    @property
    def style_sheets(self):
        inline_styles = self.document.get_elements_by_tag_name("style")
        for i in xrange(inline_styles.get_length()) :
            self._css[self._uri+'#inline_style'+str(i)] = inline_styles.item(i).get_text_content()
        return self._css

    @property
    def redirects(self):
        return self._redirects

    def _on_resource_load_finished(self, view, frame, resource):
        if resource.get_mime_type() == "text/css":
            self._css[resource.get_uri()] = resource.get_data().str

    def _on_frame_created(self, view, frame):
        self._subframes.append(frame)

    def _on_resource_request_starting(self, view, frame, resource,
                                      request, response):
        uri = request.get_uri()
        if self._filter.match(uri):
            request.set_uri("about:blank")
            elements = self._find_element_all('[src="%s"]' % uri)
            for element in elements:
                element.get_style().set_property("display", "none", "high")
                #element.get_parent_element().remove_child(element)
        else:
            if response:
                msg = response.get_message()
                if msg and msg.get_property("status-code") / 100 == 3:
                    self._redirects.append(request.get_uri())

    def _get_element_by_id(self, element, dom=None):
        doms = [dom] if dom else self.doms
        elements = []
        for dom in doms:
            res = dom.get_element_by_id(element)
            if res:
                elements.append(res)
        return elements

    def _get_element_by_class_name(self, element, dom=None):
        doms = [dom] if dom else self.doms
        elements = []
        for dom in doms:
            res = dom.get_elements_by_class_name(element)
            elements += [res.item(i) for i in xrange(res.get_length())]
        return elements

    def _get_element_by_name(self, element, dom=None):
        doms = [dom] if dom else self.doms
        elements = []
        for dom in doms:
            res = dom.get_elements_by_name(element)
            elements += [res.item(i) for i in xrange(res.get_length())]
        return elements

    def _get_element_by_tag_name(self, element, dom=None):
        doms = [dom] if dom else self.doms
        elements = []
        for dom in doms:
            res = dom.get_elements_by_tag_name(element)
            elements += [res.item(i) for i in xrange(res.get_length())]
        return elements

    def _query_selector_all(self, element, dom=None):
        doms = [dom] if dom else self.doms
        elements = []
        for dom in doms:
            try:
                res = dom.query_selector_all(element)
                elements += [res.item(i) for i in xrange(res.get_length())]
            except:
                pass
        return elements

    def _find_element_in_dom(self, element, dom):
        elements = []
        for e in self._get_element_by_id(element, dom):
            if not e in elements:
                elements.append(e)
        for e in self._get_element_by_class_name(element, dom):
            if not e in elements:
                elements.append(e)
        for e in self._query_selector_all(element, dom):
            if not e in elements:
                elements.append(e)
        return elements

    def _find_element_all(self, element):
        elements = set()
        for dom in self.doms:
            elements.update(self._find_element_in_dom(element, dom))
        return elements

    def close(self):
        self.window.destroy()

    def set_title(self, title):
        self.window.set_title(title)

    def simplfy(self):
        self.execute_script(SIMPLFY_SCRIPT)

    def set_user_agent(self, user_agent):
        self._settings.set_property('user-agent', user_agent)

    def get_element_inner_html(self, element):
        t = time.time()
        while not self.ready or time.time() - t <= 15:
            wait(1)
        htmls = [e.get_inner_html() for e in self._find_element_all(element)]
        return list((htmls))

    def take_screenshot(self, width=-1, height=-1):
        hostname = urlparse.urlparse(self._uri)[1]
        path = "./screenshots/%s--%s" % (hostname, self._tab_type)
        dview = self.get_dom_document().get_default_view()
        width = dview.get_inner_width() if width == -1 else width
        height = dview.get_outer_height() if height == -1 else height
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
        self.draw(cairo.Context(surf))
        surf.write_to_png(path)


def check_source_is_similar(tab1, tab2):
    tab1.simplfy()
    tab2.simplfy()
    diff = difflib.SequenceMatcher(None, tab1.source, tab2.source).ratio()
    return diff >= 0.9


def take_screenshots(tab1, tab2):
    tab1.take_screenshot()
    tab2.take_screenshot()


def have_equal_redirects(tab1, tab2):
    return tab1.redirects == tab2.redirects


def same_styles(tab1, tab2):
    problems = find_css_problems(tab1.style_sheets)
    return tab1.style_sheets == tab2.style_sheets and len(problems) is 0

def find_css_problems(sheets):
    issues = []
    parser = tinycss.make_parser()
    for sheet in sheets:
        parsed_sheet = parser.parse_stylesheet_bytes(sheets[sheet])
        for rule in parsed_sheet.rules:
            if rule.at_keyword is None:
                for declaration in rule.declarations:
                    if '-webkit-' in declaration.name: #we need to check if there is an unprefixed equivalent among the other declarations in this rule..
                        property_name = declaration.name[8:] # remove -webkit- prefix
                        has_equivalents = False
                        for subtest_declaration in rule.declarations:
                            if subtest_declaration.name is property_name or subtest_declaration.name is '-moz-'+property_name:
                                has_equivalents = True
                        if has_equivalents:
                            continue
                        issues.append( declaration.name+' used without equivalents in '+sheet+':'+str(declaration.line)+':'+str(declaration.column)+', value: '+declaration.value.as_css() )
    if len(issues):
        print "\n".join(issues)
    return issues

def analyze(links):
    while len(links):
        link = links.pop()
        fos_tab = Tab(link, FOS_UA, "fos")
        ios_tab = Tab(link, IOS_UA, "ios")
        t = time.time()

        if not (fos_tab.ready and ios_tab.ready) and time.time() - t < 15:
            wait(5)
        print "==== %s ====" % link
        take_screenshots(ios_tab, fos_tab)
        check = "PASS" if check_source_is_similar(ios_tab, fos_tab) else "FAIL:\n\tSource less than 90% similar"
        print "Source Compatibility:", check
        check = "PASS" if have_equal_redirects(ios_tab, fos_tab) else "FAIL:\n\t Firefox redirected to: "+(', '.join(fos_tab.redirects))+'\n\t iPhone redirected to: '+(', '.join(ios_tab.redirects))
        print "Redirects Compatibility:", check
        check = "PASS" if same_styles(ios_tab, fos_tab) else "FAIL"
        print "Styles Compatibility:", check

        ios_tab.close()
        fos_tab.close()
        time.sleep(1)

if __name__ == "__main__":
    mainloop = GLib.MainLoop()
    root_tab = Tab("www.alexa.com/topsites/countries/BR")
    links = root_tab.get_element_inner_html('small topsites-label')
    analyze(links)
    mainloop.run()
