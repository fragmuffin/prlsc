#ifndef _PRLSC_TEST_H
#define _PRLSC_TEST_H

#include "../src/prlsc.h"


// ======================== Function Prototypes ========================
// Serial comms
bool test_serialReadReady(void);
uint8_t test_readSerial(void);
bool test_serialWriteReady(void);
void test_writeSerial(uint8_t byte);

// Datagram Processors
prlsc_responseCode_t test_processDiag(prlsc_datagram_t request);
prlsc_responseCode_t test_processStream(prlsc_datagram_t request);



#endif // header protection: _PRLSC_TEST_H
