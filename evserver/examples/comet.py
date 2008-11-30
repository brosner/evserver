#!/usr/bin/python
# -*- coding: utf-8 -*-

import transports
import os

import web
import mimetypes
import random
import uuid

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
        path = os.path.join('static',filename)
        if not os.access(path, os.R_OK):
            web.notfound()
            return
        if filename=='index.html':
            web.header('Content-Type', 'text/html; charset=utf-8')
        else:
            web.header('Content-Type', mimetypes.guess_type(filename))
        f = open(path)
        data = f.read()
        web.output(data)
        f.close()
        return


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

class comet:
    def GET(self):
        lweb = web
        environ = web.ctx.environ # must cache it, becouse it's global!
        i = web.input(transport='iframe', callback='c')
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
                if t.name == 'sse':
                    u = u'abcefs'
                yield t.write(u )
                yield environ['x-wsgiorg.fdevent.readable'](fd, 1.0)
                yield t.write('padding1')
                yield environ['x-wsgiorg.fdevent.readable'](fd, 1.0)
                u = u'На берегу пустынных волн ich sih in grâwen tägelîch als er wil tagen, He wes Leovenaðes sone -- liðe him be Drihten. ἀπὸ τὸ Ἄξιον ἐστί ვეპხის ტყაოსანი შოთა რუსთაველი   Μπορώ να φάω σπασμένα γυαλιά χωρίς να πάθω τίποτα.  ⠊⠀⠉⠁⠝⠀⠑⠁⠞⠀⠛⠇⠁⠎⠎⠀⠁⠝⠙⠀⠊⠞⠀⠙⠕⠑⠎⠝⠞⠀⠓⠥⠗⠞⠀⠍⠑  私はガラスを食べられます。それは私を傷つけません。 '
                if t.name == 'sse':
                    u = u'abc'
                yield t.write(u.encode( "utf-8" ) )
                yield environ['x-wsgiorg.fdevent.readable'](fd, 1.0)
                size = random.randint(128*1024, 140*1024)
                yield t.write('%i %s' %(size, '<'*size) )
                yield environ['x-wsgiorg.fdevent.readable'](fd, 1.0)
                yield t.write('padding2')
            except GeneratorExit:
                pass
            os.close(fd)
        web.ctx.output = iterator()


class cometread:
    def GET(self):
        lweb = web
        environ = web.ctx.environ # must cache it, becouse it's global!
        i = web.input(transport='iframe', callback='c')
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


# from http://code.google.com/p/modwsgi/wiki/IntegrationWithWebPy
try:
    # webpy 0.3
    application = web.application(urls, globals()).wsgifunc()
except AttributeError:
    # webpy 0.2
    application = web.wsgifunc(web.webpyfunc(urls, globals()))


