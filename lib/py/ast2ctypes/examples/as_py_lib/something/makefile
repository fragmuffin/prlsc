PROJECT_NAME = something

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

PREPROCESS_INCLUDE_DIRS = \
	./fake-headers

PREPROCESS_FLAGS = \
	$(addprefix -I,$(PREPROCESS_INCLUDE_DIRS)) \
	-E \
	-O0

# ===== Output =====
OUT = $(PROJECT_NAME).so
CLEAN_FILES = \
	$(OUT) \
	$(PROJECT_NAME)-preproc.c


# ===== Make Targets =====
all: build preproc

rebuild: clean build preproc

preproc:
	gcc $(PREPROCESS_FLAGS) $(BUILD_FILES) > $(PROJECT_NAME)-preproc.c

build:
	gcc $(COMPILER_FLAGS) $(BUILD_FILES) -o $(OUT)

clean:
	rm -f $(CLEAN_FILES)
