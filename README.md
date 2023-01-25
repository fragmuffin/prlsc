# Serial Comms Protocol

"**Priority Rate Limited Serial Communications (PRLSC)**"
why?, because nothing else has this aacronymn... Also it's the first
one I could think of.

This defines the serial comms protocol linking the RaspberryPi to each
of the Arduino controllers.

The goal of this protocol is to combine:

* streamed data
* diagnostics

The _Physical_ & _Data Link_ layers are entrusted to UART
(via USB with the FT232R already on the ArduinoMega).
However we're lacking a `Transport` and `Network` layer.


## Terminology

PRLSC's terminology is modeled on the OSI-model.

_Frame_: 
A _frame_ is deciphered from a stream of bytes.
The stream can be tuned in to at any point in time, and the first whole
_frame_ will be picked up and passed 

_Packet_:
A _packet_ is formed from a valid _frame_
(this protocol is point-to-point, so there's no addressing necessary)

_Datagram_: 
A _datagram_ is formed from one, or many _packets_

more detail on all of these later.

## Requirements

### High Level

We'll need it to do:

 * diagnostics FIFO, frames are prioritised (both send and receive)
 * stream LIFO, buffer flushed every time it's popped
   (so, no buffer, just one value that's either been sent
   already, or it hasn't)
 * streamed frames are blindly sent; if they're corrupted, the
   destination node will ignore it.
 * diagnostics frames have more of a handshake.

### Protocol Needs

 * Distinction between Message Types:
    * Diagnostics
    * Position Stream
 * Prioritisation
    * Diagnostics frames are high priority
    * Position Stream is only sent if there's bandwidth
 * Traffic Shaping: (aka: rate limiting)
    * Diagnostic frames are sent at a maximum rate (typically alowing
      for a streamed frames to be sent in between multiplexed datagrams)
 * Multiple frames / packets for long diagnostics requests / responses.
 * Guarenteed acknowledgement
    * Positive if positive reception
    * Negative if negative reception
    * Negative if receive timeout
    * Virtual negative if no positive response received

## Structure

### Frame

* ``start_byte`` (byte) marks frame start
* ``service_code`` (byte) marks frame start
* ``data_length`` (byte) number of bytes (numeric 0-`frame_data_length_max`)
* ``frame_data[]`` (`data_length`-bytes) frame's payload
* ``checksum`` (byte) 2's compliment checksum of all bytes after `start_byte` to `frame_data`

A frame with an invalid `checksum` will be discarded; as if it were never sent.
This is a bit clumsy, but I'm not expecting enough corrupt data for this to be much of a problem.
Timeouts should keep us informed enough.

#### Encoding with Escape Bytes

PRLSC wraps frames in a similar way to SLIP (Serial Line Internet Protocol):
A frame start is defined by the `frame_byte_start_frame`. To distinguish between
an authentic start byte, and random frame data:

* if the `frame_byte_start_frame` occurs in anything following the
  first byte, the two byte sequence `frame_byte_esc`,
  `frame_byte_esc_start` is sent instead,
* if the `frame_byte_esc` byte occurs in the data, the two byte
  sequence `frame_byte_esc`, `frame_byte_esc_esc` is sent.

_Increases Frame Size_: in a worst-case scenario, this can almost
double the volume of data required to convey each payload.
Consider this when picking the byte values, and the underlying design
of the datagrams.

_Checksum_: during encoding, the checksum is calculated before the escape
bytes are injected. the checksum is also subject to this encoding

_Why so many different values?_: the `frame_byte_start_frame` marks the beginning of a _frame_, without exception.
This means if we make made `frame_byte_esc_start` == `frame_byte_start_frame`, then `frame_byte_start_frame`
could be found in a stream without it being the start of a frame.
So none of these 4 values should be equal to another.

### Packet

The `frame_data[]` from each _frame_ forms a _packet_
(there's no mulitplexing here).

So _packets_ are only conceptual, frame data is pushed straight up to
begin forming a datagram.

### Datagram

#### Stream Datagrams
Stream _datagrams_ are directly formed form each _packet's_ `packet_data`.

* ``datagram_data[]``(n-bytes) equal to the `packet_data[]` of the _packet_ this came from

#### Diagnostics Datagrams
Diagnostics _datagrams_ are formed from multiple _packets_.
When a _packet_ is formed from a _frame_ with data < `frame_data_length_max`,
the diagnostics _datagram_ is complete.
However, because some of the compositional _frames_ may have been dropped
due to corruption, the _datagram_ needs to be verified independently of
it's compositional _frames_, so we add another checksum byte.

* ``datagram_data[]`` (n-bytes) where n is simply the sum of all the bytes received in compositional packets.
* ``checksum`` (byte) only for diagnostics _datagrams_


## Usage

### Configuration

Each end of comms should have the same configuration.
Configuration parameters are:

* ``frame_byte_start_frame`` (byte)
* ``frame_byte_esc`` (byte)
* ``frame_byte_esc_start`` (byte)
* ``frame_byte_esc_esc`` (byte)

``frame_data_length_max`` (byte)
maximum number of bytes in a frame

``timer_ptr`` (word pointer)
Pointer to a timer register (only relevant for implementation in an
embedded environment)

**Per Service**

``service_code`` (byte) numeric 1-7
Identifies the content of the datagram, also serves as a priority.
The greater number service-codes are sent first, as long as the rate
limit allows.

``stream`` (boolean)

* _true_: a datagram is formed from every frame that's received.
  So a stream's payload can be no longer than
  `frame_data_length_max` bytes.
* _false_: the datagram's header will also contain a countdown of the
  number of frames remaining for the transmission.

``rate_limit`` (word)
Minimum time between sending frames.
_Unit_: the unit of this is the same as `timer_ptr`

``timeout_seq_frames``
Timeout for sequential frames.
If a frame is received for a non-streaming service which is not
the last frame for the datagram, this timeout begins. If the timeout
is reached, and `acknowledge` is true, a failure frame is returned.
If the remaining frames come after this timeout, they are considered
to be a separate datagram, whereby the checksum will likely fail, and
a second failure frame is returned.

``acknowledge`` (boolean)
if true, an ack frame is sent back upon successful, or confirmed
unsuccessful reception of a datagram.
(this option is typically set to true for diagnostics, and false
for streams)

### API

API is native to C, but so that data packing is done the same way
on both ends, the C implementation is compiled to a dynamic library,
then imported into the Python runtime for use on the Raspberry Pi.

Note: we often want to test this stuff on a single machine, so the
dynamic library is compiled, and referenced based on the machine's
archetecture (run in bash)

    $ uname -m

#### C

Example usage in C

```c
#include "prlsc.h"

// ---------- PRLSC Configuration
prlsc_config_t g_prlsc = {
    .timer_ptr = &TCNT5,
    .frame_data_length_max  = 32,
    // frame byte encoding
    .frame_byte_start_frame = 0xC0,
    .frame_byte_esc         = 0xDB,
    .frame_byte_esc_start   = 0xDC,
    .frame_byte_esc_esc     = 0xDD,
    // callbacks
    .callback_read_ready    = &l_serialReadReady,
    .callback_reader        = &l_readSerial,
    .callback_write_ready   = &l_serialWriteReady,
    .callback_writer        = &l_writeSerial,
    // services
    .service_count = 2,
    .services = {
        {
            // stream service
            .service_code = 2,
            .stream = TRUE,
            .rate_limit = 0x24, // I dunno, but that should fall slightly short of the expected fastest rate
            .timeout_seq_frames = 0, // not relevant for streams
            .acknowledge = FALSE,
            .callback = &l_processStream, // function called when datagram is received
        },{
            // diagnostics service
            .service_code = 1,
            .stream = FALSE,
            .rate_limit = 0, // not rate limited; should fill the gaps between stream data
            .timeout_seq_frames = 0x123, // I dunno, some timeout
            .acknowledge = TRUE,
            .callback = &l_processDiag, // function called when datagram is received
        }
    }

};


// ---------- Platform specific serial interface
// The following can be implemented however you'd like, this is just an example
// Note: these functions conceptually service a single serial line; a single
//       prlsc bus. This could all be duplicated to service another line
//       independent of this one.

/* Return TRUE if a byte is available to be read */
bool l_serialReadReady(void) {
    // TODO
    return (bool)(TRUE);
}

/* Read 1 byte of serial data from serial port's buffer */
uint8_t l_readSerial(void) {
    uint8_t read_byte = 0x00u;
    // TODO
    return read_byte;
}

/* Return TRUE if ready to transmit on serial */
bool l_serialWriteReady(void) {
    // TODO
    return TRUE; // always ready
}

/* Push 1 byte to the serial transmit buffer */
void l_writeSerial(uint8_t byte) {
    /* transmit data through serial port */
    // TODO
}


// ---------- Process Datagrams (diag|stream)
prlsc_datagram_t l_processDiag(prlsc_datagram_t request) {
    // read request, and process accordingly
    return prlsc_voidDatagram;
}

prlsc_datagram_t l_processStream(prlsc_datagram_t request) {
    // set PID target positions from data
    return prlsc_voidDatagram;
}

// ---------- Example Mainloop
void main(void) {
    for (;;) {
        prlsc_cyclicTask(&g_prlsc);
    }
}
```
    

#### Python
    
The below Python implementation is essentially a prettier passthrough
to the above C API's.

```python
import time
import json  # just for pretty printing
from comms import CommsService, Frame

# ----- Initialise Comms
# Functions ot send / receive serial data (eg: pyserial)
def write_serial(bytes):
    pass  # code to transmit bytes on serial comms

def read_serial():
    # code to receive a single byte, or bytes of a frame.
    # knowledge of the frame's structure is irrelevant.
    # (function must be non-blocking)
    return bytes

comms = CommsService(
    writer=write_serial,
    reader=read_signal,
)

# ----- Transmit
# Transmit single frame
frame = Frame(
    service=Frame.TYPE.STREAM,
    data=[0xA5, 0x5A, 0x00, 0xFF]
)
comms.transmit(frame)

# Transmission of arbitrary length (preferable)
transmit_frames = Frame.iterator(
    service=Frame.TYPE.STREAM,
    data=[0x11, 0x12, 0xFF],
)  # returns a Frame instance or a 
comms.transmit(transmit_frames)

# ----- Receive
while True:
    received_frames = comms.received()
    # calls read_serial and populates frames.
    # when a a frame is fully formed, it's returned
    # here (iterable).
    # Will not return a
        
    for frame in received_frames:
        if frame.service == Frame.TYPE.DIAG:
            print("Diag received:")
            print(json.dumps(frame.dict, indent=4))
        elif frame.service == Frame.TYPE.STREAM:
            print("Stream received:")
            print(json.dumps(frame.dict, indent=4))
        
    time.sleep(0.05)  # poll every 50ms

# Alternative
def handle_received_frame(frame):
    pass  # deal with incoming frames
            # probably a big state-machine

def handle_should_break():
    # If True is returned, the loop will break, and execution
    # can continue.
    return False
    
comms.receiver_loop(
    handler=handle_received_frame,
    break_on=handle_should_break,
    min_period=0.05, # if your throughput isn't fast enough, make this smaller.
)
```

