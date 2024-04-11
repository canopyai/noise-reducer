import asyncio
import numpy as np
import torch
import io
import websockets
import argparse
import time
import wave

from packages.demucs import DemucsStreamer
from packages.pretrained import get_model

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
args = argparse.Namespace(dns64=True, model_path=None, num_frames=1, num_threads=None, out=1)
model = get_model(args).to(device)
model.eval()
streamer = DemucsStreamer(model, num_frames=args.num_frames)
server_uri = "ws://34.141.221.82:8080"

async def audio_processor(websocket):
    processed_audio_data = io.BytesIO()  # Buffer for storing processed audio data
    
    async with websockets.connect(server_uri) as fsocket:
        print("Connected to fsocket")
        buff = io.BytesIO()
        first = True
        start = time.time()
        try:
            async for packet in websocket:
                # Directly process each packet
                header = packet[:4].decode('utf-8')
                if header == "RIFF":
                    packet = packet[44:]

                buff.write(packet)

                length = streamer.total_length if first else streamer.stride
                first = False

                while buff.tell() >= length * 2 * 2:  # Check if buffer has enough data
                    buff.seek(0)
                    frame_bytes = buff.read(length * 2 * 2)
                    frame = np.frombuffer(frame_bytes, dtype=np.int16).reshape(-1, 2).copy()
                    frame = torch.from_numpy(frame).float() / 32768.0  # Convert to float

                    frame = frame.to(device).mean(dim=1)  # Process frame
                    with torch.no_grad():
                        out = streamer.feed(frame.unsqueeze(0))[0]
                        out = 0.99 * torch.tanh(out)
                        out = out[:, None].repeat(1, 2)  # Duplicate channel if necessary
                        scaled_output = (out * 32768).to(torch.int16)
                        out.clamp_(-1, 1)
                        output_bytes = scaled_output.cpu().numpy().astype(np.int16).tobytes()
                        await fsocket.send(output_bytes)
                        processed_audio_data.write(output_bytes)  # Write processed audio to buffer

                    # Prepare buffer for next data
                    overflow_bytes = buff.read()
                    buff = io.BytesIO()
                    buff.write(overflow_bytes)

        except websockets.exceptions.ConnectionClosed:
            print("Connection closed")
        
        # After all processing, save the processed audio to a WAV file
        # processed_audio_data.seek(0)
        # with wave.open("processed_audio.wav", "wb") as processed_wav_file:
        #     processed_wav_file.setnchannels(1)  # Assuming mono output
        #     processed_wav_file.setsampwidth(2)  # 16-bit samples
        #     processed_wav_file.setframerate(24000)  # Sample rate
        #     processed_wav_file.writeframes(processed_audio_data.read())

        #     #close the fsocket connection
        #     await fsocket.close()
        
        # print("Processed audio saved. Time taken:", time.time() - start)

if __name__ == "__main__":
    start_server = websockets.serve(audio_processor, "localhost", 8081)
    asyncio.get_event_loop().run_until_complete(start_server)
    asyncio.get_event_loop().run_forever()
