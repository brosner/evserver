import StringIO
import sys
import server
libevent = server.libevent
import urllib
import traceback
import ctypes
import utils
import copy
import time

import os, os.path, logging
log = logging.getLogger(os.path.basename(__file__))

class BadRequest: pass


class Request:
    environ = None
    application = None
    response_len = Ellipsis
    standard_out_dict = {
        'code' : 500,
        'reason' : "Internal Error",
        'headers' : [('Content-type','text/plain'),],
        'transmitted': False,
        'chunked': False,
    }
    out_dict = None
    response_closer = None
    inside_wsgi = False

    # set/clear from server.handlers_*
    buf = None
    close_key = None
    event_key = None

    last_fd = None
    suspended = False
    timeout = None
    iterable = None

    # statistics
    content_length = 0
    chunks_number = 0
    context_switches = 1
    created = None
    all_cpu_time = 0.0
    cur_cpu_time = 0.0

    def __init__(self, evreq, vhostdata):
        self.application = vhostdata['application']
        self.timeout = []
        self.out_dict = copy.deepcopy(self.standard_out_dict)
        self.created = server.now
        self.vhostdata = vhostdata
        self.environ = self.request_to_environ(evreq)

        if self.created in self.vhostdata['requests']:
            log.error('conflict in requests_dict %r' % (self.created,))
        self.vhostdata['requests'][self.created] = self
        self.vhostdata['counter'] += 1

    def start_wsgi_application(self):
        ''' returns <out_dict>, chunked, list or iterator, set all needed headers here'''
        writer = StringIO.StringIO()
        def start_response(status, response_headers, exc_info=None):
            self.out_dict['code'], _, self.out_dict['reason'] = status.partition(' ')
            self.out_dict['code'] = int(self.out_dict['code'])
            self.out_dict['headers'] = response_headers

            # set headers for chunked:
            if self.out_dict['chunked']:
                self.set_chunked_headers()
            if exc_info:
                if self.out_dict['transmitted']:
                    raise exc_info[0], exc_info[1], exc_info[2]
            return writer.write

        iterable_len = None
        try:
            iterable = self.application(self.environ, start_response)
            if getattr(iterable, '__len__', None): # execute len() only once, and in the try/except block
                iterable_len = len(iterable)
            if getattr(iterable, 'close', None):
                self.response_closer = iterable.close
        except Exception:
            log.error(str(traceback.format_exc()).strip())
            self.out_dict = copy.deepcopy(self.standard_out_dict) # ignore their headers
            return self.out_dict, True, ['Internal Server Error']

        if iterable is None:
            iterable = []
            iterable_len = 0

        # low probable and without straightforward solution, not worth implementing fully
        if writer.len and iterable:
            log.error("Passed both iterable and writer. Ignoring your return value, sending only writer.")
            iterable = []
            iterable_len = 0

        writer.seek(0)
        if writer.len > 0:
            assert(iterable_len == 0)
            iterable = [writer.read()]
            iterable_len = 1
        writer.close()
        # ufff. we just got rid of the writer. now only iterable matters

        if iterable_len is not None:
            if iterable_len == 0:
                self.out_dict['headers'].append(('Content-Length', str(0)))
                return self.out_dict, False, []
            elif iterable_len == 1:
                # single data
                content, = iterable
                content = str(content)
                self.set_notchunked_headers(len(content))
                return self.out_dict, False, [content]
            elif iterable_len > 1:
                # chunked
                self.out_dict['chunked'] = True
                self.set_chunked_headers()
                return self.out_dict, True, iterable
            else:
                assert(0)

        self.out_dict['chunked'] = True
        self.set_chunked_headers()
        # iterable is NOT list
        self.iterable = iterable
        return self.out_dict, True, self.iterable_wrapper()

    def continue_wsgi_application(self, timeout):
        assert(self.iterable)
        assert(self.suspended)
        assert(not self.event_key)
        self.suspended = False
        self.context_switches += 1
        if self.timeout:
            self.timeout.pop()
            assert(not self.timeout)
        if timeout:
            self.timeout.append(True)

        return self.out_dict, True, self.iterable_wrapper()

    def iterable_wrapper(self):
        assert(not self.suspended)
        assert(self.iterable)
        iterable = self.iterable
        try:
            for content in iterable:
                if self.suspended == True:
                    self.iterable = iterable
                    return
                else:
                    yield content
            self.iterable = None
            return
        except Exception:
            if not self.out_dict['transmitted']:
                self.out_dict = copy.deepcopy(self.standard_out_dict) # ignore their headers
            log.error(str(traceback.format_exc()).strip())
            self.iterable = None
            return

    def is_closed(self):
        if not self.suspended:
            assert(not self.iterable)
            return True
        else:
            return False

    def update_cpu_time(self):
        delta = time.time() - server.now
        self.now_cpu_time = delta
        self.all_cpu_time += delta
        self.vhostdata['cpu_time'] += delta

    def set_chunked_headers(self):
        if self.environ['SERVER_PROTOCOL'] == 'HTTP/1.0':
            utils.add_header(self.out_dict['headers'], 'Connection', 'close')
            utils.add_header(self.out_dict['headers'], 'Transfer-Encoding', '')
        elif self.environ['SERVER_PROTOCOL'] == 'HTTP/1.1':
            utils.add_header(self.out_dict['headers'], 'Transfer-Encoding', 'chunked')

    def set_notchunked_headers(self, l):
        utils.add_header(self.out_dict['headers'], 'Content-Length', str(l))
        if self.environ.get('HTTP_CONNECTION', '').upper() == 'KEEP-ALIVE':
            utils.add_header(self.out_dict['headers'], 'Connection', 'Keep-Alive')

    def readable(self, evreq, fd, timeout=None):
        return self.schedule_fd(evreq, fd, timeout, libevent.EV_READ)

    def writable(self, evreq, fd, timeout=None):
        return self.schedule_fd(evreq, fd, timeout, libevent.EV_WRITE)

    def schedule_fd(self, evreq, fd, timeout, event_flag):
        if getattr(fd, 'fileno', None):
            fd = fd.fileno()
        assert(isinstance(fd, int) or isinstance(fd, long))
        assert(fd >= 0)
        self.last_fd = fd

        byref_timev = None
        if timeout is not None:
            timev = libevent.timeval()
            timev.tv_sec  = int(timeout)
            timev.tv_usec = int((timeout - int(timeout)) * 1000000)
            byref_timev = ctypes.byref(timev)

        event = libevent.event()
        byref_event = ctypes.byref(event)

        # exit points: event (cleared  in handler), connection broken (cleared  in tail)
        self.event_key = utils.set_userdata( (evreq, self, byref_event) )
        libevent.event_set(byref_event, fd, event_flag, server.event_callback_ptr, self.event_key)
        libevent.evtimer_add(byref_event, byref_timev)
        self.suspended = True
        return ''

    def get_url(self):
        environ = self.environ
        url = environ['wsgi.url_scheme']+'://'

        if environ.get('HTTP_HOST'):
            url += environ['HTTP_HOST']
        else:
            url += environ['SERVER_NAME']

            if environ['wsgi.url_scheme'] == 'https':
                if environ['SERVER_PORT'] and environ['SERVER_PORT'] != '443':
                    url += ':' + environ['SERVER_PORT']
            else:
                if environ['SERVER_PORT'] and environ['SERVER_PORT'] != '80':
                    url += ':' + environ['SERVER_PORT']

        url += urllib.quote(environ.get('SCRIPT_NAME',''))
        url += urllib.quote(environ.get('PATH_INFO',''))
        if environ.get('QUERY_STRING'):
            url += '?' + environ['QUERY_STRING']
        return url

    def close(self, con_broken=False):
        # remove all scheduled events, and destroy self.
        assert(not self.buf)
        assert(not self.close_key)
        assert(not self.event_key)

        if self.response_closer:
            try:
                self.response_closer()
            except Exception:
                log.error(str(traceback.format_exc()).strip())

        if con_broken and self.last_fd is not None:
            try:
                os.close(self.last_fd)
            except OSError:
                pass
            self.last_fd = None

        if self.created not in self.vhostdata['requests']:
            log.error('request_dict conflict in removing')
        else:
            del self.vhostdata['requests'][self.created]
        if con_broken:
            self.vhostdata['broken'] += 1
        del self.vhostdata


    def request_to_environ(self, req):
        headers = {}
        if req.contents.type == libevent.EVHTTP_REQ_GET:
            headers['REQUEST_METHOD'] = 'GET'
        elif req.contents.type == libevent.EVHTTP_REQ_POST:
            headers['REQUEST_METHOD'] = 'POST'
        elif req.contents.type == libevent.EVHTTP_REQ_HEAD:
            headers['REQUEST_METHOD'] = 'HEAD'
        else:
            raise BadRequest("Unknown request method")

        # see: http://mail.python.org/pipermail/web-sig/2007-January/002475.html
        headers['PATH_INFO'], _, headers['QUERY_STRING'] = req.contents.uri.partition('?')
        #headers['SCRIPT_NAME'], suffix,  headers['PATH_INFO'] = headers['PATH_INFO'].rpartition('/')
        #headers['SCRIPT_NAME'] += suffix
        headers['SCRIPT_NAME'] = ''

        headers_dict = utils.libevent_get_headers_dict(req.contents.input_headers)
        for k, v in headers_dict.items():
            headers['HTTP_' + k.upper().replace('-','_')] = v

        if 'HTTP_CONTENT_TYPE' in headers:
            headers['CONTENT_TYPE'] = headers['HTTP_CONTENT_TYPE']

        if 'HTTP_CONTENT_LENGTH' in headers:
            headers['CONTENT_LENGTH'] = headers['HTTP_CONTENT_LENGTH']

        host, _, port = headers.get('HTTP_HOST', '').rpartition(':')
        headers['SERVER_NAME'] = host
        headers['SERVER_PORT'] = port
        # major and minor is char, so it's treated as singlechar string.
        # we could cast it to int, but ord is simpler.
        headers['SERVER_PROTOCOL'] = 'HTTP/%i.%i' % (ord(req.contents.major), ord(req.contents.minor))

        # not in standard
        headers['REMOTE_ADDR'] = req.contents.remote_host[:]
        headers['REMOTE_HOST'] = req.contents.remote_host[:]
        headers['REMOTE_PORT'] = req.contents.remote_port

        headers['wsgi.version'] = (1, 0)
        # TODO: support https
        headers['wsgi.url_scheme'] = "http"

        # request body stream
        input_stream = StringIO.StringIO()
        if req.contents.input_buffer and req.contents.input_buffer.contents.off:
            buf = ctypes.create_string_buffer(req.contents.input_buffer.contents.off)
            # Warning, warning. okay, this should work, but it's not the cleanest :)
            ctypes.memmove(buf, req.contents.input_buffer.contents.buffer, req.contents.input_buffer.contents.off)

            input_stream.write(buf.raw)
            input_stream.flush()
            input_stream.seek(0)
            del buf
        '''
        d = []
        for k, v in headers.items():
            if not v:
                d.append(k)
        for k in d:
            del headers[k]
        '''
        headers['wsgi.input'] = input_stream
        headers['wsgi.errors'] = sys.stderr # TODO: this should be a log object
        headers['wsgi.multithread'] = False
        headers['wsgi.multiprocess'] = False
        headers['wsgi.run_once'] = False
        headers['wsgi.now'] = lambda: server.now

        headers['x-wsgiorg.fdevent.readable'] = lambda *args, **kwargs: self.readable(req, *args, **kwargs)
        headers['x-wsgiorg.fdevent.writable'] = lambda *args, **kwargs: self.writable(req, *args, **kwargs)
        headers['x-wsgiorg.fdevent.timeout'] = self.timeout

        return headers

