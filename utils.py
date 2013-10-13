import sys
import time

from gi.repository import Gtk

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
