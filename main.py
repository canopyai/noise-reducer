import asyncio
import numpy as np
import torch
import io
import websockets
import argparse
import time
import json
import base64

from packages.demucs import DemucsStreamer
from packages.pretrained import get_model

buff = io.BytesIO()
altered_audio = io.BytesIO()
device = 'cpu'  # Use 'cuda' for GPU

args = argparse.Namespace(dns64=True, model_path=None, num_frames=1, num_threads=None, out=1)
model = get_model(args).to(device)
model.eval()
streamer = DemucsStreamer(model, num_frames=args.num_frames)


async def audio_processor(websocket):
    global buff

    first = True
    start = time.time()
    try:
        async for packet in websocket:

            json_message = json.loads(packet)
            data = json_message["data"]

            if data == "done":
                altered_audio.close()
                print("Finished processing audio")
                await websocket.send("EOT")
                break

            data = base64.b64decode(data)
            
            buff.write(data)

            length = streamer.total_length if first else streamer.stride
            first = False

            if buff.tell() >= length * 2 * 2:  # Check if buffer has enough data
                buff.seek(0)
                frame_bytes = buff.read(length * 2 * 2)
                frame = np.frombuffer(frame_bytes, dtype=np.int16).reshape(-1, 2).copy()
                frame = torch.from_numpy(frame).float() / 32768.0  # Convert to float and scale

                frame = frame.to(device).mean(dim=1)  # Take the mean across channels if needed
                s = time.time()
                with torch.no_grad():
                    out = streamer.feed(frame.unsqueeze(0))[0]
                    out = 0.99 * torch.tanh(out) 
                    out = out[:, None].repeat(1, 2)
                    scaled_output = (out * 32768).to(torch.int16)
                    out.clamp_(-1, 1)
                    output_bytes = scaled_output.cpu().numpy().astype(np.int16).tobytes()
                    altered_audio.write(output_bytes)
                    print("time taken to process audio: ", time.time()-s)
                    await websocket.send(output_bytes)

                # Handle overflow in buff
                overflow_bytes = buff.read()
                buff = io.BytesIO()
                buff.write(overflow_bytes)
            else:
                await websocket.send("received")

    except websockets.exceptions.ConnectionClosed:
        print("Connection closed")
    
    print("Time taken:", time.time() - start)

if __name__ == "__main__":
    start_server = websockets.serve(audio_processor, "localhost", 8081)
    asyncio.get_event_loop().run_until_complete(start_server)
    asyncio.get_event_loop().run_forever()
    
