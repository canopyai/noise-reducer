import asyncio
import websockets
from pydub import AudioSegment
import time
import io
import json
import base64

processed_audio = io.BytesIO()

async def stream_audio(file_path, server_uri, output_file_path):
    audio = AudioSegment.from_file(file_path)

    sample_width = audio.sample_width
    frame_rate = audio.frame_rate
    channels = audio.channels

    print(f"sample_width: {sample_width}, frame_rate: {frame_rate}, channels: {channels}")

    chunk_length_ms = 20

    num_chunks = len(audio) // chunk_length_ms

    async with websockets.connect(server_uri) as websocket:
        for i in range(num_chunks):
            start_ms = i * chunk_length_ms
            end_ms = start_ms + chunk_length_ms
            chunk = audio[start_ms:end_ms]

            raw_data = chunk.raw_data

            s = time.time()
            await websocket.send(raw_data)
            response = await websocket.recv()

            if response != "received":
                processed_audio.write(response)
                print(f"received response for chunk {i} in {time.time() - s} seconds")

        print("sending done")
        # await websocket.send(json.dumps({"index": "done", "data": "done"}))
        processed_audio.seek(0)
        output_audio = AudioSegment.from_raw(processed_audio, sample_width=2, frame_rate=frame_rate/2, channels=2)
        output_audio.export(output_file_path, format="wav")
        print("done")


if __name__ == "__main__":
    file_path = "audio.wav"
    server_uri = "ws://localhost:8081"
    output_file_path = "socket_processed_combined.wav"

    asyncio.get_event_loop().run_until_complete(stream_audio(file_path, server_uri, output_file_path))