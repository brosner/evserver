#!/usr/bin/python
import subprocess
import os
import signal
import random
import socket
import time
import sys
import traceback
import fcntl

try:
    os.mkfifo('/tmp/fifo')
except OSError:
    pass

def evserver_start(cmd):
    port = random.randint(32000,64000)
    fd = open('log','w')
    proc = subprocess.Popen(["./evserver/evserver.py", "--libevent=./evserver/libevent.so", "-n", "-vvv", "-l","127.0.0.1:%i" % port, "-e", cmd], stdout=fd.fileno())
    sd = socket.socket()
    sd.settimeout(3.0)
    for i in range(10):
        try:
            sd.connect( ('127.0.0.1',port) )
        except socket.error:
            pass
        else:
            break
        time.sleep(0.1)
    else:
        raise Exception("Can't connect to server")
    def x():
        b = open('log', 'r')
        a = b.read()
        b.close()
        return a
    proc.data = x
    proc.ffdd = fd
    return sd, proc

def evserver_stop(sd, proc):
    proc.ffdd.close()
    sd.close()
    os.kill(proc.pid, signal.SIGKILL)



def test_return_none():
    for data in ['None', '""', '[]']:
        for v in [0,1]:
            sd, pid = evserver_start("def application(*args): return %s" % data)

            sd.send("GET /test_return_none HTTP/1.%i\r\n\r\n" % v)
            headers, _, payload = sd.recv(8192).partition('\r\n\r\n')
            assert(not payload)
            assert('chunked' not in headers)
            assert('Transfer-Encoding' not in headers)
            assert(headers.startswith('HTTP/1.%i 500' % v))
            assert('Content-Length: 0' in headers)
            assert('Connection: close' not in headers)

            evserver_stop(sd, pid)

def test_return_empty():
    for v in [0,1]:
        sd, pid = evserver_start("def application(*args):return ['']")

        sd.send("GET /test_return_empty HTTP/1.%i\r\n\r\n" % v)
        headers, _, payload = sd.recv(8192).partition('\r\n\r\n')
        assert(not payload)
        assert('chunked' not in headers)
        assert('Transfer-Encoding' not in headers)
        assert(headers.startswith('HTTP/1.%i 500' % v))
        assert('Content-Length: 0' in headers)
        assert('Connection: close' not in headers)

        evserver_stop(sd, pid)

def test_return_single():
    for v in [0,1]:
        sd, pid = evserver_start("def application(*args):return ['a']")

        sd.send("GET /test_return_single HTTP/1.%i\r\n\r\n" % v)
        headers, _, payload = sd.recv(8192).partition('\r\n\r\n')
        assert(payload == 'a')
        assert('chunked' not in headers)
        assert('Transfer-Encoding' not in headers)
        assert(headers.startswith('HTTP/1.%i 500' % v))
        assert('Content-Length: 1' in headers)
        assert('Connection: close' not in headers)

        evserver_stop(sd, pid)


def test_return_chunked_10():
    for c in ["['a', 'b']", "( i for i in ['a', 'b'])", "('a', 'b')"]:
        sd, pid = evserver_start("def application(*args):return %s" % c)

        sd.send("GET /test_return_chunked_10 HTTP/1.0\r\n\r\n")
        headers, _, payload = sd.recv(8192).partition('\r\n\r\n')
        assert(payload == 'ab')
        assert('chunked' not in headers)
        assert(headers.startswith('HTTP/1.0 500'))
        assert('Content-Length:' not in headers)
        assert('Connection: close' in headers)
        '''
        try:
            sd.send('G')
            raise Exception('connection should be closed')
        except socket.error:
            pass
        '''
        evserver_stop(sd, pid)

def test_return_chunked_11():
    for c in ["['a', 'b']", "( i for i in ['a', 'b'])", "('a', 'b')"]:
        sd, pid = evserver_start("def application(*args):return %s" % c)

        sd.send("GET /test_return_chunked_11 HTTP/1.1\r\n\r\n")
        headers, _, payload = sd.recv(8192).partition('\r\n\r\n')
        assert(payload == '1\r\na\r\n1\r\nb\r\n0\r\n\r\n')
        assert('Transfer-Encoding: chunked' in headers)
        assert(headers.startswith('HTTP/1.1 500'))
        assert('Content-Length:' not in headers)
        assert('Connection: close' not in headers)

        evserver_stop(sd, pid)


def application_iteratorstop(environ, start_response):
    start_response("200 OK", [('Content-type','text/plain')])
    fd = os.open('/tmp/fifo', os.O_RDONLY | os.O_NONBLOCK)
    print "OPENING"
    sys.stdout.flush()
    try:
        yield 'Start!'
        for j in range(1):
            yield environ['x-wsgiorg.fdevent.readable'](fd, 1.0)
            yield '(%i)' % (j)
    except GeneratorExit:
        pass
    print "CLOSING"
    sys.stdout.flush()
    os.close(fd)

def test_iteratorstop_break():
    sd, proc = evserver_start("import test; application = test.application_iteratorstop")

    sd.send("GET /test_iteratorstop_break HTTP/1.0\n\r\n")
    headers, _, payload = sd.recv(8192).partition('\r\n\r\n')
    assert(payload == 'Start!')
    assert('Content-Length:' not in headers)
    assert('Connection: close' in headers)
    assert('OPENING' in proc.data())
    sd.close()
    time.sleep(0.1)
    assert('CLOSING' in proc.data())

    evserver_stop(sd, proc)

def test_iteratorstop_letend():
    sd, proc = evserver_start("import test; application = test.application_iteratorstop")

    sd.send("GET /test_iteratorstop_letend HTTP/1.0\n\r\n")
    headers, _, payload = sd.recv(8192).partition('\r\n\r\n')
    assert(payload == 'Start!')
    assert('Content-Length:' not in headers)
    assert('Connection: close' in headers)
    payload = sd.recv(8192) # wait
    assert(payload == '(0)')
    time.sleep(0.1)
    assert('OPENING' in proc.data())
    assert('CLOSING' in proc.data())
    evserver_stop(sd, proc)


if False:
    # this doesn't work for for new libevent
    def application_iteratorstop(environ, start_response):
        start_response("200 OK", [('Content-type','text/plain')])
        fd = os.open('/dev/null', os.O_RDONLY | os.O_NONBLOCK)
        try:
            yield 'Start!'
            for j in range(1):
                yield environ['x-wsgiorg.fdevent.readable'](fd, 0.5)
                yield '(%i)' % (j)
        except GeneratorExit:
            pass
        os.close(fd)

    def test_iterator_devnull():
        sd, proc = evserver_start("import test; application = test.application_iteratorstop")

        sd.send("GET /test_iterator_devnull HTTP/1.1\n\r\n")
        headers, _, payload = sd.recv(8192).partition('\r\n\r\n')
        assert(payload == 'Start!')
        assert('Content-Length:' not in headers)
        assert('Connection: close' not in headers)
        assert('Transfer-Encoding: chunked' in headers)
        payload = sd.recv(8192) # wait
        assert(payload == '(0)')

        evserver_stop(sd, proc)

'''
def test_headers_none():
    sd, pid = evserver_start("def application(env, startr):startr('123 Test app', [('Header', 'Value')]);return None")

def test_headers_single():
    sd, pid = evserver_start("def application(env, startr):startr('123 Test app', [('Header', 'Value')]);return ['a']")

def test_headers_chunk():
    sd, pid = evserver_start("def application(env, startr):startr('123 Test app', [('Header', 'Value')]);return ['a', 'b']")

def test_keepalive_10():
    sd, pid = evserver_start("def application(env, startr):startr('123 Test app', [('Header', 'Value')]);return ['a']")

def test_keepalive_11_single():
    sd, pid = evserver_start("def application(env, startr):startr('123 Test app', [('Header', 'Value')]);return ['a']")

def test_keepalive_11_chunk():
    sd, pid = evserver_start("def application(env, startr):startr('123 Test app', [('Header', 'Value')]);return ['a', 'b']")
'''

def test_return_chunked_11_keepalive():
    sd, pid = evserver_start("def application(*args):return ['a', 'b']")

    sd.send("GET /test_return_chunked_11 HTTP/1.1\r\nConnection: keep-alive\r\n\r\n")
    headers, _, payload = sd.recv(8192).partition('\r\n\r\n')
    assert(payload == '1\r\na\r\n1\r\nb\r\n0\r\n\r\n')
    assert('chunked' in headers)
    assert(headers.startswith('HTTP/1.1 500'))
    assert('Content-Length:' not in headers)
    assert('Connection: close' not in headers)

    sd.send("GET /test_return_chunked_11 HTTP/1.1\r\nConnection: keep-alive\r\n\r\n")
    headers, _, payload = sd.recv(8192).partition('\r\n\r\n')
    assert(payload == '1\r\na\r\n1\r\nb\r\n0\r\n\r\n')
    assert('chunked' in headers)
    assert(headers.startswith('HTTP/1.1 500'))
    assert('Content-Length:' not in headers)
    assert('Connection: close' not in headers)

    evserver_stop(sd, pid)




if __name__ == '__main__':
    for t in [t for t in globals().keys() if (t.startswith('test') and callable(globals()[t])) ]:
        try:
            ret = globals()[t]()
        except Exception, e:
            print str(traceback.format_exc()).strip()
            print "test %s: FAILED (%r)" % (t,e)
            sys.exit(1)
        if ret:
            print "test %s: FAILED (%r)" % (t,ret)
            sys.exit(1)
        print "test %s: OK" % (t,)
