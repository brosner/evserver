import cgi
import mimetypes
import os
import os.path

ROOT='/etc'


file_cache = {}

def application(environ, start_response):
    #form = dict(cgi.parse_qsl(environ.get('QUERY_STRING', '')))
    path = os.path.normpath(os.path.join(ROOT, environ['PATH_INFO'][1:]))

    if path not in file_cache:
        if not path.startswith(ROOT):
            start_response("403 Forbidden", [('Content-type','text/plain')])
            return ('403 Access Denied',)

        if not os.path.isfile(path):
            start_response("404 Not Found", [('Content-type','text/plain')])
            return ('404 Not Found',)

        if not os.access(path, os.R_OK):
            start_response("403 Forbidden", [('Content-type','text/plain')])
            return ('403 Access Denied',)

        fd = open(path, 'rb')
        data = fd.read() # could be changed to yielding if the file is slow
        fd.close()

        mt  = mimetypes.guess_type(path)[0]
        if not mt: mt = 'text/html; charset=utf-8'
        headers = [('Content-type', mt)]
        file_cache[path] = (headers, data)

    headers, data = file_cache[path]
    start_response("200 OK", headers)
    return [data]