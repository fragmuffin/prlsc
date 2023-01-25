PROJECT_NAME = test

# ===== Build Files =====
# Build Files
BUILD_FILES = \
	./test.c \
	../src/prlsc.c

# ===== Include Directories =====
INCLUDE_DIRS = \
	.

COMPILER_FLAGS = \
	-shared \
	$(addprefix -I,$(INCLUDE_DIRS)) \
	-fPIC \
	-ftest-coverage \
	-coverage \
	-g

PREPROCESS_INCLUDE_DIRS = \
	../../../utils/fake-headers

PREPROCESS_FLAGS = \
	$(addprefix -I,$(PREPROCESS_INCLUDE_DIRS)) \
	-E

# ===== Output =====
OUT = $(PROJECT_NAME).so
GIT_IGNORED_FILES=$(shell git check-ignore *)
CHECKOUT_COMMENT = automated checkout

# ===== Make Targets =====
all: test

build:
	gcc $(COMPILER_FLAGS) $(BUILD_FILES) -o $(OUT)

rebuild: clean $(OUT)

preproc:
	gcc $(PREPROCESS_FLAGS) $(BUILD_FILES) > $(PROJECT_NAME)-preproc.c

$(OUT):

clean:
	rm -rf $(GIT_IGNORED_FILES)

test: clean preproc build
	python -m unittest discover -s tests -p 'test_*.py' --verbose
	#python -m unittest --verbose tests.test_receiveFrame.TestDatagramBasics.test_basic_diag
	

# Test Coverage
test-coverage: test
	lcov --base-directory . --directory . -c -o $(PROJECT_NAME)-lcov.info
	rm -rf ./html
	genhtml -o ./html -t "prlsc test coverage" --num-spaces 4 $(PROJECT_NAME)-lcov.info

# Future Improvement: separate coverage per test, however, the test-list isn't that easy to get...
# to get test-list, in python:
#	>>> import unittestcase
#   >>> import testdll
#	>>> suite = unittest.TestSuite()
#   >>> suite.addTest(unittest.defaultTestLoader.loadTestsFromModule(testdll))
#	>>> for test in suite:
#   >>>     print test._tests # hierarchy of <unittest.suite.TestSuite> instances
