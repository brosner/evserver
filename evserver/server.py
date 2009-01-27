#!/usr/bin/python
# -*- coding: utf-8 -*-

import ctypes
import sys
import os
import signal
import utils
from pkg_resources import resource_filename

v = ctypes.libeventbinary_version.replace('-','_').replace('.','_')

oldcwd = os.getcwd()
os.chdir( os.path.join(resource_filename(__name__, ''), '..')  )

modulename = 'evserver.ctypes_event_%s' % v
try:
    def my_import(name):
        mod = __import__(name)
        components = name.split('.')
        for comp in components[1:]:
            mod = getattr(mod, comp)
        return mod
    libevent = my_import(modulename)
except (AttributeError, ImportError), e:
    raise Exception("**** libevent ctypes bindings %r are broken - probably wrong version of binary ****\n" % (modulename,)+
                    "                currently, libevent.so is loaded from %r \n" %(ctypes.libeventbinary,)+
                    "                try to specify different 'libevent.so' using '--libevent </path/to/libevent.so> \n"+
                    "                if that fails, try to create new ctypes bindings for libevent using 'make bindings'\n"+
                    "                Tried to load the bindings from directory: %r\nError message: %r\n" % (os.getcwd(), str(e)) )
os.chdir( oldcwd )


import traceback
import time
from functools import wraps
import StringIO
import datetime
import request
import gc
import os, os.path, logging

log = logging.getLogger(os.path.basename(__file__))



HTTP_CALLBACK  = ctypes.CFUNCTYPE(None, ctypes.POINTER(libevent.evhttp_request), ctypes.c_void_p)
EVENT_CALLBACK = ctypes.CFUNCTYPE(None, ctypes.c_int, ctypes.c_short, ctypes.c_void_p)
CLOSE_CALLBACK = ctypes.CFUNCTYPE(None, ctypes.POINTER(libevent.evhttp_connection), ctypes.c_void_p)

req_type = ctypes.POINTER(libevent.evhttp_request)
buf_type = ctypes.POINTER(libevent.evbuffer)

# cached timer, updated for every event
now = time.time()
event_counter = 0

REQUEST_NEW=1
REQUEST_CONTINUE=2
REQUEST_CLOSE=3

def new_request_callback(evreq, userdata_key):
    global now, event_counter
    now = time.time()
    event_counter += 1
    # force type conversion. I have no idea why, but it's needed.
    evreq = ctypes.cast(evreq, req_type)

    vhostdata = utils.get_userdata(userdata_key)
    req = request.Request(evreq, vhostdata)

    return root_handler(evreq, req, REQUEST_NEW)

def event_callback(fd, evt, userdata_key):
    global now, event_counter
    now = time.time()
    event_counter += 1
    evreq, req, byref_event = utils.get_and_del_userdata(userdata_key)
    req.event_key = None

    return root_handler(evreq, req, REQUEST_CONTINUE, evt)

def void_callback(conn, userdata_key):
    return 0

def freeevcon_callback(fd, evt, userdata_key):
    evcon, byref_event, byref_timev = utils.get_and_del_userdata(userdata_key)
    del byref_event
    del byref_timev
    libevent.evhttp_connection_free(evcon)
    return 0


def close_callback(conn, userdata_key):
    global now, event_counter
    now = time.time()
    event_counter += 1

    evreq, req = utils.get_and_del_userdata(userdata_key)
    req.close_key = None

    return root_handler(evreq, req, REQUEST_CLOSE)


# never ever gc this
new_request_callback_ptr = HTTP_CALLBACK(new_request_callback)
event_callback_ptr = EVENT_CALLBACK(event_callback)
close_callback_ptr = CLOSE_CALLBACK(close_callback)
void_callback_ptr = CLOSE_CALLBACK(void_callback)
freeevcon_callback_ptr = EVENT_CALLBACK(freeevcon_callback)

def root_handler(evreq, req, event_type, evt=None):
    content_length = 0
    chunks_number = 0
    response_dict = {'code':0, 'reason':''}
    request_closed  = False

    # dispatcher, new reqest or resume one?
    # head.
    if event_type == REQUEST_NEW:
        response_dict, chunked, iterable = req.start_wsgi_application()
        if not chunked:
            data = ''
            for data in iterable:
                break
            data = str(data)

            buf = libevent.evbuffer_new()
            for key, value in response_dict['headers']:
                libevent.evhttp_add_header(evreq.contents.output_headers, str(key), str(value))
            libevent.evbuffer_add(buf, data, len(data))
            libevent.evhttp_send_reply(evreq, response_dict['code'], response_dict['reason'], buf)
            libevent.evbuffer_free(buf)
            response_dict['transmitted'] = True
            req.content_length += len(data)
            req.chunks_number += 1

            content_length = len(data)
            chunks_number = 1
            del buf

    if event_type == REQUEST_CONTINUE:
        response_dict, chunked, iterable = req.continue_wsgi_application(True if evt and (evt & libevent.EV_TIMEOUT) else False)
        assert(chunked)

    # body.
    if event_type in [REQUEST_NEW, REQUEST_CONTINUE] and chunked:
        assert(getattr(iterable, '__iter__', None))
        iterator = getattr(iterable, '__iter__')()
        try:
            first_chunk = str(iterator.next())
        except StopIteration:
            first_chunk = None

        if not req.buf: # must be after first evaluation of iterable
            req.buf = libevent.evbuffer_new()
            for key, value in response_dict['headers']:
                if req.environ['SERVER_PROTOCOL'] == 'HTTP/1.1' and key == "Transfer-Encoding": # libevent automagically adds it's own transer-encoding header. fuck you libevent
                    continue
                libevent.evhttp_add_header(evreq.contents.output_headers, str(key), str(value))
            libevent.evhttp_send_reply_start(evreq, response_dict['code'], response_dict['reason'])
            response_dict['transmitted'] = True

            # exit points: connection broken (cleared in handler), end of request (cleared in tail)
            req.close_key = utils.set_userdata( (evreq, req) )
            libevent.evhttp_connection_set_closecb(evreq.contents.evcon, close_callback_ptr, req.close_key)

        if first_chunk:
            libevent.evbuffer_add(req.buf, first_chunk, len(first_chunk))
            libevent.evhttp_send_reply_chunk(evreq, req.buf)

            req.content_length += len(first_chunk)
            req.chunks_number += 1
            content_length += len(first_chunk)
            chunks_number  += 1

        # now transfer all the chunks
        for data_chunk in iterator:
            data_chunk = str(data_chunk)

            if not data_chunk: # can't really send empty data -> it means conn close
                continue

            # TODO: bug here, packets aren't on the wire just after evhttp_send_reply_chunk, and they should
            # TODO: this is not nice, but this is how http works in libevent, sorry.
            libevent.evbuffer_add(req.buf, data_chunk, len(data_chunk))
            libevent.evhttp_send_reply_chunk(evreq, req.buf)

            req.content_length += len(data_chunk)
            req.chunks_number += 1
            content_length += len(data_chunk)
            chunks_number  += 1

    # before closing
    req.update_cpu_time()
    # tail.
    if event_type == REQUEST_CLOSE or (chunked and req.is_closed()):
        if evreq.contents.evcon and evreq.contents.evcon.contents and evreq.contents.evcon.contents.closecb:
            libevent.evhttp_connection_set_closecb(evreq.contents.evcon, void_callback_ptr, None)

        if req.close_key:
            assert(event_type != REQUEST_CLOSE)
            utils.get_and_del_userdata(req.close_key)
            del req.close_key

        if event_type != REQUEST_CLOSE:
            libevent.evhttp_send_reply_end(evreq)
        else:
            assert(event_type == REQUEST_CLOSE)
            if evreq.contents.evcon:
                # BUG in libevent, memleak if conn is broken
                event = libevent.event()
                timeval = libevent.timeval()
                timeval.tv_sec  = 0
                timeval.tv_usec = 1
                byref_event = ctypes.byref(event)
                byref_timev = ctypes.byref(timeval)
                libevent.evtimer_set(byref_event, freeevcon_callback_ptr, utils.set_userdata( (evreq.contents.evcon, byref_event, byref_timev) )  )
                libevent.evtimer_add(byref_event, byref_timev)

        if req.buf:
            libevent.evbuffer_free(req.buf)
            del req.buf

        # free event, if scheduled:
        if req.event_key:
            assert(event_type == REQUEST_CLOSE)
            _, _,  byref_event = utils.get_and_del_userdata( req.event_key )
            libevent.event_del(byref_event)
            del byref_event
            del req.event_key

        req.close(con_broken=True if event_type == REQUEST_CLOSE else False)
        request_closed = True

    if event_type == REQUEST_NEW and not chunked:# cleanup single
        req.close(con_broken=False)
        # How the fuck to force closing connection here..., after sendig data
        #libevent.evhttp_request_free(evreq)
        #libevent.evhttp_connection_free(evreq.contents.evcon)

    log.debug('''%(host)s "%(method)s %(url)s %(http)s" %(status_code)i %(content_length)s/%(chunks_number)s (%(time).1fms) - %(event)s''' % {
        'method': req.environ['REQUEST_METHOD'],
        'url': req.get_url(),
        'http': req.environ['SERVER_PROTOCOL'],
        'status_code': response_dict['code'],
        'content_length': content_length,
        'chunks_number': chunks_number,
        'host': '%s:%i' % (req.environ['REMOTE_HOST'], req.environ['REMOTE_PORT']),
        'time': (req.now_cpu_time) * 1000, # in miliseconds
        'event': 'close' if request_closed else 'single' if not chunked else 'chunk',
        })

    return 1




def signal_handler(req, nr, user_data):
    log.info("signal")
    libevent.event_loopexit(None)
    return 1

def hup_handler(req, nr, user_data):
    i = gc.collect()
    log.info("SIGHUP caught! %i objects collected, %i frozen, %i objects, %i events" % (i, len(utils.USERDATA), len(gc.get_objects()), event_counter ))
    return 1


def libevent_set_signal_handler(signo, handler):
    event = libevent.event()
    event_ref = utils.inc_ref(ctypes.byref(event))
    libevent.signal_set(event_ref, signo, utils.inc_ref(EVENT_CALLBACK(handler)), None)
    libevent.signal_add(event_ref, None)

vhosts = []
base = None

def main_init():
    global base
    base = libevent.event_init()
    # handle CTRL+C
    libevent_set_signal_handler(signal.SIGINT, signal_handler)
    libevent_set_signal_handler(signal.SIGHUP, hup_handler)

def main_loop( bindings ):
    global base

    https = []
    for (host, port, application) in bindings:
        log.info("Binding to %s:%i" % (host,port))
        http = libevent.evhttp_start(host, port)
        if not http:
            log.critical("Bad host/port (host=%r port=%r) or address already in use" % (host,port))
            log.critical("QUITTING!")
            os.abort()
        libevent.evhttp_set_timeout(http,60) # minute, that's just for the http stuff
        vhostdata = {
            'application':application,
            'counter':0,
            'host':host,
            'port':port,
            'requests': {},
            'broken': 0,
            'cpu_time':0.0,
        }
        libevent.evhttp_set_gencb(http, new_request_callback_ptr, utils.set_userdata(vhostdata));
        vhosts.append(vhostdata)
        https.append(http)


    # The main libevent loop... Forever.
    libevent.event_dispatch()

    # end loop - id est Ctrl+c
    log.info("Quitting")
    for http in https:
        libevent.evhttp_free(http)
    libevent.event_base_free(base)

    gc.collect()
    utils.clear_ref()


