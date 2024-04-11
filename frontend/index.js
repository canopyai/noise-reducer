document.getElementById('start').addEventListener('click', startRecording);

async function startRecording() {
    // Set the WebSocket route
    const route = 'ws://localhost:8081';

    // Create a new WebSocket connection
    const socket = new WebSocket(route);

    // Request access to the user's microphone
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

    // Configure the audio recorder
    let recorder = new RecordRTC(stream, {
        type: 'audio',
        mimeType: 'audio/wav',
        recorderType: RecordRTC.StereoAudioRecorder,
        timeSlice: 250,
        desiredSampRate: 16000,
        numberOfAudioChannels: 1,
        ondataavailable: async (blob) => {
            if (socket && socket.readyState === WebSocket.OPEN) {
                const arrayBuffer = await blob.arrayBuffer();
                // Send the audio data as an ArrayBuffer
                socket.send(arrayBuffer);
            }
        }
    });

    // Start recording
    recorder.startRecording();

    // Listen for messages from the server
    socket.onmessage = function(event) {
        // Print the received message to the console
        console.log("Message from server:", event.data);
    };

    // Optional: Listen for errors
    socket.onerror = function(event) {
        console.error("WebSocket error:", event);
    };
}
