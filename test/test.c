#include <stdio.h>
#include <string.h>

#include "test.h"

uint16_t dummyTimer = 10u;

// ---------- PRLSC Configuration
/*
prlsc_serviceConfig_t g_prlscServices[] = {
    {
        // stream service
        .stream = TRUE,
        .rateLimit = 0x24, // I dunno, but that should fall slightly short of the expected fastest rate
        .timeoutSeqFrames = 0, // not relevant for streams
        .acknowledge = FALSE,
        .callback = &test_processStream, // function called when datagram is received
    },{
        // diagnostics service
        .stream = FALSE,
        .rateLimit = 0, // not rate limited; should fill the gaps between stream data
        .timeoutSeqFrames = 0x123, // I dunno, some timeout
        .acknowledge = TRUE,
        .callback = &test_processDiag, // function called when datagram is received
    }
};

// State

uint8_t g_prlscFrameBuffer[PRLSC_FRAME_MAX_BYTES];
uint8_t g_prlscCurFrameData[PRLSC_FRAME_MAX_BYTES];

prlsc_busState_t g_prlscState = {
    .frame = {
        .state = PRLSC_FRAMESTATE_WAIT_STARTBYTE,
        .byteCount = 0u,
        .curIdx = 0u,
        .buffer = g_prlscFrameBuffer,
        .frame = {
            .data = g_prlscCurFrameData,
        },
        .framesReceived = 0,
    },
};

prlsc_config_t g_prlsc = {
    .timerPtr = &dummyTimer,
    .frameDataLengthMax  = 32,
    // frame byte encoding
    .frameByteStartFrame    = 0xC0u,
    .frameByteEsc           = 0xDBu,
    .frameByteEscStart      = 0xDCu,
    .frameByteEscEsc        = 0xDDu,
    // callbacks
    .callbackReadReady  = &test_serialReadReady,
    .callbackReader     = &test_readSerial,
    .callbackWriteReady = &test_serialWriteReady,
    .callbackWriter     = &test_writeSerial,
    // services
    .serviceCount = 2,
    .services = g_prlscServices,
    // buffer(s)
    .state = &g_prlscState,
};
*/

// ---------- Platform specific serial interface
// The following can be implemented however you'd like, this is just an example
// Note: these functions conceptually service a single serial line; a single
//       prlsc bus. This could all be duplicated to service another line
//       independent of this one.

/* Return TRUE if a byte is available to be read */
bool test_serialReadReady(void) {
    // TODO
    return true;
}

/* Read 1 byte of serial data from serial port's buffer */
uint8_t test_readSerial(void) {
    uint8_t read_byte = 0x00u;
    // TODO
    return read_byte;
}

/* Return TRUE if ready to transmit on serial */
bool test_serialWriteReady(void) {
    // TODO
    return true; // always ready
}

/* Push 1 byte to the serial transmit buffer */
void test_writeSerial(uint8_t byte) {
    /* transmit data through serial port */
    // TODO
}


// ---------- Process Datagrams (diag|stream)
prlsc_responseCode_t test_processDiag(prlsc_datagram_t request) {
    // eg: read request, and process accordingly
    return PRLSC_RESPONSE_CODE_POSITIVE;
}

prlsc_responseCode_t test_processStream(prlsc_datagram_t request) {
    // eg: set PID target positions from data
    return PRLSC_RESPONSE_CODE_POSITIVE;
}


/** Process Communications
 * This process would typically run in an infinite loop, or a timed interrupt
 *
void process_comms(void) {
    // ----- Service tx/rx to keep comms alive -----
    // received any bytes, if so, push them to prlsc
    while (l_serialReadReady()) {
        prlsc_pushByte(&g_prlsc, l_readSerial());
    }
    // prlsc has bytes for us to transmit
    while (prlsc_bytesWriteReady(&g_prlsc)) {
        l_writeSerial(prlsc_popByte(&g_prlsc));
    }

    // ----- Receive & Process -----
    if (prlsc_datagramReceived()) {
        // Get Request
        prlsc_datagram_t request = prlsc_datagramPop(&g_prlsc);

        // Process request, and form response
        switch (request.type) {
            case PRLSC_TYPE_DIAGNOSTICS:
                {
                    l_processDiag(request);
                    break;
                }
            case PRLSC_TYPE_STREAM:
                {
                    l_processStream(request);
                    break;
                }
            default:
        }

        // Send response
        //prlsc_datagramPush(&g_prlsc, response);
    }

    // tick
    prlsc_tick();
}//*/






