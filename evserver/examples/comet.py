#!/usr/bin/python
# -*- coding: utf-8 -*-

import transports
import os

import web
import mimetypes
import random
import uuid
from pkg_resources import resource_filename

import os, os.path, logging

log = logging.getLogger(os.path.basename(__file__))


urls = (
    '/static/([^/]+)', 'staticfiles',
    '/', 'staticfiles',
    '/comet', 'comet',
    '/echoread',  'cometread',
    '/echowrite', 'cometwrite',
)

class staticfiles:
    def GET(self, filename='index.html'):
        path = resource_filename(__name__, os.path.join('static',filename))
        #path = os.path.join('static',filename)
        if not os.access(path, os.R_OK):
            web.notfound()
            return
        if filename=='index.html':
            web.header('Content-Type', 'text/html; charset=utf-8')
        else:
            mt  = mimetypes.guess_type(filename)[0]
            if not mt: mt = 'text/html; charset=utf-8'
            web.header('Content-Type', mt )
        f = open(path)
        data = f.read()
        web.output(data)
        f.close()
        return


class comet:
    def GET(self):
        environ = web.ctx.environ # must cache it, becouse it's global!
        i = web.input(transport='iframe', callback='c')
        if i.transport == 'longpoll':
            return comet_longpoll().GET()
        t = transports.get_transport(i.transport, i.callback)
        for k, v in t.get_headers():
            web.header(k, v)

        def iterator():
            fname = '/tmp/fifo'
            try:
                os.mkfifo(fname)
            except OSError:
                pass
            fd = os.open(fname, os.O_RDONLY | os.O_NONBLOCK)
            try:
                yield t.start()
                yield t.write("connected!")
                yield environ['x-wsgiorg.fdevent.readable'](fd, 1.0)
                u = ''.join([ chr(i) for i in range(128)])
                yield t.write(u )
                yield environ['x-wsgiorg.fdevent.readable'](fd, 1.0)
                yield t.write('padding1')
                yield environ['x-wsgiorg.fdevent.readable'](fd, 1.0)
                u = u'На берегу пустынных волн ich sih in grâwen tägelîch als er wil tagen, He wes Leovenaðes sone -- liðe him be Drihten. ἀπὸ τὸ Ἄξιον ἐστί ვეპხის ტყაოსანი შოთა რუსთაველი   Μπορώ να φάω σπασμένα γυαλιά χωρίς να πάθω τίποτα.  ⠊⠀⠉⠁⠝⠀⠑⠁⠞⠀⠛⠇⠁⠎⠎⠀⠁⠝⠙⠀⠊⠞⠀⠙⠕⠑⠎⠝⠞⠀⠓⠥⠗⠞⠀⠍⠑  私はガラスを食べられます。それは私を傷つけません。'
                yield t.write(u.encode( "utf-8" ) )
                yield environ['x-wsgiorg.fdevent.readable'](fd, 1.0)
                size = random.randint(128*1024, 140*1024)
                yield t.write('%i %s' %(size, '<'*size) )
                yield environ['x-wsgiorg.fdevent.readable'](fd, 3.0)
                yield t.write('padding2')
                yield environ['x-wsgiorg.fdevent.readable'](fd, 1.0)
                yield t.write("  \t\r\n\r\n\t \n\r  ")
                yield environ['x-wsgiorg.fdevent.readable'](fd, 1.0)
                yield t.write('padding3')
                yield environ['x-wsgiorg.fdevent.readable'](fd, 1.0)
                yield t.write("event1")
                yield t.write("event2")
                yield environ['x-wsgiorg.fdevent.readable'](fd, 1.0)
                yield t.write('padding4')
                yield environ['x-wsgiorg.fdevent.readable'](fd, 1.0)
                yield t.write('padding4')
                yield environ['x-wsgiorg.fdevent.readable'](fd, 1.0)
                yield t.write('padding5')
            except GeneratorExit:
                pass
            os.close(fd)
        web.ctx.output = iterator()

class comet_longpoll:
    def GET(self):
        environ = web.ctx.environ # must cache it, becouse it's global!
        i = web.input(eid='0')
        eid = int(i.eid)
        t = transports.get_transport('longpoll')
        for k, v in t.get_headers():
            web.header(k, v)

        if eid > 13:
            raise Exception

        def iterator():
            fname = '/tmp/fifo'
            try:
                os.mkfifo(fname)
            except OSError:
                pass
            fd = os.open(fname, os.O_RDONLY | os.O_NONBLOCK)
            try:
                #yield t.start()
                if eid == 0:
                    yield t.write("connected!")
                if eid == 1:
                    yield environ['x-wsgiorg.fdevent.readable'](fd, 1.0)
                    yield t.write(''.join([ chr(i) for i in range(128)]))
                if eid == 2:
                    yield environ['x-wsgiorg.fdevent.readable'](fd, 1.0)
                    yield t.write('padding1')
                if eid == 3:
                    yield environ['x-wsgiorg.fdevent.readable'](fd, 1.0)
                    u = u'На берегу пустынных волн ich sih in grâwen tägelîch als er wil tagen, He wes Leovenaðes sone -- liðe him be Drihten. ἀπὸ τὸ Ἄξιον ἐστί ვეპხის ტყაოსანი შოთა რუსთაველი   Μπορώ να φάω σπασμένα γυαλιά χωρίς να πάθω τίποτα.  ⠊⠀⠉⠁⠝⠀⠑⠁⠞⠀⠛⠇⠁⠎⠎⠀⠁⠝⠙⠀⠊⠞⠀⠙⠕⠑⠎⠝⠞⠀⠓⠥⠗⠞⠀⠍⠑  私はガラスを食べられます。それは私を傷つけません。'
                    yield t.write(u.encode( "utf-8" ) )
                if eid == 4:
                    yield environ['x-wsgiorg.fdevent.readable'](fd, 1.0)
                    size = random.randint(128*1024, 140*1024)
                    yield t.write('%i %s' %(size, '<'*size) )
                if eid == 5:
                    yield environ['x-wsgiorg.fdevent.readable'](fd, 1.0)
                    yield t.write('padding2')
                if eid == 6:
                    yield environ['x-wsgiorg.fdevent.readable'](fd, 1.0)
                    yield t.write("  \t\r\n\r\n\t \n\r  ")
                if eid == 7:
                    yield environ['x-wsgiorg.fdevent.readable'](fd, 1.0)
                    yield t.write('padding3')
                if eid == 8:
                    yield environ['x-wsgiorg.fdevent.readable'](fd, 1.0)
                    yield t.write("event1")
                    yield t.write("event2")
                if eid == 9:
                    yield environ['x-wsgiorg.fdevent.readable'](fd, 1.0)
                    yield t.write('padding4')
                if eid == 10:
                    yield environ['x-wsgiorg.fdevent.readable'](fd, 1.0)
                    yield t.write('padding4')
                if eid == 11:
                    yield environ['x-wsgiorg.fdevent.readable'](fd, 1.0)
                    yield t.write('padding5')
                if eid == 12:
                    pass
                if eid == 13:
                    yield environ['x-wsgiorg.fdevent.readable'](fd)
            except GeneratorExit:
                pass
            os.close(fd)
        web.ctx.output = iterator()



class cometwrite:
    def POST(self):
        i = web.input(uid='x')
        uid = i.uid.replace('.','').replace('/','')
        path = os.path.join('/tmp/','fifo-' + uid)
        if not os.access(path, os.W_OK):
            web.notfound()
            return
        web.header('Content-Type', 'text/plain; charset=utf-8')
        fd = os.open(path, os.O_WRONLY | os.O_NONBLOCK)
        os.write(fd, web.data() )
        os.close(fd)
        web.output('ok')
        return


class cometread:
    def GET(self):
        lweb = web
        environ = web.ctx.environ # must cache it, becouse it's global!
        i = web.input(transport='iframe', callback='c')
        if i.transport == 'longpoll':
            return cometread_longpoll().GET()
        t = transports.get_transport(i.transport, i.callback)
        for k, v in t.get_headers():
            web.header(k, v)

        def iterator():
            uid = str(uuid.uuid4())
            fname = '/tmp/fifo-%s' % (uid,)
            try:
                os.mkfifo(fname)
            except OSError:
                pass
            try:
                yield t.start()
                yield t.write('connected!')
                fd = os.open(fname, os.O_RDONLY | os.O_NONBLOCK)
                os.read(fd, 4096)
                yield environ['x-wsgiorg.fdevent.readable'](fd, 1.0)
                os.close(fd)
                yield t.write(uid)
                while True:
                    fd = os.open(fname, os.O_RDONLY | os.O_NONBLOCK)
                    os.read(fd, 4096)
                    yield environ['x-wsgiorg.fdevent.readable'](fd)
                    yield t.write(os.read(fd, 4096))
                    os.close(fd)
            except GeneratorExit:
                pass
            os.unlink(fname)
        web.ctx.output = iterator()

class cometread_longpoll:
    def GET(self):
        environ = web.ctx.environ # must cache it, becouse it's global!
        i = web.input(eid='0', a='default')
        eid = int(i.eid)
        uid = str(i.a).replace('.','').replace('/','')
        t = transports.get_transport('longpoll')
        for k, v in t.get_headers():
            web.header(k, v)

        def iterator():
            fname = '/tmp/fifo-%s' % (uid,)
            try:
                os.mkfifo(fname)
            except OSError:
                pass
            if eid == 0:
                yield t.write('connected!')
            elif eid == 1:
                yield t.write(uid)
            else:
                try:
                    fd = os.open(fname, os.O_RDONLY | os.O_NONBLOCK)
                    yield environ['x-wsgiorg.fdevent.readable'](fd)
                    yield t.write(os.read(fd, 4096))
                    os.close(fd)
                except GeneratorExit:
                    pass
            os.unlink(fname)
        web.ctx.output = iterator()


# from http://code.google.com/p/modwsgi/wiki/IntegrationWithWebPy
try:
    # webpy 0.3
    application = web.application(urls, globals()).wsgifunc()
except AttributeError:
    # webpy 0.2
    application = web.wsgifunc(web.webpyfunc(urls, globals()))


