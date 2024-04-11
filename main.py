import asyncio
import numpy as np
import torch
import io
import websockets
import argparse
import time

# Assuming the presence of these modules in your project
from packages.demucs import DemucsStreamer
from packages.pretrained import get_model

# Initialize model and device
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
args = argparse.Namespace(dns64=True, model_path=None, num_frames=1, num_threads=None, out=1)
model = get_model(args).to(device)
model.eval()
streamer = DemucsStreamer(model, num_frames=args.num_frames)
server_uri = "ws://34.141.221.82:8080"

async def listen_to_fsocket(fsocket):
    try:
        async for message in fsocket:
            print("Received from fsocket:", message)
    except websockets.exceptions.ConnectionClosed:
        print("fsocket connection closed")
    except Exception as e:
        print(f"Error listening to fsocket: {e}")

async def audio_processor(websocket, path):
    processed_audio_data = io.BytesIO()

    async with websockets.connect(server_uri) as fsocket:
        print("Connected to fsocket")
        # Start listening to fsocket in the background
        fsocket_listener_task = asyncio.create_task(listen_to_fsocket(fsocket))

        buff = io.BytesIO()
        first = True

        try:
            async for packet in websocket:
                if packet[:4].decode('utf-8') == "RIFF":
                    packet = packet[44:]

                buff.write(packet)

                length = streamer.total_length if first else streamer.stride
                first = False

                while buff.tell() >= length * 2 * 2:
                    buff.seek(0)
                    frame_bytes = buff.read(length * 2 * 2)
                    frame = np.frombuffer(frame_bytes, dtype=np.int16).reshape(-1, 2).copy()
                    frame = torch.from_numpy(frame).float() / 32768.0

                    frame = frame.to(device).mean(dim=1)
                    with torch.no_grad():
                        out = streamer.feed(frame.unsqueeze(0))[0]
                        out = 0.99 * torch.tanh(out)
                        out = out[:, None].repeat(1, 2)
                        scaled_output = (out * 32768).to(torch.int16)
                        out.clamp_(-1, 1)
                        output_bytes = scaled_output.cpu().numpy().astype(np.int16).tobytes()
                        
                        await fsocket.send(output_bytes)
                        processed_audio_data.write(output_bytes)

                    overflow_bytes = buff.read()
                    buff = io.BytesIO()
                    buff.write(overflow_bytes)

        except websockets.exceptions.ConnectionClosed:
            print("Connection closed with the client.")
        except Exception as e:
            print(f"An error occurred: {e}")
        finally:
            # Ensure the listener task is cancelled if we're done processing
            fsocket_listener_task.cancel()

if __name__ == "__main__":
    start_server = websockets.serve(audio_processor, "0.0.0.0", 8080)
    asyncio.get_event_loop().run_until_complete(start_server)
    asyncio.get_event_loop().run_forever()
