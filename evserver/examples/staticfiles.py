import cgi
import mimetypes
import os
import os.path

ROOT='/etc'


file_cache = {}

def application(environ, start_response):
    #form = dict(cgi.parse_qsl(environ.get('QUERY_STRING', '')))
    path = environ['PATH_INFO']
    path = os.path.normpath(path)

    if path not in file_cache:
        if not path.startswith(ROOT):
            file_cache[path] = ("403 Forbidden", [('Content-type','text/plain')], '403 Access Denied')
        elif not os.path.isfile(path):
            file_cache[path] = ('404 Not Found', [('Content-type','text/plain')], '404 Not Found')
        elif not os.access(path, os.R_OK):
            file_cache[path] = ("403 Forbidden", [('Content-type','text/plain')], '403 Access Denied')
        else:
            fd = open(path, 'rb')
            data = fd.read() # could be changed to yielding if the file is slow
            fd.close()
    
            mt  = mimetypes.guess_type(path)[0]
            if not mt: mt = 'text/html; charset=utf-8'
            headers = [('Content-type', mt)]
            file_cache[path] = ("200 OK", headers, data)

    code, headers, data = file_cache[path]
    start_response(code, headers)
    return [data]


import socket
def application_comet_spawn(environ, start_response):
    start_response('200 OK', [('Content-type','text/plain')])
    def iterator():
        sd = socket.socket()
        sd.bind( ('127.0.0.1', 0) )
        sd.listen(2)
        try:
            for i in range(10):
                sd.settimeout(0.1)
                try:
                    sd.accept()
                except Exception: pass
                yield 'ping\r\n' # this is not working for spawning
        except GeneratorExit:
            pass
        sd.close()
    return iterator()

def application_comet_awsgi(environ, start_response):
    start_response('200 OK', [('Content-type','text/plain')])
    def iterator():
        sd = socket.socket()
        sd.bind( ('127.0.0.1', 0) )
        sd.listen(2)
        try:
            for i in range(10):
                yield environ['x-wsgiorg.fdevent.readable'](sd, 0.1)
                yield 'ping\r\n'
        except GeneratorExit:
            pass
        sd.close()
    return iterator()



