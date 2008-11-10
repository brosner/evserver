#!/usr/bin/python
# -*- coding: utf-8 -*-

from functools import wraps
from django.http import HttpResponse, HttpResponseBadRequest
import django_evserver.json as json
from django_evserver.server import defer_for_fifo, EVENT_CLOSED

import django_evserver.transports as transports
import os, os.path, logging, traceback
log = logging.getLogger(os.path.basename(__file__))

import sys
transports = {
    'basic':                transports.BasicTransport,
    'iframe':               transports.IFrameTransport,
    'htmlfile':             transports.IFrameTransport,
    'server_sent_events':   transports.SSETransport,
    'sse':                  transports.SSETransport,
    'xhr_multipart':        transports.XHRMultipartTransport,
    'xhr_stream':           transports.XHRStreamTransport,
    'xhr':                  transports.XHRStreamTransport,
}


def comet_start(transport, callback, domain):
    ''' Produce headers content for comet conection. '''
    if transport == 'sse':
        data     = '''Event: sessionid\ndata: p4sq1n8b$EGcGnKpwW7yNw\n\n\r\n'''
        mimetype = 'application/x-dom-event-stream'
    elif transport == 'iframe' or transport == 'htmlfile':
        fill = '<span></span>'*80  + '\r\n\r\n' # fill for safari, 1024 bytes of padding
        if transport == 'htmlfile':
            domain = '''<script>try{document.domain='%s';}catch(e){alert('Setting document.domain failed.');}</script>\n''' % domain
        else:
            domain = ''
        data     = '''<html><body onLoad="try{parent.%s_reconnect(true);}catch(e){};">%s\n%s\n''' % \
                      (callback, domain, fill)
        mimetype = 'text/html; charset=utf-8'
    else: # if transport == 'xhr':
        ## application/xml based on: http://lists.macosforge.org/pipermail/webkit-dev/2007-June/002041.html
        ## must be some message here, at least one byte long...
        data = ' '
        mimetype = 'application/xml; charset=utf-8'

    return (data, mimetype)

def comet_continue(transport, data, callback):
    ''' Create data wrapper on comet conection. '''
    if transport == 'sse':
        content = '''Event: comet\ndata: %s\n\n''' % data
    elif transport == 'iframe' or transport == 'htmlfile':
        content = '''<script>try{parent.%s(%s);}catch(e){alert('c ' + document.domain);}</script>\r\n''' % \
            (callback, json.write(data))
    else:    #elif transport == 'xhr':
        content = '''%s\r\n''' % data
    return content



def comet_fifo_json(fifo_name='', time_delta=30.0):
   def decorator(function):
       @wraps(function)
       def _wrapper(request, *args, **kwargs):
           return json_comet_wrapper(request, function, fifo_name, time_delta, *args, **kwargs)
       return _wrapper
   return decorator


def json_comet_wrapper(request, user_view, fifo_name, time_delta, *args, **kwargs):
    response_prev = request.META.get('response_prev', None)
    event_flags   = request.META.get('event_flags', None)
    event_type    = request.META.get('event_type', None)

    if not response_prev:
        transport = request.GET.get('transport', None)
        callback  = request.GET.get('callback', 'c').replace("'", "").replace('"', '')
        domain    = request.GET.get('domain', request.META['SERVER_NAME']).replace("'", "").replace('"', '')
        view_data = {}
        first_request = True
    else:
        transport = response_prev.transport
        callback  = response_prev.callback
        view_data = response_prev.view_data
        first_request = False
       
    
    # run callback if first request or event (not on timeout)
    if event_flags != 1:
        keepalive = False
    else: # keepalive
        keepalive = True
    
        
    #kwargs.setdefault('response_prev', response_prev)
    #kwargs.setdefault('event_flags', event_flags)
    kwargs.setdefault('view_data', view_data) # that's going to be changed by callback
    kwargs.setdefault('keepalive', keepalive)
    kwargs.setdefault('event_type', event_type)
    
    payload = user_view(request, *args, **kwargs)
    if not keepalive or payload: # not keepalive or something returned
        payload = json.write(payload)
    else: #keepalive and empty response
        payload = ' '
    
    # produce Response object, for comet application
    # first request, not continuation
    if event_type == EVENT_CLOSED:
        return HttpResponse()
    elif first_request:
        content, mimetype = comet_start(transport, callback, domain)
        response = HttpResponse(content, mimetype=mimetype)
        response['Cache-Control'] = 'no-cache'

        # append user data
        content = comet_continue(transport, payload, callback)
        response.write(content)
    # if not first_request: -> continue previous request
    else: 
        content  = comet_continue(transport, payload, callback)
        response = HttpResponse(content)

    
    response.transport = transport
    response.callback  = callback
    response.view_data = view_data
    
    
    return defer_for_fifo(
        response,
        fifo_name, time_delta,
        request.META['PATH_INFO'])





def comet_fifo(time_delta=30.0):
   def decorator(function):
       @wraps(function)
       def _wrapper(request, *args, **kwargs):
           print "ok"
           return comet_wrapper(request, function, time_delta, *args, **kwargs)
       return _wrapper
   return decorator


def comet_wrapper(request, user_view, time_delta, *args, **kwargs):
    print "ok"
    response_prev = request.META.get('response_prev', None)
    event_flags   = request.META.get('event_flags', None)
    event_type    = request.META.get('event_type', None)

    if not response_prev:
        transport = request.GET.get('transport', None)
        callback  = request.GET.get('callback', 'c').replace("'", "").replace('"', '')
        domain    = request.GET.get('domain', request.META['SERVER_NAME']).replace("'", "").replace('"', '')
        view_data = {}
        first_request = True
    else:
        transport = response_prev.transport
        callback  = response_prev.callback
        view_data = response_prev.view_data
        first_request = False
       
    
    # run callback if first request or event (not on timeout)
    if event_flags != 1:
        keepalive = False
    else: # keepalive
        keepalive = True
    
        
    #kwargs.setdefault('response_prev', response_prev)
    #kwargs.setdefault('event_flags', event_flags)
    kwargs.setdefault('view_data', view_data) # that's going to be changed by callback
    kwargs.setdefault('keepalive', keepalive)
    kwargs.setdefault('event_type', event_type)
    
    try:
        fifo_name, payload = user_view(request, *args, **kwargs)
    except Exception, e:
        tb = traceback.format_exc()
        log.error('got exception in comet handler\n%s' % tb)
        return HttpResponseBadRequest()
    print "ok"
    if not keepalive or payload: # not keepalive or something returned
        payload = payload
    else: #keepalive and empty response
        payload = ' '
    
    # produce Response object, for comet application
    # first request, not continuation
    if event_type == EVENT_CLOSED:
        return HttpResponse()
    elif isinstance(payload, HttpResponse):
        return payload
    elif first_request:
        content, mimetype = comet_start(transport, callback, domain)
        response = HttpResponse(content, mimetype=mimetype)
        response['Cache-Control'] = 'no-cache'

        # append user data
        content = comet_continue(transport, payload, callback)
        response.write(content)
    # if not first_request: -> continue previous request
    else: 
        content  = comet_continue(transport, payload, callback)
        response = HttpResponse(content)

    
    response.transport = transport
    response.callback  = callback
    response.view_data = view_data
    
    
    return defer_for_fifo(
        response,
        fifo_name, time_delta,
        request.META['PATH_INFO'])









def orbited_comet_fifo():
   def decorator(function):
       @wraps(function)
       def _wrapper(request, *args, **kwargs):
           return orbited_comet_wrapper(request, function, *args, **kwargs)
       return _wrapper
   return decorator



def orbited_comet_wrapper(request, user_view, *args, **kwargs):
    response_prev = request.META.get('response_prev', None)
    event_flags   = request.META.get('event_flags', None)
    event_type    = request.META.get('event_type', None)
    
    etype = None

    if not response_prev:
        transport = request.GET.get('transport', 'basic')
        callback  = request.GET.get('callback', 'c')
        domain    = request.GET.get('domain', None)
        try:
            transport = transports[transport](callback=callback, domain=domain)
        except KeyError:
            transport = transports['basic'](callback=callback, domain=domain)
        user_data = {}
        etype      = 'new'
    else:
        transport = response_prev.transport
        user_data = response_prev.user_data
        etype      = 'event'
       
    # run callback if first request or event (not on timeout)
    if event_flags == 1:
        etype = 'keepalive'
    
    if event_type == EVENT_CLOSED:
        etype = 'closed'
    
    kwargs.setdefault('user_data', user_data) # that's going to be changed by callback
    kwargs.setdefault('event_type', etype)
    
    try:
        payload = user_view(request, *args, **kwargs)
        if isinstance(payload, tuple):
            (fifo_name, time_delta, payload) = payload
        
    except Exception, e:
        tb = traceback.format_exc()
        log.error('got exception in comet handler\n%s' % tb)
        return HttpResponseBadRequest()
    
    if not payload: # just in case
        payload = ' '
    
    if isinstance(fifo_name, int):
        status = fifo_name
    else:
        status = 200
    
    # produce Response object, for comet application
    # first request, not continuation
    if etype == 'closed':
        return HttpResponse(status=status)
    elif isinstance(payload, HttpResponse):
        return payload
    
    if not isinstance(payload, list):
        payloads = [payload]
    else:
        payloads = payload
    
    content = '\r\n'.join(map(transport.encode, payloads))
    
    if etype == 'new':
        response = HttpResponse( transport.get_initial_data(), status=status)
        response['Cache-Control'] = 'no-cache'
        
        for key, value in transport.headers.items():
            response[key] = value

        response.write(content)
    # if not first_request: -> continue previous request
    else: 
        response = HttpResponse(content, status=status)

    if isinstance(fifo_name, int):
        return response
    
    # save data
    response.transport = transport
    response.user_data = user_data
    
    return defer_for_fifo(
        response,
        fifo_name, time_delta,
        request.META['PATH_INFO'])

