import json

import os, os.path, logging
log = logging.getLogger(os.path.basename(__file__))
import sys
import uuid
import re
import urllib

class Transport():
    callback = 'c'
    domain   = None
    headers  = {
        'Cache-Control': 'no-cache',
        'Content-Type': 'text/plain',
    }
    name = None

    def __init__(self, name, callback='c', domain=''):
        self.name = name
        self.callback = ''.join(re.findall('[a-z0-9_]+', callback))
        self.domain = ''.join(re.findall('[a-z0-9._-]+', domain))

    def start(self):
        return ''

    def write(self, data):
        return '''%s\r\n''' % (data)

    def get_headers(self):
        return self.headers.items()

class BasicTransport(Transport):
    def __init__(self, *args, **kwargs):
        self.headers['Content-Type'] = 'text/html'
        Transport.__init__(self, *args, **kwargs)

    def start(self):
        return '''<html><head></head><body onload="setTimeout('window.location.reload()', 2000);">\n'''

    def write(self, data):
        return '<b>%s</b><br />\r\n' % (data,)

class IFrameTransport(Transport):

    def __init__(self, *args, **kwargs):
        self.headers['Content-Type'] = 'text/html; charset=utf-8'
        self.headers['Refresh'] = '3000'
        Transport.__init__(self, *args, **kwargs)

    initial_data = '''
        <html>
        <head>
            <meta http-equiv="Content-Type" content="text/html; charset=UTF-8"/>
            <script type="text/javascript" charset="utf-8">
            function extract_xss_domain(old_domain) {
                domain_pieces = old_domain.split('.');
                if (domain_pieces.length === 4) {
                    var is_ip = !isNaN(Number(domain_pieces.join('')));
                    if (is_ip) {
                       return old_domain;
                    }
                }
                return domain_pieces.slice(-2).join('.');
            }

            //document.domain = extract_xss_domain(document.domain);
          </script>
        </head>
        <body onLoad="try{parent.%(callback)s_reconnect();}catch(e){alert(e.message);}">
    ''' + ('<span></span>' * 80)

    def start(self):
        return self.initial_data % {'callback':self.callback, 'domain':self.domain }

    def write(self, data):
        return '''<script>try{parent.%s(%s);}catch(e){alert(e.message);}</script>\r\n''' % \
                        (self.callback, json.write(data))


class SSETransport(Transport):

    def __init__(self, *args, **kwargs):
        self.headers['Reconnection-Time'] = '2000'
        self.headers['Refresh'] = '3000'
        self.headers['Content-Type'] = 'application/x-dom-event-stream; charset=UTF-8'
        self.headers['Cache-Control'] =  'no-cache, must-revalidate'
        Transport.__init__(self, *args, **kwargs)

    def start(self):
        return 'Event: sessionid\ndata: %s\n\n' % (str(uuid.uuid4()).replace('-','')[:22],)

    def write(self, data):
        return  'Event: payload\n' +    \
                'data: %s' % urllib.quote(data) + \
                '\n\n'

class XHRStreamTransport(Transport):
    boundary = '\r\n|O|\r\n'

    def __init__(self, *args, **kwargs):
        self.headers['Content-Type'] = 'application/x-orbited-event-stream; charset=utf-8'

        Transport.__init__(self, *args, **kwargs)

    initial_data = '.'*256 + '\r\n\r\n'

    def start(self):
        return self.initial_data

    def write(self, data):
        return data + self.boundary

        # if transport == 'xhr':
        ## application/xml based on: http://lists.macosforge.org/pipermail/webkit-dev/2007-June/002041.html
        ## must be some message here, at least one byte long...

def format_block(s):
    ''' Formatter for block strings to be sent as HTTP.
        (so they can be written cleanly in python classes)

        Dedent every line of a string by the indent of the first line,
        replace newlines with '\r\n', and remove any trailing whitespace.
    '''
    s = s.lstrip('\r\n').rstrip() # leading empty lines, trailing whitespace
    lines = s.expandtabs(4).splitlines()

    # find w, the smallest indent of a line with content
    w = min([len(line) - len(line.lstrip()) for line in lines])

    return '\r\n'.join([line[w:] for line in lines])


class XHRMultipartTransport(Transport):
    boundary = 'orbited--'
    multipart_content_type = 'application/json'

    def __init__(self, *args, **kwargs):
        self.headers['Content-Type'] = 'multipart/x-mixed-replace;boundary="%s"' % boundary
        Transport.__init__(self, *args, **kwargs)

    def encode(self, data):
        boundary = "\r\n--%s\r\n" % self.boundary
        headers = (formatBlock('''
            Content-type: %s
            Content-length: %s
        ''') + '\r\n\r\n') % (self.multipart_content_type, len(data))
        return ''.join([headers, data, boundary])









transports = {
    'basic':                BasicTransport,
    'iframe':               IFrameTransport,
    'htmlfile':             IFrameTransport,
    'server_sent_events':   SSETransport,
    'sse':                  SSETransport,
    'xhr_multipart':        XHRMultipartTransport,
    'xhr_stream':           XHRStreamTransport,
    'xhr':                  XHRStreamTransport,
}

def get_transport(name, *args, **kwargs):
    if name not in transports:
        return None

    return transports[name](name, *args, **kwargs)



