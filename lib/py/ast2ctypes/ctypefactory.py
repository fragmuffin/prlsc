try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO
import logging
import pycparser
from pycparser.c_ast import (
    NodeVisitor,
    Typedef,
    PtrDecl, TypeDecl, FuncDecl, FuncDef,
    Struct,
    IdentifierType,
)
import fnmatch
from ctypes import (
    Structure,
    c_char,
    c_uint8, c_uint16, c_uint32, c_uint64,
    c_int8, c_int16, c_int32, c_int64,
    c_float, c_double, c_longdouble,
    POINTER, CFUNCTYPE,
)

log = logging.getLogger(__name__)


class CTypeFactory(NodeVisitor):
    """
    Generates ctypes classes from typedefs in c-code

    Preparation:
        The simplest way to present your code is with a generated precompiler
        c file. This can be generated as part of your existing toolchian with:

        $ gcc -I./fake-headers -E mycode.c > mycode-preproc.c

        note you will probably need to create a whole lot of blank headers
        and put them into fake-headers to baby-sit

    Usage:
        import pycparser
        with open('mycode-preproc.c', 'r') as cfilehandle:
            parser = pycparser.c_parser.CParser()
            ast = parser.parse(cfilehandle.read())
            factory = CTypeFactory(ast)
        checksum = factory['myprj_checksum_t'](0x00)
    """

    # Map types
    #   I've got to be honest, I'm not clear on how these types map to different fundamental
    #   binary numbering systems. two's compliment of a word, a single byte from 0 to 255... I'm
    #   just trial:error mapping them as I go (because I'm too lazy... or scared to google it).
    BASE_CTYPES_CLASS_MAP = {
        ('void',):                      None, # special case
        # Integer Types
        ('unsigned', 'char'):           c_uint8,
        ('unsigned', 'short', 'int'):   c_uint16,
        ('unsigned', 'int'):            c_uint32,
        ('long', 'unsigned', 'int'):    c_uint64,
        ('unsigned', 'long', 'int'):    c_uint64,
        ('signed', 'char'):             c_int8,
        ('char',):                      c_char,
        ('short', 'int'):               c_int16,
        ('int',):                       c_int32,
        ('long', 'int'):                c_int64,
        # Floating Point Types
        ('float',):                     c_float,
        ('double',):                    c_double,
        ('long', 'double',):            c_longdouble,
    }

    def __init__(self, ast, typedef_patterns=('*',), funcdef_patterns=('*',), ctypes_class_map=None, pack=False):
        """
        Parse given C-Code and maps typedefs matching pattern to self.ctypes_map
        :param ast: Abstract Syntax Tree provided by pycparser (pycparser.c_ast.FileAST instance)
        :param typedef_patterns: list of patterns of typedef's to map (uses fnmatch)
        :param funcdef_patterns: list of patterns of function defenitions to map (uses fnmatch)
        :param ctypes_class_map: dict of c-types (as a tuple of strings) to ctype base classes
                                    (defaults to self.BASE_CTYPES_CLASS_MAP)
        :param pack: if True, structures will be packed tight, instead of being padded based on the architecture
        """
        assert isinstance(ast, pycparser.c_ast.FileAST), "bad parameter type"
        self.ast = ast
        self.typedef_patterns = typedef_patterns
        self.funcdef_patterns = funcdef_patterns

        self.ctypes_class_map = ctypes_class_map
        if self.ctypes_class_map is None:
            self.ctypes_class_map = self.BASE_CTYPES_CLASS_MAP

        self.pack = pack

        # AST node maps from visitors
        self.typedef_map = {}
        self.funcdef_map = {}

        # Built classes
        self.ctypes_map = {}

        # populate
        #   - self.typedef_map
        #   - self.funcdef_map
        self.visit(self.ast)

        for (name, node) in self.typedef_map.items():
            log.debug("finding ctype for typedef: %s", name)
            if self._name_match(name, self.typedef_patterns):
                if name not in self.ctypes_map:
                    self._build_ctype(node, buffer=True)  # populates self.ctypes_map
                else:
                    log.debug("(%s is already buffered)", name)

        for (name, node) in self.funcdef_map.items():
            log.debug("finding ctype for function: %s", name)
            if self._name_match(name, self.funcdef_patterns):
                if name not in self.ctypes_map:
                    self._build_ctype(node, buffer=True)
                else:
                    log.debug("(%s is already buffered)", name)

    def _buffer_ctype(self, ctype_class, buffer=False):
        if ctype_class is None:
            return None
        name = ctype_class.__name__
        if buffer:
            if name not in self.ctypes_map:
                log.debug("buffered: %s", name)
                self.ctypes_map[name] = ctype_class
            else:
                log.debug("already buffered: %s", name)
                assert id(self.ctypes_map[name]) == id(ctype_class), "duplicate classes made (shouldn't be possible)"
            return self.ctypes_map[name]
        else:
            return ctype_class

    def _build_ctype(self, node, **kwargs):
        """
        Recursively calls down the given AST (node)
        :param node: AST node for which to build a ctype (instance of class inheriting from pycparser.c_ast.Node)
        :return: class inheriting from relevant ctype (dynamically built)
        """
        if isinstance(kwargs.get('recursive_depth', None), int):
            kwargs['recursive_depth'] += 1
        else:
            kwargs['recursive_depth'] = 0
        assert kwargs['recursive_depth'] < 60, "too many things"

        # debug stuff
        #str_buffer = StringIO()
        #node.show(buf=str_buffer, offset=kwargs['recursive_depth'])
        #print(str_buffer.getvalue().split('\n')[0])

        # args
        class_name = kwargs.get('class_name', None)

        if class_name and class_name in self.ctypes_map:
            return self.ctypes_map[class_name]

        if isinstance(node, Typedef):
            # type definition wrapper, pass down to type
            kwargs.update({'class_name': node.name})
            ctype_class = self._build_ctype(node.type, **kwargs)
            ctype_class.__name__ = node.name
            return self._buffer_ctype(ctype_class, True)  # always buffer typedefs (they're all global)

        elif isinstance(node, FuncDef):
            kwargs.update({'class_name': node.decl.name})
            ctype_class = self._build_ctype(node.decl.type, **kwargs)
            ctype_class.__name__ = node.decl.name
            return self._buffer_ctype(ctype_class, True)  # always buffer function def's (they're all global)

        elif isinstance(node, TypeDecl):
            # type declaration wrapper, pass down to type
            return self._build_ctype(node.type, **kwargs)

        elif isinstance(node, PtrDecl):
            # pointer
            if isinstance(node.type, FuncDecl):
                # TODO: explain why function pointers aren't pointers
                #       (coz I don't quite get why this is necessary yet)
                return self._build_ctype(node.type, **kwargs)
            return POINTER(self._build_ctype(node.type, **kwargs))

        elif isinstance(node, IdentifierType):
            if tuple(node.names) in self.ctypes_class_map:
                # base type:
                # typedef unsigned char uint8_t;
                return self.ctypes_class_map[tuple(node.names)]

            elif len(node.names) == 1 and node.names[0] in self.typedef_map:
                # referred type:
                # typedef uint8_t prlsc_checksum_t;

                # next_node = self.typedef_map[node.names[0]]
                # #kwargs.update({'class_name': node.names[0]})
                # base_class = self._build_ctype(next_node, buffer=True)
                # return self._process_ctype(type(class_name, (base_class,), {}), buffer)
                return self._build_ctype(self.typedef_map[node.names[0]], **kwargs)

            else:
                raise NotImplementedError("IdentifierType names not supported: '%s'" % ' '.join(node.names))

        elif isinstance(node, Struct):
            # struct
            _fields_ = []
            for decl in node.decls:
                _fields_.append((
                    decl.name,
                    self._build_ctype(decl.type, **kwargs)
                ))
            _pack_ = 1 if self.pack else 0

            return type(class_name, (Structure,), {
                '_fields_': _fields_,
                '_pack_': _pack_,
            })

        elif isinstance(node, FuncDecl):
            # function pointer: (minus the pointer)
            # void  (*callbackWriter)(uint8_t);
            ret_ctype = self._build_ctype(node.type, **kwargs)
            param_ctypes = []
            for param in node.args.params:
                param_ctypes.append(self._build_ctype(param.type, **kwargs))
            if param_ctypes == [None]:  # single parameter resembling (void), ie: no parameters
                param_ctypes =  []

            return CFUNCTYPE(*([ret_ctype] + param_ctypes))

        raise NotImplementedError("%r not supported" % node)

    def _name_match(self, name, patterns):
        """
        Returns true if name matches one of self.patterns
        :param name: string to test
        :return: True if name matches one or more of the fnmatch patterns in self.patterns
        """
        if isinstance(name, str):
            return any(fnmatch.fnmatch(name, p) for p in self.typedef_patterns)
        return False

    # ------ Visitors:
    def get_decl_name(self, node):
        """Gets a declaration name, or dies trying"""
        if isinstance(node, TypeDecl):
            return node.declname
        elif isinstance(node, FuncDef):
            return node.decl.name
        else:
            return self.get_decl_name(node.type)

    def visit_Typedef(self, node):
        """
        Typedef Visitor
        Stores the typedefs it finds in self.typedef_map

        Important: Preprocessed C files can contain multiples of the same typedef, from the same file.
            gcc -Ifake-headers -E file1.c file2.c > preproc.c
        Even though their definitions are identical, I've found their AST can be different.
        In these cases, the first stored AST is correct, and the second is not.
        This is why the first occurrence is stored, and the remainder are ignored.

        :param node: FileAST node being visited (pycparser.c_ast.Typedef instance)
        """
        name = self.get_decl_name(node)
        if name not in self.typedef_map:
            log.debug("--- found Typedef: %s", name)
            self.typedef_map[name] = node
        else:
            log.debug("--- found Typedef: %s (duplicate ignored)", name)

    def visit_FuncDef(self, node):
        """
        FuncDef Visitor
        Stores the function definitions it finds in self.funcdef_map
        :param node: AST node found in FileAST being visited (pycparser.c_ast.FuncDef instance)
        """
        name = self.get_decl_name(node)
        if name not in self.funcdef_map:
            log.debug("--- found FuncDef: %s", name)
            self.funcdef_map[name] = node
        else:
            log.debug("--- found FuncDef: %s (duplicate ignored)", name)
