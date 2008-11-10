from orbited.util import formatBlock
import django_evserver.json as json

class Transport():
    callback = None
    domain   = None
    initial_data = ''
    headers  = {}
    
    def __init__(self, callback=None, domain=None):
        self.callback = callback
        self.domain   = domain
    
    def get_initial_data(self):
        return self.initial_data
    
    def encode(self, data):
        return data

class BasicTransport(Transport):
    name = 'basic'
    headers = {
        'Content-Type': 'text/html',
    }
    initial_data = '''
        <html>
        <head>
        </head>
        <body onload="setTimeout('window.location.reload()', 2000);">
    '''
    
    def encode(self, data):
        return '<b>%s</b><br>\r\n' % (json.write(data),)

class IFrameTransport(Transport):
    name = 'iframe'
    headers = {
        'Content-Length': '1000000',
        'Content-Type':   'text/html',
        'Cache-Control':  'no-cache',
    }
    
    initial_data = '''
        <html>
        <head>
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
            
            document.domain = extract_xss_domain(document.domain);
          </script>
        </head>
        <body onLoad="try{parent.%(callback)s_reconnect();}catch(e){alert(e.message);}">
    ''' + ('<span></span>' * 100)
    
    def get_initial_data(self):
        return self.initial_data % {'callback':self.callback, 'domain':self.domain}
    
    def encode(self, data):
        # alert('sending event failed %(callback)s' + e.description + ' ' + e.message + ' '  + parent.%(callback)s);
        return '''<script>try{parent.%(callback)s(%(data)s);}catch(e){alert(e.message);}</script>''' % \
                    {'callback':self.callback, 'data':json.write(data)}
    
class SSETransport(Transport):
    name = 'sse'
    headers = {
        'Content-Type': 'application/x-dom-event-stream',
        'Reconnection-Time':  '5000',
        'Cache-Control': 'no-cache',
    }
    
    def encode(self, data):
        return (
            'Event: orbited\n' +
            '\n'.join(['data: %s' % line for line in data.splitlines()]) +
            '\n\n'
        )

class XHRStreamTransport(Transport):
    name = 'xhr_stream'
    boundary = '\r\n|O|\r\n'
    headers = {
        'Content-Type': 'application/x-orbited-event-stream'
    }
    
    initial_data = '.'*256 + '\r\n\r\n'
        
    def encode(self, data):        
        return data + self.boundary
    
class XHRMultipartTransport(Transport):
    name = 'xhr_multipart'
    boundary = 'orbited--'
    multipart_content_type = 'application/json'
    
    headers = {
        'Content-Type': 'multipart/x-mixed-replace;boundary="%s"' % boundary
    }
        
    def encode(self, data):
        boundary = "\r\n--%s\r\n" % self.boundary
        headers = (formatBlock('''
            Content-type: %s
            Content-length: %s
        ''') + '\r\n\r\n') % (self.multipart_content_type, len(data))
        return ''.join([headers, data, boundary])
    
