import pickle

def save(key, objects):
	"""
	Use pickle to save objects to a file
	"""
	filename = os.path.join(os.path.dirname(__file__), key+'.pickle')
	with open(filename, 'wb') as file:
		pickle.dump(objects, file, protocol=pickle.HIGHEST_PROTOCOL)

def load(key):
	filename = os.path.join(os.path.dirname(__file__), key+'.pickle')
	if not os.path.isfile(filename):
		return
	with open(filename, 'rb') as file:
		return pickle.load(file)
