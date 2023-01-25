#include "prlsc.h"

#include <string.h>

// ========================== Global Variables ============================
// TODO: becuase multiple busses are possible, and entirely independant.
//       it's also possible that global variables are entirely replaced
//       with state variables.


// ========================= Functions: Initialization ===========================

// ========================= Functions: Utilities ===========================

/*! @brief Calculate frame checksum from buffer
 *
 *  @param buffer frame buffer, including the startByte
 *  @return calculated checksum value (ignores checksum byte of the frame buffer itself)
 */
prlsc_checksum_t prlsc_calcFrameBufferChecksum(prlsc_config_t *config, uint8_t *buffer) {
    volatile prlsc_checksum_t l_checksum; // volatile to remove compiler optimisations (causing problems)
    l_checksum = config->callbackChecksumCalc(
        &(PRLSC_FRAMEBUFFER_SERVICECODE(buffer)),
        PRLSC_FRAMEBUFFER_LENGTH(buffer) + 2
    );
    return l_checksum;
}


/*! @brief Determine if frame data is valid
 *
 *  @param buffer frame buffer, including the startByte
 *  @return true if frame data is valid, false otherwise
 */
bool prlsc_frameChecksumValid(prlsc_config_t *config, uint8_t *buffer) {
    bool checksumValid = true;
    if (PRLSC_FRAMEBUFFER_CHECKSUM(buffer) != prlsc_calcFrameBufferChecksum(config, buffer)) {
        checksumValid = false;
    }
    return checksumValid;
}


/*! @brief Calculate datagram's checksum
 *
 *  @param config bus configuration (contains the pointer to checksum calculation function)
 *  @param datagram datagram to calculate
 *  @return checksum value
 */
prlsc_checksum_t prlsc_calcDatagramChecksum(prlsc_config_t *config, prlsc_datagram_t datagram) {
    return config->callbackChecksumCalc(datagram.data, datagram.length);
}


/*! @brief Determine if datagram data is valid
 *
 *  @param config bus configuration (contains the pointer to checksum calculation function)
 *  @param datagram datagram to verify
 *  @return true if datagram data is valid, false otherwise
 */
bool prlsc_datagramChecksumValid(prlsc_config_t *config, prlsc_datagram_t datagram) {
    bool checksumValid = true;
    if (datagram.checksum != prlsc_calcDatagramChecksum(config, datagram)) {
        checksumValid = false;
    }
    return checksumValid;
}


/*! @brief Copy bytes from a standard linear array to a circular buffer
 *
 *  Copy will still work with > 1 revolution of the circular buffer (where: revolutions = destLength / length).
 *
 *  @param dest         pointer to first destination byte {destArr <= dest < destArr + (destSize * sizeof(uint8_t))}
 *  @param source       pointer to first byte of source (a standard array of bytes)
 *  @param length       number of bytes to copy
 *  @param destArr      pointer to first byte of circular buffer
 *  @param destLength   number of bytes in circular buffer
 */
void prlsc_memcpy_flat2circular(uint8_t *dest, uint8_t *source, uint16_t length, uint8_t *destArr, uint16_t destSize) {
    if (length > 0u) {
        uint16_t l_length = (length > destSize) ? destSize : length;
        uint16_t l_sourceIndex = (length - l_length);
        uint16_t l_destIndexEnd = ((uint16_t)(dest - destArr) + length) % destSize; // last index circular buffer + 1
        uint16_t l_destIndex = (l_destIndexEnd - l_length) + ((l_length > l_destIndexEnd) ? destSize : 0u);

        if (l_destIndex == 0u || l_destIndex < l_destIndexEnd) {
            memcpy(&(destArr[l_destIndex]), &(source[l_sourceIndex]), l_length);
        } else {
            memcpy(&(destArr[l_destIndex]), &(source[l_sourceIndex]), destSize - l_destIndex);
            memcpy(&(destArr[0]), &(source[l_sourceIndex + (destSize - l_destIndex)]), l_length - (destSize - l_destIndex));
        }
    }
}


/*! @brief Copy bytes from a circular buffer to a standard linear array
 *
 *  If requested to copy > 1 revoluion, only 1 revolution will be copied (where: revolutions = sourceLength / length).
 *
 *  @param dest         pointer to first destination byte (a standard array of bytes)
 *  @param source       pointer to first byte of source {sourceArr <= source < sourceArr + destLength}
 *  @param length       number of bytes to copy
 *  @param sourceArr    pointer to first byte of circular buffer
 *  @param sourceSize   number of bytes in circular buffer
 */
void prlsc_memcpy_circular2flat(uint8_t *dest, uint8_t *source, uint16_t length, uint8_t *sourceArr, uint16_t sourceSize) {
    if (length > 0u) {
        uint16_t l_sourceIndex = (uint16_t)(source - sourceArr);
        uint16_t l_length = (length > sourceSize) ? sourceSize : length;
        if (l_sourceIndex + l_length < sourceSize) {
            memcpy(dest, source, l_length);
        } else {
            memcpy(dest, source, sourceSize - l_sourceIndex);
            memcpy(&(dest[sourceSize - l_sourceIndex]), sourceArr, l_length - (sourceSize - l_sourceIndex));
        }
    }
}


/*! @brief Calculate time difference
 *
 *  Equivalent of to_time - fromTime, but handles overflow scenarios
 *
 *  @param fromTime start time
 *  @param toTime end time
 *  @return time passed between the 2 points
 */
prlsc_time_t prlsc_timeDiff(prlsc_time_t fromTime, prlsc_time_t toTime) {
    // Assumption: given values, and the counter/timer used will
    // overflow as a uint16 (same as prlsc_time_t type).
    // If overflow is less than that of a uint16, this will need to be more
    // than a simple difference calculation.
    return toTime - fromTime;
}


// ========================= Functions: Receiving ===========================

/*! @brief Push byte from serial bus into PRLSC interpreter
 *
 *  Buffer will begin to populate with a startFrame byte. At any stage a
 *  startFrame byte will reset the accumulator, ignoring all previous bytes.<br/>
 *  Proceeding bytes will be decoded and stored in a buffer.<br/>
 *  Once the frame is fully formed, it will be passed to prlsc_pushFrame()
 *
 *  @param config prlsc configuration
 *  @param byte byte that's been received on serial
 */
void prlsc_receiveByte(prlsc_config_t *config, prlsc_state_t *state, uint8_t byte) {
    prlsc_rxFrameState_t *frameState = &(state->receiver.frame);
    // push
    bool l_push = false;
    uint8_t l_byte = byte;

    // State machine
    if (byte == config->frameByteStartFrame) {
        // Start byte resets state, without exception.
        frameState->curIdx = 0u;
        frameState->byteCount = config->frameLengthMax + 4u; // will be corrected when 2nd byte is received
        l_push = true;
        frameState->state = PRLSC_RXFRAMESTATE_COLLECTING;
    } else {
        switch (frameState->state) {
            case PRLSC_RXFRAMESTATE_COLLECTING:
                {
                    if (byte == config->frameByteEsc) {
                        // escape sequence found, don't collect byte, just change state
                        frameState->state = PRLSC_RXFRAMESTATE_ESC;
                    } else {
                        l_push = true;
                    }
                } break;
            case PRLSC_RXFRAMESTATE_ESC:
                {
                    // last byte to be received was an escape byte...
                    if (byte == config->frameByteEscEsc) {
                        l_byte = config->frameByteEsc;
                        l_push = true;
                        frameState->state = PRLSC_RXFRAMESTATE_COLLECTING;
                    } else if (byte == config->frameByteEscStart) {
                        l_byte = config->frameByteStartFrame;
                        l_push = true;
                        frameState->state = PRLSC_RXFRAMESTATE_COLLECTING;
                    } else {
                        // oops!, invalid byte, wait for next frame
                        frameState->state = PRLSC_RXFRAMESTATE_WAIT_STARTBYTE;
                        state->errorCode = PRLSC_ERRORCODE_RXFRAME_BAD_ESC;
                    }
                } break;
            case PRLSC_RXFRAMESTATE_WAIT_STARTBYTE:
            default:
                // all bytes received are ignored until a start-byte is captured
                break;
        }
    }

    // Push byte to buffer
    if (l_push == true) {
        frameState->buffer[frameState->curIdx] = l_byte;

        if (frameState->curIdx == 1) {
            // Set Service Code
            if (PRLSC_SERVICEINDEX(l_byte) >= config->serviceCount) {
                // oops, service code exceeds index bounds
                frameState->state = PRLSC_RXFRAMESTATE_WAIT_STARTBYTE;
                state->errorCode = PRLSC_ERRORCODE_RXFRAME_SERVICEINDEX_BOUNDS;
            }
        } else if (frameState->curIdx == 2) {
            // Set Data Length
            // 2nd byte in sequence is the data_length
            if (l_byte <= config->frameLengthMax) {
                // frame size = data_length + <the following:>
                //  [0] - start_byte    (1-byte)
                //  [1] - service_code  (1-byte)
                //  [2] - data_length   (1-byte) (this byte)
                //  [n] - checksum      (1-byte)
                frameState->byteCount = l_byte + 4;
            } else {
                // oops, frame's too long
                frameState->state = PRLSC_RXFRAMESTATE_WAIT_STARTBYTE;
                state->errorCode = PRLSC_ERRORCODE_RXFRAME_TOO_LONG;
            }
        }

        // Increment frame buffer index
        frameState->curIdx++;

        // Frame Completion
        if (frameState->curIdx >= frameState->byteCount) {
            // Last byte received
            if (prlsc_frameChecksumValid(config, frameState->buffer)) {
                prlsc_frame_t l_frame;

                // Frame is valid
                // Increase number received (for testing)
                frameState->framesReceived++;

                // Copy byte-buffer to frame
                l_frame.serviceIndex = PRLSC_FRAMEBUFFER_SERVICEINDEX(frameState->buffer);
                l_frame.subServiceIndex = PRLSC_FRAMEBUFFER_SUBSERVICEINDEX(frameState->buffer);
                l_frame.length = PRLSC_FRAMEBUFFER_LENGTH(frameState->buffer);
                l_frame.data = PRLSC_FRAMEBUFFER_DATA(frameState->buffer); // references frameState buffer, not a copy
                l_frame.checksum = PRLSC_FRAMEBUFFER_CHECKSUM(frameState->buffer);

                // Pass up the chain
                prlsc_receiveFrame(config, state, l_frame);
            } else {
                // oops, bad checksum
                state->errorCode = PRLSC_ERRORCODE_RXFRAME_BAD_CHECKSUM;
            }
            // Set state-machine to wait
            frameState->state = PRLSC_RXFRAMESTATE_WAIT_STARTBYTE;
        }
    }
}


/*! @brief Push valid frame upstream
 *
 *  Frames will form datagrams.
 *  When a datagram is completed, it is pushed upstream
 *
 *  @param config prlsc configuration
 *  @param frame frame struct to push
 */
void prlsc_receiveFrame(prlsc_config_t *config, prlsc_state_t *state, prlsc_frame_t frame) {
    prlsc_rxDatagramState_t *l_state = &(state->receiver.datagram[frame.serviceIndex]);
    prlsc_serviceConfig_t *serviceConfig = &(config->services[frame.serviceIndex]);

    switch (l_state->state) {
        case PRLSC_RXDATAGRAMSTATE_POPULATING:
            {
                if ((l_state->curIdx + frame.length - 1) > config->datagramLengthMax) {
                    l_state->curIdx = 0;
                    if ((frame.length >= config->frameLengthMax) && (serviceConfig->stream != true)) {
                        l_state->state = PRLSC_RXDATAGRAMSTATE_ERROR;
                    } // else: try next frame
                    state->errorCode = PRLSC_ERRORCODE_DATAGRAM_TOO_LONG;
                } else {

                    // Append frame's data to datagram's buffer
                    if (frame.length > 0) {
                        memcpy(&(l_state->buffer[l_state->curIdx]), frame.data, frame.length);
                        l_state->curIdx += frame.length;
                    }

                    if ((frame.length < config->frameLengthMax) || (serviceConfig->stream == true)) {
                        // This is the last frame, datagram is complete.
                        prlsc_datagram_t l_datagram;

                        // Build Datagram
                        l_datagram.serviceIndex = frame.serviceIndex;
                        l_datagram.subServiceIndex = frame.subServiceIndex;
                        l_datagram.data = l_state->buffer;
                        if (serviceConfig->stream == true || l_state->curIdx == 0u) {
                            l_datagram.length = l_state->curIdx;
                            l_datagram.checksum = 0u;
                        } else {
                            l_datagram.length = l_state->curIdx - 1;
                            l_datagram.checksum = l_state->buffer[l_state->curIdx - 1];
                        }

                        // Checksum verification (if relevant)
                        if ((serviceConfig->stream == true) || prlsc_datagramChecksumValid(config, l_datagram)) {
                            // Call configured datagram receiver callback (application dependent)
                            config->callbackReceivedDatagram(l_datagram);
                        } else {
                            state->errorCode = PRLSC_ERRORCODE_DATAGRAM_BAD_CHECKSUM;
                        }

                        l_state->curIdx = 0;
                    }
                }
            } break;
        case PRLSC_RXDATAGRAMSTATE_ERROR:
        default:
            {
                if ((frame.length < config->frameLengthMax) || (serviceConfig->stream == true)) {
                    l_state->state = PRLSC_RXDATAGRAMSTATE_POPULATING;
                }
            } break;
    }
}


// ========================= Functions: Transmitting ===========================

/*! @brief Buffer bytes required to transmit given datagram
 *
 *  Calculate how many buffer bytes will be needed to store the
 *  (unencoded) serial bytes for a datagram
 *
 *  @param config prlsc configuration
 *  @param datagram prlsc datagram being transmitted
 *  @return number of buffer bytes required, if a problem is found, errorCode is set and 0 is returned.
 */
uint16_t prlsc_bufferBytesRequired(prlsc_config_t *config, prlsc_state_t *state, prlsc_datagram_t *datagram) {
    uint16_t l_bytesToTransmit = 0u;

    if (datagram->serviceIndex >= config->serviceCount) {
        // Service does not exist
        state->errorCode = PRLSC_ERRORCODE_DATAGRAM_SERVICEINDEX_BOUNDS;
    } else if (datagram->length > config->datagramLengthMax) {
        // Datagram data length exceeds limits
        state->errorCode = PRLSC_ERRORCODE_DATAGRAM_TOO_LONG;
    } else {
        uint16_t l_totalFrameBytes;

        // Calculate: Number of frame bytes
        if (config->services[datagram->serviceIndex].stream == true) { // stream
            l_totalFrameBytes = datagram->length;
        } else { // diagnostics
            l_totalFrameBytes = datagram->length + sizeof(prlsc_checksum_t);
        }

        if ((config->services[datagram->serviceIndex].stream == true) && (l_totalFrameBytes > config->frameLengthMax)) {
            // Streaming services cannot accomodate multiple frames.
            state->errorCode = PRLSC_ERRORCODE_DATAGRAM_TOO_LONG;
        } else {
            uint16_t l_requiredFrames;

            // Calculate: Frames required
            if (config->services[datagram->serviceIndex].stream == true) { // stream
                // stream doesn't require an extra empty frame if datagram.length == {max frame length}
                // therefore, stream is always one frame (that's the whole point of a stream)
                l_requiredFrames = 1u;
            } else {
                // datagram needs an extra empty frame if datagram.length / {max frame length} = an integer
                l_requiredFrames = (l_totalFrameBytes + config->frameLengthMax) / config->frameLengthMax;
            }

            // Determine required bytes, by adding:
            //  - overhead per frame (4 bytes):
            //      - start byte
            //      - serviceCode [*1]
            //      - length [*1]
            //      - checksum [*1]
            //  - data bytes
            //
            //  *1 UNENCODED: buffered frames are not encoded because there will be no corruption at this point;
            //      everything after the start byte will be encoded when sending. As a precaution, the next byte
            //      after the end of a frame must be a start byte, if it isn't an errorcode is set which will
            //      signify a corrupt buffer.
            l_bytesToTransmit = l_totalFrameBytes + (l_requiredFrames * 4);
        }
    }

    return l_bytesToTransmit;
}


/*! @brief Transmit a datagram
 *
 *  Break up a datagram into frames ready to send over serial comms.
 *  when this function returns a non-zero, the memory allocated in datagram.data
 *  can be released; it's been buffered for transmission.
 *
 *  @param config prlsc configuration
 *  @param datagram datagram to be broken up and transmitted
 *  @return number of frames buffered for sending (> 0 signifies success)
 */
uint16_t prlsc_transmitDatagram(prlsc_config_t *config, prlsc_state_t *state, prlsc_datagram_t datagram) {
    // Local Variables
    prlsc_transmitterBuffer_t *l_state;
    prlsc_serviceConfig_t *l_serviceConfig;
    uint16_t l_requiredBytes, l_bufferBytesAvailalbe, l_frameCount = 0u;

    // Determine required bytes (error-state if 0 is returned; that's not possible)
    l_requiredBytes = prlsc_bufferBytesRequired(config, state, &datagram);
    if (l_requiredBytes == 0u) {
        return l_frameCount; // 0u
    }

    l_state = &(state->transmitterBuffer[datagram.serviceIndex]);
    l_serviceConfig = &(config->services[datagram.serviceIndex]);

    // Bytes available in buffer
    //  note: maximum bytes available in buffer is bufferSize - 1, this is because if bufferIdx == txIdx.
    //        that can mean 1 of 2 things: the buffer is empty, or the buffer is full... to avoid this
    //        conundrum, we make sure this can only mean the buffer is empty by never fully filling it.
    l_bufferBytesAvailalbe = (l_state->bufferSize - ((
        (l_state->bufferIdx >= l_state->txIdx) ? l_state->bufferIdx : (l_state->bufferIdx + l_state->bufferSize)
    ) - l_state->txIdx)) - 1;

    if (l_bufferBytesAvailalbe < l_requiredBytes) {
        // Not enough space in buffer, cannot continue
        // (note: this is not an error state, but a naturally occuring inconvenience)
    } else {
        // Everything checks out; populate buffer frames...

        // Frame Buffer
        uint8_t *l_frameBuffer; // Linear buffer for simplicity.
                                // This buffer's content is to be copied to the service's
                                // transmitter cirular-buffer before return.

        // Data indexes
        uint16_t l_dataChunkSize;
        uint16_t l_datagramDataIdx = 0u;
        uint16_t l_frameDataIndex;
        uint16_t l_thisFrameNetBytes;

        // Flags (
        bool l_checksumAppended = false;
        bool l_isLastFrame = false;

        l_frameBuffer = state->transmitter.frameBuffer;

        do { // loop per frame
            // --- Data
            l_dataChunkSize = datagram.length - l_datagramDataIdx;
            if (config->frameLengthMax < l_dataChunkSize) {
                l_dataChunkSize = config->frameLengthMax;
            }
            memcpy(&(PRLSC_FRAMEBUFFER_DATA(l_frameBuffer)[0]), &(datagram.data[l_datagramDataIdx]), l_dataChunkSize);
            l_datagramDataIdx += l_dataChunkSize;
            l_frameDataIndex = l_dataChunkSize;

            // datagram chcksum added to frame data (or not)
            if (config->services[datagram.serviceIndex].stream == true) {
                // Streamed frame
                l_isLastFrame = true;
            } else {
                // Diagnostics frame (add checksum when space available, last frame must not be full
                if (l_frameDataIndex < config->frameLengthMax) { // there's still space available in frame
                    // this can only occur if there's no more datagram data to push into the frame
                    if (l_datagramDataIdx >= datagram.length && l_checksumAppended != true) {
                        // datagram data has been depleated; all that's left is the checksum
                        PRLSC_FRAMEBUFFER_DATA(l_frameBuffer)[l_frameDataIndex] = datagram.checksum;
                        l_frameDataIndex++;
                        l_checksumAppended = true;
                    }
                    if (l_frameDataIndex < config->frameLengthMax) { // there's still space available in frame
                        l_isLastFrame = true;
                    }

                } // else: another frame must be transmitted (even if it contains no data)
            }

            // --- Frame header data
            // (depednent on data content, so done after data is copied)
            PRLSC_FRAMEBUFFER_STARTBYTE(l_frameBuffer) = config->frameByteStartFrame;
            PRLSC_FRAMEBUFFER_SERVICECODE(l_frameBuffer) = PRLSC_DATAGRAM_SERVICECODE(datagram);
            PRLSC_FRAMEBUFFER_LENGTH(l_frameBuffer) = l_frameDataIndex;
            // checksum must be done last, as it uses all other frame bytes (except the start byte)
            PRLSC_FRAMEBUFFER_CHECKSUM(l_frameBuffer) = prlsc_calcFrameBufferChecksum(config, l_frameBuffer);

            l_thisFrameNetBytes = PRLSC_FRAMEBUFFER_LENGTH(l_frameBuffer) + 4;

            // --- Copy linear buffer -> circular buffer
            prlsc_memcpy_flat2circular(
                &(l_state->buffer[l_state->bufferIdx]), // dest
                &(PRLSC_FRAMEBUFFER_STARTBYTE(l_frameBuffer)), // source
                l_thisFrameNetBytes, // length
                l_state->buffer, // destArr
                l_state->bufferSize // destSize
            );
            if (l_serviceConfig->stream == true && l_serviceConfig->onlyTxLatest == true) {
                // effectively empty the buffer (so that the newly added frame is all that's there)
                l_state->txIdx = l_state->bufferIdx;
            }
            l_state->bufferIdx = (l_state->bufferIdx + l_thisFrameNetBytes) % l_state->bufferSize;
            state->newTxDataFlag = true; // set consumable flag
            l_frameCount++;

        } while (l_isLastFrame != true);

    }
    return l_frameCount;
}


/*! @brief Determines if any service is ready to transmit, then prepares transmission state
 *
 *  This implements both the priority, and rate-limiting nature of this protocol.
 *    - Priority: services with a lower code are higher priority
 *    - Rate Limit: frames per service can only be sent every `rateLimit` units of time
 *          This is configured per servce, a value of 0 imposes no limiting
 *
 *  Transmission is initialised if a service frame is ready to be sent.
 *  As part of this process, the buffered frame is populated from the service's circular buffer,
 *  and the transmission index (txIndex) is moved forward.
 *  So, this function must not be called again before the prepared frame is physically transmitted.
 *
 *  @param config bus configuration, if `true` is returned, state->transmitter is set-up for byte transmission
 *  @param serviceCode if `true` is returned, serviceCode will be set to the service that is ready to transmit
 *                     if `false` is returned, and timeToRateLimitLifted != 0u, serviceCode will be set to the service who's rate-limit
 *                     will be lifted after timeToRateLimitLifted ticks (time) has passed.
 *  @param timeToRateLimitLifted if service is ready to send but is rate-limited,
 *                  this will be set to the remaining time until the service is no longer limited.
 *                  If no services are ready-but-limited, this value will be set to 0u (value is always affected)
 *                  Important: if function returns `true`, rate-limiting for latter service-codes will not be checked. Therefore
 *                  when this function returns `true`, this value may be innacruate.
 *  @return `true` if a service was found ready to transmit (`false` otherwise), state->transmitter state will be initialised
 */
bool prlsc_prepareServiceTransmission(prlsc_config_t *config, prlsc_state_t *state, prlsc_serviceIndex_t *serviceIndex, prlsc_time_t *timeToRateLimitLifted) {
    // --- Local Variables
    prlsc_serviceIndex_t l_curServiceIndex;
    prlsc_transmitterBuffer_t l_curServiceTxBuffer;
    bool l_setupCurService = false;
    // Timing
    prlsc_time_t l_curTime = config->callbackGetTime();
    prlsc_time_t l_timeSinceLastFrame;
    prlsc_time_t l_curServiceRateLimit;

    *timeToRateLimitLifted = 0u;

    // --- Loop through each service (from highest priority to lowest)
    // loop is broken if service is found ready to transmit
    for (l_curServiceIndex=0u; l_curServiceIndex<config->serviceCount; l_curServiceIndex++) {
        // Does service buffer (there's something to send)
        l_curServiceTxBuffer = state->transmitterBuffer[l_curServiceIndex];
        if (l_curServiceTxBuffer.txIdx != l_curServiceTxBuffer.bufferIdx) {
            // This service's buffer has something to transmit
            l_curServiceRateLimit = config->services[l_curServiceIndex].rateLimit;
            if (l_curServiceRateLimit > 0u) {
                l_timeSinceLastFrame = prlsc_timeDiff(
                    state->lastTransmitted[l_curServiceIndex],
                    l_curTime
                );
                if (l_timeSinceLastFrame >= l_curServiceRateLimit) {
                    // Service has stuff to send, and it's not limited
                    *serviceIndex = l_curServiceIndex;
                    l_setupCurService = true;
                    break;
                } else {
                    // Service is rate-limited
                    // determine how much time until rate-limit is lifted.
                    // push back smallest value to referenced parameter so caller can do something smart with it.
                    prlsc_time_t l_tempTime = l_curServiceRateLimit - l_timeSinceLastFrame;
                    if (*timeToRateLimitLifted == 0u || l_tempTime < *timeToRateLimitLifted) {
                        *timeToRateLimitLifted = l_tempTime;
                        *serviceIndex = l_curServiceIndex;
                    }
                }
            } else {
                // Service has stuff to send, and it has no rate limiter
                *serviceIndex = l_curServiceIndex;
                l_setupCurService = true;
                break;
            }
        }
    }

    if (l_setupCurService) {
        // --- Initialise transmitter state
        prlsc_transmitterState_t *l_txState = &(state->transmitter);
        prlsc_transmitterBuffer_t *l_txBuffer = &(state->transmitterBuffer[*serviceIndex]);

        // copy from circular buffer
        uint16_t l_frameLength = l_txBuffer->buffer[(l_txBuffer->txIdx + 2u) % l_txBuffer->bufferSize] + 4u;
        prlsc_memcpy_circular2flat(
            &(l_txState->transmitBuffer[0]), &(l_txBuffer->buffer[l_txBuffer->txIdx]),
            l_frameLength, l_txBuffer->buffer, l_txBuffer->bufferSize
        );

        l_txState->transmitLength = l_frameLength;
        l_txState->transmitServiceIndex = *serviceIndex;
        l_txState->state = PRLSC_TXBYTESTATE_START;
        l_txState->bufferIndex = 0u;

        // --- Buffer is consumed, increment transmission index
        l_txBuffer->txIdx = (l_txBuffer->txIdx + l_frameLength) % l_txBuffer->bufferSize;

        return true;
    }

    // No services have anything to send (or are currently rate-limited)
    return false;
}


/*! @brief Transmit Byte
 *
 *  Transmit the next byte of the current frame.
 *
 *  @param config bus configuration
 *  @return `true` if there's more to send, `false` if the last byte has been sent
 */
bool prlsc_txByte(prlsc_config_t *config, prlsc_state_t *state) {
    // Local Variables
    prlsc_transmitterState_t *l_state = &(state->transmitter);
    bool l_transmitByte = false;
    bool l_moreToSend = true;
    uint8_t l_byte;

    // State machine
    // cases ordered from most common, to least (for efficiency of execution)
    switch (l_state->state) {
        case PRLSC_TXBYTESTATE_NORMAL_BYTE:
            {
                l_byte = l_state->transmitBuffer[l_state->bufferIndex];
                l_transmitByte = true;
                // encode this byte?
                if (l_byte == config->frameByteStartFrame || l_byte == config->frameByteEsc) {
                    l_byte = config->frameByteEsc;
                    l_state->state = PRLSC_TXBYTESTATE_ESCAPED_BYTE;
                } else {
                    l_state->bufferIndex++;
                    // after index is incremented...
                    if (l_state->bufferIndex >= l_state->transmitLength) {
                        // reached end of tx buffer, flip switch to do nothing, and return false
                        l_state->state = PRLSC_TXBYTESTATE_DO_NOTHING;
                        l_moreToSend = false;
                    }
                }
            } break;
        case PRLSC_TXBYTESTATE_START:
            {
                l_byte = l_state->transmitBuffer[l_state->bufferIndex];
                l_transmitByte = true;
                l_state->bufferIndex++;
                // start of frame, set the time
                state->lastTransmitted[l_state->transmitServiceIndex] = config->callbackGetTime();
                l_state->state = PRLSC_TXBYTESTATE_NORMAL_BYTE;
            } break;
        case PRLSC_TXBYTESTATE_ESCAPED_BYTE:
            {
                l_byte = l_state->transmitBuffer[l_state->bufferIndex];
                if (l_byte == config->frameByteStartFrame) {
                    l_byte = config->frameByteEscStart;
                } else if (l_byte == config->frameByteEsc) {
                    l_byte = config->frameByteEscEsc;
                } else {
                    // l_byte doesn't match that found in state: PRLSC_TXBYTESTATE_NORMAL_BYTE;
                    // transmitBuffer content has changed since state machine was last called, or something
                    // much more horrible has happened.
                    // Needless to say: this code should never be executed.
                    state->errorCode = PRLSC_ERRORCODE_TXFRAME_BAD_ESC;
                    // beyond setting this code, this error isn't handled.
                }
                l_transmitByte = true;
                l_state->bufferIndex++;
                // after index is incremented...
                if (l_state->bufferIndex >= l_state->transmitLength) {
                    // reached end of tx buffer, flip switch to do nothing, and return false
                    l_state->state = PRLSC_TXBYTESTATE_DO_NOTHING;
                    l_moreToSend = false;
                } else {
                    l_state->state = PRLSC_TXBYTESTATE_NORMAL_BYTE;
                }
            } break;
        case PRLSC_TXBYTESTATE_DO_NOTHING:
        default:
            // ideally this code is never called
            l_moreToSend = false;
            break;
    }

    if (l_transmitByte) {
        // transmit byte
        config->callbackSendByte(l_byte);
    }
    return l_moreToSend;
}
