from recapturedocs.json import encode, decode

class X(object):
	def __init__(self, n):
		self.n = n
	def __eq__(self, other):
		return self.n == other.n

def test_encode_class():
	encode(X(3))

def test_decode_class():
	orig = X(4)
	restored = decode(encode(orig))
	assert restored == orig
