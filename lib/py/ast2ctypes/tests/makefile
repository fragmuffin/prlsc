PROJECT_NAME = test

# ===== Build Files =====
# Build Files
BUILD_FILES = \
	./$(PROJECT_NAME).c

# ===== Include Directories =====
INCLUDE_DIRS = \
	.

COMPILER_FLAGS = \
	-shared \
	$(addprefix -I,$(INCLUDE_DIRS)) \
	-fPIC \
	-g \
	-O0
	

# ../../../fake-headers
PREPROCESS_INCLUDE_DIRS = \
	.

PREPROCESS_FLAGS = \
	$(addprefix -I,$(PREPROCESS_INCLUDE_DIRS)) \
	-E \
	-O0

# ===== Output =====
OUT = $(PROJECT_NAME).so
GIT_IGNORED_FILES = \
	*.pyc \
	$(OUT) \
	*-preproc.c


# ===== Make Targets =====
all: test

build:
	gcc $(COMPILER_FLAGS) $(BUILD_FILES) -o $(OUT)

rebuild: clean build

preproc:
	gcc $(PREPROCESS_FLAGS) $(BUILD_FILES) > $(PROJECT_NAME)-preproc.c

clean:
	rm -rf $(GIT_IGNORED_FILES)

test: build preproc
	python -m unittest discover --verbose
