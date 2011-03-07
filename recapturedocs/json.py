from __future__ import absolute_import
# http://docs.python.org/library/json.html
import json

class GenericEncoder(json.JSONEncoder):
	def default(self, 