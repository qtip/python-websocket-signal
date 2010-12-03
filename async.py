from threading import Thread
from time import sleep

class Async(Thread):
    def __init__(self, function, *args, **kwargs):
        self._callback = None
        self.function = function
        self.args = args
        self.kwargs = kwargs
        self._value = None
        self.finished = False
        Thread.__init__(self)
        self.start()
    def callback(self, _callback):
        self._callback = _callback
    @property
    def value(self):
        if not self.finished:
            self.join()
        return self._value
    def run(self):
        self._value = self.function(*self.args, **self.kwargs)
        self.finished = True
        if self._callback:
            self._callback(self)

if __name__ == "__main__":
    def slow_add(x,y):
        sleep(1)
        return x+y

    def print_value(async):
        print(async.value)

    print(Async(slow_add, 1, 2).value)          #blocking
    print(Async(slow_add, 1, 3))                #future
    Async(slow_add, 1, 4).callback(print_value) #callback
