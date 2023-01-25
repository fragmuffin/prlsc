#ifndef _PRLSC_H
#define _PRLSC_H

#include <inttypes.h>
#include <stdbool.h>


// ==================== Constants ====================
// prlsc_errorCode_t
#define PRLSC_ERRORCODE_NONE                         (0u)
#define PRLSC_ERRORCODE_RXFRAME_BAD_ESC              (1u)
#define PRLSC_ERRORCODE_RXFRAME_SERVICEINDEX_BOUNDS  (2u)
#define PRLSC_ERRORCODE_RXFRAME_TOO_LONG             (3u)
#define PRLSC_ERRORCODE_RXFRAME_BAD_CHECKSUM         (4u)
#define PRLSC_ERRORCODE_DATAGRAM_BAD_CHECKSUM        (5u)
#define PRLSC_ERRORCODE_DATAGRAM_TOO_LONG            (6u)
#define PRLSC_ERRORCODE_DATAGRAM_SERVICEINDEX_BOUNDS (7u)
#define PRLSC_ERRORCODE_TXFRAME_BAD_ESC              (8u)

// prlsc_serviceType_t
#define PRLSC_TYPE_STREAM       (1u)
#define PRLSC_TYPE_DIAGNOSTICS  (2u)

// prlsc_responseCode_t
#define PRLSC_RESPONSE_CODE_POSITIVE        (0x00u)
#define PRLSC_RESPONSE_CODE_INVALID_REQUEST (0x01u)
#define PRLSC_RESPONSE_CODE_UNKNOWN_REQUEST (0x02u)

// prlsc_rxFrameStateMachineState_t
#define PRLSC_RXFRAMESTATE_WAIT_STARTBYTE (0u)
#define PRLSC_RXFRAMESTATE_COLLECTING     (1u)
#define PRLSC_RXFRAMESTATE_ESC            (2u)

// prlsc_rxDatagramStateMachineState_t
#define PRLSC_RXDATAGRAMSTATE_POPULATING  (0u)
#define PRLSC_RXDATAGRAMSTATE_ERROR       (1u)

// prlsc_txByteState_t
#define PRLSC_TXBYTESTATE_DO_NOTHING        (0u)
#define PRLSC_TXBYTESTATE_START             (1u)
#define PRLSC_TXBYTESTATE_NORMAL_BYTE       (2u)
#define PRLSC_TXBYTESTATE_ESCAPED_BYTE      (3u)


// ==================== Macros ====================
#define PRLSC_FRAMEBUFFER_STARTBYTE(buffer)         ((buffer)[0])
#define PRLSC_FRAMEBUFFER_SERVICECODE(buffer)       ((buffer)[1])
#define PRLSC_FRAMEBUFFER_LENGTH(buffer)            ((buffer)[2])
#define PRLSC_FRAMEBUFFER_DATA(buffer)              (&((buffer)[3]))
#define PRLSC_FRAMEBUFFER_CHECKSUM(buffer)          ((buffer)[PRLSC_FRAMEBUFFER_LENGTH(buffer) + 3])

#define PRLSC_SERVICEINDEX(serviceCode)             (((serviceCode) & 0b11100000u) >> 5)
#define PRLSC_SUBSERVICEINDEX(serviceCode)          ((serviceCode) & 0b00011111u)
#define PRLSC_FRAMEBUFFER_SERVICEINDEX(buffer)      (PRLSC_SERVICEINDEX(PRLSC_FRAMEBUFFER_SERVICECODE(buffer)))
#define PRLSC_FRAMEBUFFER_SUBSERVICEINDEX(buffer)   (PRLSC_SUBSERVICEINDEX(PRLSC_FRAMEBUFFER_SERVICECODE(buffer)))

#define PRLSC_FRAME_SERVICECODE(frame)          ((((frame.serviceIndex & 0b00000111u) << 5) | (frame.subServiceIndex & 0b00011111u)) & 0xFFu)
#define PRLSC_DATAGRAM_SERVICECODE(datagram)    ((((datagram.serviceIndex & 0b00000111u) << 5) | (datagram.subServiceIndex & 0b00011111u)) & 0xFFu)


// ==================== Type Definitions ====================
typedef uint8_t prlsc_serviceIndex_t;
typedef uint8_t prlsc_subServiceIndex_t;
typedef uint8_t prlsc_serviceType_t;
typedef uint8_t prlsc_checksum_t;
typedef uint16_t prlsc_time_t;
typedef uint8_t prlsc_errorCode_t;
// State Machine States
typedef uint8_t prlsc_rxFrameStateMachineState_t;
typedef uint8_t prlsc_rxDatagramStateMachineState_t;
typedef uint8_t prlsc_txByteState_t;

// Response Codes
typedef uint8_t prlsc_responseCode_t;

// ---- Frame
typedef struct {
    prlsc_serviceIndex_t serviceIndex;
    prlsc_subServiceIndex_t subServiceIndex;
    uint8_t length; //!< number of bytes in `data` (does not include checksum)
    uint8_t *data;
    prlsc_checksum_t checksum;
} prlsc_frame_t;

// ---- Datagram
typedef struct {
    prlsc_serviceIndex_t serviceIndex;
    prlsc_subServiceIndex_t subServiceIndex;
    uint16_t length; //!< number of bytes in `data`
    uint8_t *data;
    prlsc_checksum_t checksum;
} prlsc_datagram_t;


// --- State (volatile, initialised to the same initial state each time)
typedef struct {
    prlsc_rxFrameStateMachineState_t state;
    uint16_t byteCount; //!< number of bytes expected in this frame (all other excluded)
    uint16_t curIdx; //!< current index in frame buffer
    uint8_t *buffer; //!< buffer size expected to be >= max(config.state[x].frameLengthMax + 4) bytes (for all services)
    uint8_t framesReceived; //!< rolling counter of frames received
} prlsc_rxFrameState_t;

typedef struct {
    prlsc_rxDatagramStateMachineState_t state;
    uint8_t *buffer; //!< buffer for datagram, must have a length of `datagramLengthMax` + 1 for diagnostic service, or `frameLengthMax` for streaming service
    uint8_t curIdx; //!< current index in buffer, should initially be 0u
} prlsc_rxDatagramState_t;

typedef struct {
    prlsc_rxFrameState_t frame;
    prlsc_rxDatagramState_t *datagram; //!< one per service
} prlsc_receiverState_t;

typedef struct {
    //! bufferSize: number of bytes in buffer, must be >=
    //!     streaming service: frameLengthMax + 4 + 1
    //!     diagnostics service: datagramLengthMax + ((datagramLengthMax / frameLengthMax) * 4) + 1
    uint16_t bufferSize;
    uint8_t *buffer; //!< ring-buffer of bytes to be transmitted (unencoded), must have bufferSize bytes available.
    uint16_t bufferIdx; //!< index of next byte to buffer (incremented when buffering)
    uint16_t txIdx; //!< index of next byte to transmit (if equal to bufferIdx, the buffer is empty) (incremented upon transmission)
} prlsc_transmitterBuffer_t;

typedef struct {
    // State memory used to create buffer strings
    uint8_t *frameBuffer; //!< buffer used to create a frame in a linear string before adding it to a service's circular buffer
    // Transmit string Setup (set once per frame)
    uint8_t *transmitBuffer; //!< buffer used to transmit from (all bytes after [0] will be encoded)
    uint16_t transmitLength;
    prlsc_serviceIndex_t transmitServiceIndex;
    // Transmit string State
    prlsc_txByteState_t state; //!< state-machine's state (init to `PRLSC_TXBYTESTATE_DO_NOTHING`)
    uint16_t bufferIndex; //!< current transmitting index (init to 0u)
} prlsc_transmitterState_t;

typedef struct {
    prlsc_errorCode_t errorCode; //!< contains the latest error encountered
    // Receiver State
    prlsc_receiverState_t receiver; //!< byte receiver status
    // Transmitter State
    prlsc_transmitterBuffer_t *transmitterBuffer; //!< transmitter state (one per service)
    prlsc_transmitterState_t transmitter; //!< byte transmitter status
    // Time Tracking
    prlsc_time_t *lastTransmitted; //!< time each service was last transmitted
    // TODO: clock overflow could incorrectly trigger rate-limiting, is this risk worth mitigating?
    bool newTxDataFlag; //!< flag is set to true when a new frame is added to the tx buffer of any service (may be consumed by application)
} prlsc_state_t;


// --- Config (non-volatile configuration)
// Configuration
typedef struct {
    bool            stream;
    prlsc_time_t    rateLimit; //!< uses main config's `timerPtr`
    bool            onlyTxLatest; //!< if set, only the last buffered frame will be transmitted, (only applicable for a stream)
} prlsc_serviceConfig_t;

//! PRLSC Configuration
typedef struct {
    // Frame byte encoding
    uint8_t frameByteStartFrame;
    uint8_t frameByteEsc;
    uint8_t frameByteEscStart;
    uint8_t frameByteEscEsc;

    // Callback(s)
    prlsc_time_t (*callbackGetTime)(void); //!< returns current time
    prlsc_checksum_t (*callbackChecksumCalc)(uint8_t *arr, uint16_t length); //!< called to calculate frame & datagram checksums
    void (*callbackSendByte)(uint8_t byte); //!< called to physically transmit `byte` over the serial bus
    void (*callbackReceivedDatagram)(prlsc_datagram_t); //!< called when a datagram is received (from any service)

    // Size limits
    uint8_t         frameLengthMax; //!< maximum number of data bytes in a frame {0 < `frameLengthMax` <= 0xFF}
    uint16_t        datagramLengthMax; //!< maximum number of data bytes in a datagram {0 < `datagramLengthMax` <= 0xFFFF}, and must be >= `frameLengthMax`

    // Services
    uint8_t                 serviceCount; //!< number of elements in the services array {0 > serviceCount >= 8}
    prlsc_serviceConfig_t * services; //!< lesser indexed services are sent with a higher priority
} prlsc_config_t;


// ==================== Global Variables ====================


// ==================== Function Prototypes ====================
// Utilities
extern prlsc_checksum_t prlsc_calcFrameBufferChecksum(prlsc_config_t *config, uint8_t *buffer);
extern bool prlsc_frameChecksumValid(prlsc_config_t *config, uint8_t *buffer);
extern prlsc_checksum_t prlsc_calcDatagramChecksum(prlsc_config_t *config, prlsc_datagram_t datagram);
extern bool prlsc_datagramChecksumValid(prlsc_config_t *config, prlsc_datagram_t datagram);
extern void prlsc_memcpy_flat2circular(uint8_t *dest, uint8_t *source, uint16_t length, uint8_t *destArr, uint16_t destLength);
extern void prlsc_memcpy_circular2flat(uint8_t *dest, uint8_t *source, uint16_t length, uint8_t *sourceArr, uint16_t sourceSize);
extern prlsc_time_t prlsc_timeDiff(prlsc_time_t fromTime, prlsc_time_t toTime);

// Receivers
extern void prlsc_receiveByte(prlsc_config_t *config, prlsc_state_t *state, uint8_t byte);
extern void prlsc_receiveFrame(prlsc_config_t *config, prlsc_state_t *state, prlsc_frame_t frame);

// Transmitters
extern uint16_t prlsc_bufferBytesRequired(prlsc_config_t *config, prlsc_state_t *state, prlsc_datagram_t *datagram);
extern uint16_t prlsc_transmitDatagram(prlsc_config_t *config, prlsc_state_t *state, prlsc_datagram_t datagram);
extern bool prlsc_prepareServiceTransmission(prlsc_config_t *config, prlsc_state_t *state, prlsc_serviceIndex_t *serviceIndex, prlsc_time_t *timeToRateLimitLifted);
extern bool prlsc_txByte(prlsc_config_t *config, prlsc_state_t *state);

#endif // header protection: _PRLSC_H
