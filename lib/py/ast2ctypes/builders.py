import ctypes


# ---- ctype Builders / Helpers
def build_struct(cls, **kwargs):
    """
    Build a struct with the given class
    :param cls: ctypes Structure class to populate
    :param kwargs:
    :return: populated instance of cls
    """
    assert issubclass(cls, ctypes.Structure), "bad paramter"
    obj = cls()
    for (key, value) in kwargs.items():
        if key.endswith('__exact'):
            key = key[:-len('__exact')]
            assert key in dict(cls._fields_), "%s struct has no %s attribute" % (cls.__name__, key)
            setattr(obj, key, value)
        else:
            setattr(obj, key, dict(cls._fields_)[key](value))
    return obj


def build_array(cls, elements):
    """
    Build an array of the given class with the given values
    :param cls: ctypes class of array to build
    :param elements: list of values (python list)
    :return:
    """
    assert isinstance(elements, (tuple, list)), "bad parameter"
    array = (cls * len(elements))()
    for (i, value) in enumerate(elements):
        array[i] = value
    return array
