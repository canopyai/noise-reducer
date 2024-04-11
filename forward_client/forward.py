import asyncio
import websockets
import io
import wave
import numpy as np

async def handle_client(websocket, path):
    # Prepare a buffer to accumulate received audio data
    processed_audio = io.BytesIO()

    try:
        # Handle incoming messages from the client
        async for message in websocket:
            # Accumulate received audio data
            processed_audio.write(message)
            response = f"Server received {len(message)} bytes of data."
            print(response)
            await websocket.send(response)

    except websockets.exceptions.ConnectionClosed as e:
        # Log the reason for the connection closure
        print(f"Connection closed: {e.code} - {e.reason}")

    finally:
        # Check if there's any received audio data before writing to a WAV file
        if processed_audio.getbuffer().nbytes > 0:
            write_audio_to_wav(processed_audio.getvalue())
            print("Cleaned audio written to 'cleaned_output.wav'.")
        else:
            print("No audio data received.")

def write_audio_to_wav(audio_bytes):
    # Audio parameters for the WAV file
    sample_rate = 24000
    channels = 1
    sampwidth = 2  # 2 bytes for 16 bits

    # Convert bytes back to numpy array (adjust dtype according to actual data)
    audio_array = np.frombuffer(audio_bytes, dtype=np.int16)
    # Ensure the array is shaped as a series of mono samples
    audio_array = audio_array.reshape(-1, channels)

    with wave.open("cleaned_output.wav", "wb") as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(sampwidth)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(audio_array.tobytes())



if __name__ == "__main__":
    start_server = websockets.serve(handle_client, "localhost", 8082)
    asyncio.get_event_loop().run_until_complete(start_server)
    asyncio.get_event_loop().run_forever()

