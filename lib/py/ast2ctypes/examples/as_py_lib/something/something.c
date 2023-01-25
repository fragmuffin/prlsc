#include <stdio.h>

int add(int a, int b) {
    return a + b;
}

int subtract(int a, int b) {
    return a - b;
}

int multiply(int a, int b) {
    return a * b;
}

// you get the point...
// how about something more complex

typedef struct {
    int x;
    int y;
} vertex_t;

typedef struct {
    unsigned char red;
    unsigned char green;
    unsigned char blue;
} color_t;

typedef struct {
    vertex_t topLeft;
    vertex_t bottomRight;
    color_t color;
} square_t;

int squaresArea(square_t square) {
    int width, height;
    width = square.bottomRight.x - square.topLeft.x;
    height = square.bottomRight.y - square.topLeft.y;
    return width * height;
}

// and something that uses an external function
void pointlessPrint(char *text) {
    printf("%s\n", text);
}

// how about a function pointer (stolen from the fn_ptr example, because originality just died)
int ratio2percent(int a, int b) {
    // converts a:b to percentage, eg: 10:20 = 50%
    // so ratio2percent(10, 20) will return (int)(50)
    return (a * 100) / b;
}

int passthrough(int (*func)(int, int), int a, int b) {
    // fun fact: without compiler flag of -O0 this whole function would be optimised out.
    // so... don't do that... or rather, don't not do that... now my head hurts.
    return func(a, b);
}

