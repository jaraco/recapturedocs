from __future__ import absolute_import
# http://docs.python.org/library/json.html
import json

class GenericEncoder(json.JSONEncoder):
	"""
	A JSON encoder that encodes any Python object similar to how
	the pickle module works.
	"""
	def default(self, object):
		# use the pickle protocol 2 to serialize the object
		reduced = object.__reduce_ex__(2)
		return self.save_reduce(*reduced, obj = object)

	def save_reduce(self, func, args, state, listitems=None,
		dictitems=None, obj=None):
		"""
		generate a JSON representation of this object's reduce_ex
		result.
		"""
		cls, args = args[0], args[1:]
		return self.encode(dict(
			__python_class__ = cls.__name__,
			__python_module__ = cls.__module__,
			args = self.encode(args),
			state = self.encode(state),
			))

encode = GenericEncoder().encode

def decode_object_hook(object):
	if '__python_class__' not in object.keys():
		return object
	class_name = object['__python_class__']
	mod_name = object['__python_module__']
	args = object['args']
	state = object['state']
	mod = __import__(mod_name)
	cls = getattr(mod, class_name)
	ob = cls.__new__(*args)
	ob.__dict__.update(state)
	return ob

decode = json.JSONDecoder(object_hook = decode_object_hook).decode
