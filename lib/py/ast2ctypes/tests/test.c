/*
    - explicitly declared function pointer:
        - variable
        - attribute of struct
        - parameter to function
        - return from function
    - typedef'd function pointer:
        - (same use-cases for `explicitly declared`)
*/

// test_fn_variable
int (testFnVar)(int);

// test_fn_ptr_variable
int (* testFnPtrVar)(int);

// test_fn_ptr_param
void testFnPtrParamFunc(int (*func)(int)) {
}

// test_fn_ptr_return
// don't know how to do this without a typedef

// test_fn_td_variable
typedef int (testFnTdVar_t)(int);
testFnTdVar_t testFnTdVar;

// test_fn_ptr_td_variable
typedef int (* testFnPtrTdVar_t)(int);
testFnPtrTdVar_t testFnPtrTdVar;

// test_fn_ptr_td_param
typedef int (* testFnPtrDtParam_t)(int);
void testFnPtrDtParamFunc(testFnPtrDtParam_t func) {
}

// test_fn_ptr_td_return
typedef int (* testFnPtrDtReturn_t)(int);
testFnPtrDtReturn_t testFnPtrDtReturnFunc(void) {
    return (testFnPtrDtReturn_t)((void *)(0x00));
}



