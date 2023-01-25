typedef short int ret_t;
typedef short int param_t;

ret_t add(param_t a, param_t b) {
    return (ret_t)(a + b);
}

typedef ret_t (callback_t)(param_t a, param_t b);
ret_t passthrough(callback_t *func, param_t a, param_t b) {
    // without compiler flag of -O0 this whole function would be optimised out.
    // because it's... well... it's completely useless, let's be honest here.
    return func(a, b);
}
