#!/usr/bin/env python
from something import (
    # basics
    add, subtract, multiply,
    # nested struct example
    vertex_t, color_t, square_t,
    squaresArea,
    # external function example
    pointlessPrint,
    # function pointer
    ratio2percent, passthrough,
    ratio2percent__t,
)
import ctypes

# this also works
#from something import *

print(f"1 + 2 = {add(1, 2)}")
print(f"10 - 22 = {subtract(10, 22)}")
print(f"10 * 5 = {multiply(10, 5)}")


# --- nested struct example
top_left = vertex_t()
top_left.x = 10
top_left.y = 20

bottom_right = vertex_t()
bottom_right.x = 40
bottom_right.y = 30

green = color_t()
green.red = 0x00
green.green = 0xFF
green.blue = 0x00

shape = square_t()
shape.topLeft = top_left
shape.bottomRight = bottom_right
shape.color = green

print(f"area of square = {squaresArea(shape)}")


# --- pointless print function
# Rant:
#   there's nothing to prove here, I just wanted to share my pain which is the-necessity-of-fake-headers
#   go ahead, remove fake-headers from the makefile and see what I mean.
# Something more helpful:
#   just google "pycparser fake headers" to learn more, there are some awesome people out there that
#   document this sh.... shtuff.
pointlessPrint(b"this is printed to screen by library")

# --- function pointer example
# python callback
def add_stuff(a, b):
    return a + b

# function pointer type defined manually:
func_class = ctypes.CFUNCTYPE(ctypes.c_int32, ctypes.c_int32, ctypes.c_int32)
ans = passthrough(func_class(add_stuff), 70, 30)
print(f"70 + 30 = {ans}")

# masking the add_stuff function with the same function signature as ratio2percent.
# (otherwise known as "cheating")
ans = passthrough(ratio2percent__t(add_stuff), 40, 50)
print(f"40 + 50 = {ans}")

# Pull the function pointer type from passthrough's own argument declarations
# (this is probably the best use-case)
ans = passthrough(passthrough.argtypes[0](add_stuff), 22, 88)
print(f"22 + 88 = {ans}")

# c callback
# wrap the function call in it's own type
ans = passthrough(ratio2percent__t(ratio2percent), 50, 70)
print(f"50:70 = {ans}%")
