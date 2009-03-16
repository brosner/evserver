import evserver.transports

def encapsulate_to_comet(userfunction):
    def wrapper(request, *args, **kwargs):
        transport = evserver.transports.get_transport(
                            request.GET.get('transport','basic'),
                            callback=request.GET.get('callback','c0'),
                            domain=request.GET.get('domain',''))
        response = userfunction(request, *args, **kwargs)
        iterator = response._container
        def wrapper2():
            try:
                yield transport.start()
                for item in iterator:
                    if item:
                        yield transport.write(item)
                    else:
                        yield item
            except GeneratorExit:
                if getattr(iterator, 'close', None):
                    iterator.close()

        response._container = wrapper2()
        for k, v in transport.get_headers():
            response[k] = v
        return response

    return wrapper
