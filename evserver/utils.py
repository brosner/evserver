
import os, os.path, logging
log = logging.getLogger(os.path.basename(__file__))

USERDATA={}
def set_userdata(ud):
    key = id(ud)
    if key in USERDATA:
        log.critical('set_userdata: registered object already exists key=%r ud=%r' % (key, ud))
    USERDATA[key] = ud
    return key

def get_userdata(key, default=None):
    if key not in USERDATA:
        log.critical('get_userdata: object not registered key=%r' % (key,))
        return default
    return USERDATA[key]

def is_in_userdata(key):
    if key not in USERDATA:
        return True
    return False

def get_and_del_userdata(key, default=None):
    data = get_userdata(key, default=default)
    if key in USERDATA:
        del USERDATA[key]
    return data


references = {}
def inc_ref(obj):
    ''' make sure that the object will never be garbage-collected, to avoid mem problems with ctypes'''
    references[id(obj)] = obj
    return obj

def clear_ref():
    global references
    del references
    references = {}


def add_header(hd, nk, nv):
    for i, (k, v) in enumerate(hd):
        if k == nk:
            hd[i] = (nk, nv)
            return hd
    hd.append( (nk, nv) )
    return hd


def libevent_get_headers_dict(node):
    ev = None
    dd = {}
    if node and node.contents and node.contents.tqh_first:
        ev = node.contents.tqh_first.contents
    while ev:
        dd[ev.key[:]] = ev.value[:]
        if not ev.next or not ev.next.tqe_next:
            break
        ev = ev.next.tqe_next.contents
    return dd
