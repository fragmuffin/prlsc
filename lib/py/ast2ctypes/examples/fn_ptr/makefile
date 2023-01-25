PROJECT_NAME = prog

# ===== Build Files =====
# Build Files
BUILD_FILES = \
	./prog.c

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
	$(OUT) \
	$(PROJECT_NAME)-preproc.c \
	$(PROJECT_NAME).gcno


# ===== Make Targets =====
all: run

build: $(OUT)

rebuild: clean build

preproc:
	gcc $(PREPROCESS_FLAGS) $(BUILD_FILES) > $(PROJECT_NAME)-preproc.c

$(OUT):
	gcc $(COMPILER_FLAGS) $(BUILD_FILES) -o $(OUT)

clean:
	rm -rf $(GIT_IGNORED_FILES)

run: build preproc
	python run.py
