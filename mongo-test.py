from pymongo import MongoClient
import sys
import time

client = MongoClient('mongodb://109.90.189.171:27017')
db = client.mozilla.mozcompat

def get_documents():
    return [d for d in db.find()]

if len(sys.argv) == 2 and sys.argv[1] == "delete":
    db.remove()

elif len(sys.argv) == 2 and sys.argv[1] == "benchmark":
    t1 = time.time()
    while len(get_documents()) < 10:
        time.sleep(1)
    print time.time() - t1

else:
    print len(get_documents())

