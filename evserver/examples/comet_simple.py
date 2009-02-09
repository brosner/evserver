'''
    evserver --exec="import evserver.examples.comet_simple; application=evserver.examples.comet_simple.simplest_comet_application"

'''
import evserver.transports as transports

def simplest_comet_application(environ, start_response):
    t = transports.get_transport('basic')
    start_response('200 OK', t.get_headers())
    yield t.start()
    yield t.write('fist message!')
    yield t.write('second message!')
    yield t.write('third message!')
