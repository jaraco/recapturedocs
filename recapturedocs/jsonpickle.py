"""
A few handlers to make sure recapturedocs objects are serializable to JSON
"""

import jsonpickle
from boto.resultset import ResultSet
from boto.mturk.connection import HIT


class BotoResultSetHandler(jsonpickle.handlers.BaseHandler):
    def flatten(self, obj, data):
        data[jsonpickle.tags.SEQ] = self._base.flatten(list(obj))
        data.update(self._base.flatten(vars(obj)))
        return data

    def restore(self, data):
        obj = ResultSet.__new__(ResultSet)
        data.pop(jsonpickle.tags.OBJECT)
        items = data.pop(jsonpickle.tags.SEQ)
        items = self._base.restore(items)
        obj.extend(items)
        obj.__dict__.update(self._base.restore(data))
        return obj


class OldStyleClassParamsHandler(jsonpickle.handlers.BaseHandler):
    params = ()

    def flatten(self, obj, data):
        data.update(self._base.flatten(vars(obj)))
        return data

    def restore(self, data):
        cls = jsonpickle.unpickler.loadclass(data.pop(jsonpickle.tags.OBJECT))
        obj = cls(*self.params)
        obj.__dict__.update(self._base.restore(data))
        return obj


class OldStyleClassParamsHandler_None(OldStyleClassParamsHandler):
    params = (None,)  # type: ignore


def setup_handlers():
    jsonpickle.handlers.registry.register(ResultSet, BotoResultSetHandler)
    jsonpickle.handlers.registry.register(HIT, OldStyleClassParamsHandler_None)
