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


'''
Test methodogy:

$ ./evserver/evserver --exec "import examples.staticfiles; application = examples.staticfiles.application_comet" -nvvv -p
$ PYTHONPATH=. spawn --port=8080 --processes=1 --threads=0 evserver.examples.staticfiles.application_comet 2>/dev/null > a

$ cat plot
set xlabel 'drift time in ms'
set ylabel 'number of events'

plot '/tmp/a' using 1:2  with lines

$ grep connec a|head -n 1; grep connect a|tail -n 1;grep -e "^[0-9-]*$" a|sort|uniq -c|sort -k 2 -n|sed "s/^[^0-9]*\([0-9]*\) \([0-9-]*\)$/\2\t\1/" > /tmp/a; gnuplot -persist plot

'''


payload = '.\r\n'
timeout = 0.500  # 500ms
howmany = int(10.0 / timeout)


from eventlet import api
import socket
import time
import sys
l = sys.stdout
c = 0
starttime = 0

def application_comet(environ, start_response):
    evserver = True if 'x-wsgiorg.fdevent.readable' in environ else False

    start_response('200 OK', [('Content-type','text/plain')])
    def iterator():
        global c, starttime
        if not starttime:
            starttime = time.time()
        tt0 = time.time()
        deltas = 0.0
        c += 1
        l.write("connections %r %.3fs\n" % (c, time.time() - starttime))
        sd = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) # any udp socket
        try:
            for i in range(howmany):
                t0 = time.time()
                if evserver:
                    yield environ['x-wsgiorg.fdevent.readable'](sd, timeout)
                else: # spawning
                    try:
                        api.trampoline(sd, read=True, timeout=timeout)
                    except api.TimeoutError:
                        pass
                    #time.sleep(timeout) #api.sleep(timeout)
                delta = (time.time()-t0-timeout)
                deltas += delta
                l.write('%i\n' % (delta* 1000.0))
                yield payload
        except GeneratorExit:
            pass
        sd.close()
        tt1 = time.time()
        tt = tt1-tt0
        l.write('total time %.3f, deltas=%.3f drift=%.3f\n' % (tt, deltas, tt-(howmany*timeout)-deltas))
        c -= 1
    return iterator()


