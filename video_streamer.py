
import cv2
import threading
import time
import logging

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")

class VideoStreamer:
    """
    A class to manage video stream ingestion from RTSP/ONVIF sources,
    handling connection, frame reading, and basic error recovery.
    Uses a separate thread for non-blocking frame reading.
    """
    def __init__(self, source_url: str, name: str = "VideoStreamer"):
        self.source_url = source_url
        self.name = name
        self.cap = None
        self.grabbed = False
        self.frame = None
        self.running = False
        self.read_lock = threading.Lock()
        self.thread = None
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5
        self.reconnect_delay_seconds = 5

        logging.info(f"[{self.name}] Initializing video streamer for source: {self.source_url}")

    def start(self):
        """
        Starts the video stream by opening the capture and launching the reading thread.
        """
        if self.running:
            logging.warning(f"[{self.name}] Stream is already running.")
            return self

        self.running = True
        self._open_capture()
        if self.cap and self.cap.isOpened():
            self.thread = threading.Thread(target=self._update, name=self.name)
            self.thread.daemon = True
            self.thread.start()
            logging.info(f"[{self.name}] Video stream started successfully.")
        else:
            self.running = False
            logging.error(f"[{self.name}] Failed to start video stream: Could not open capture.")
        return self

    def _open_capture(self):
        """
        Attempts to open the video capture object.
        """
        if self.cap:
            self.cap.release()
        self.cap = cv2.VideoCapture(self.source_url)
        if not self.cap.isOpened():
            logging.error(f"[{self.name}] Failed to open video capture for {self.source_url}")
            self.grabbed = False
            self.frame = None
        else:
            logging.info(f"[{self.name}] Video capture opened successfully.")
            self.grabbed, self.frame = self.cap.read() # Read first frame immediately

    def _update(self):
        """
        Continuously reads frames from the video stream in a separate thread.
        Handles reconnection attempts.
        """
        while self.running:
            if not self.cap or not self.cap.isOpened():
                logging.warning(f"[{self.name}] Video capture lost. Attempting to reconnect...")
                self.reconnect_attempts = 0
                while self.running and self.reconnect_attempts < self.max_reconnect_attempts:
                    time.sleep(self.reconnect_delay_seconds)
                    self._open_capture()
                    if self.cap and self.cap.isOpened():
                        logging.info(f"[{self.name}] Reconnected to stream after {self.reconnect_attempts + 1} attempts.")
                        self.reconnect_attempts = 0
                        break
                    else:
                        self.reconnect_attempts += 1
                        logging.error(f"[{self.name}] Reconnection attempt {self.reconnect_attempts}/{self.max_reconnect_attempts} failed.")
                
                if self.reconnect_attempts >= self.max_reconnect_attempts:
                    logging.critical(f"[{self.name}] Max reconnection attempts reached. Stopping stream.")
                    self.stop()
                    break

            with self.read_lock:
                self.grabbed, self.frame = self.cap.read()

            if not self.grabbed:
                logging.warning(f"[{self.name}] Failed to grab frame. Stream might be broken. Attempting to re-open...")
                self._open_capture() # Attempt to re-open if frame grab fails
                if not self.grabbed and self.running: # If still not grabbed after re-open, log error
                    logging.error(f"[{self.name}] Still unable to grab frame after re-opening. This might be a persistent issue.")

            time.sleep(0.001) # Small delay to prevent busy-waiting

    def read(self):
        """
        Returns the latest frame and a boolean indicating if it was successfully grabbed.
        """
        with self.read_lock:
            return self.grabbed, self.frame.copy() if self.frame is not None else None

    def stop(self):
        """
        Stops the video stream and releases the capture object.
        """
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5) # Wait for the thread to finish
            if self.thread.is_alive():
                logging.warning(f"[{self.name}] Thread did not terminate gracefully.")
        if self.cap:
            self.cap.release()
            logging.info(f"[{self.name}] Video stream stopped and capture released.")

    def __enter__(self):
        return self.start()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

# Example Usage (for testing purposes)
if __name__ == "__main__":
    # Use a dummy video file for testing if a real RTSP stream is not available
    # You can replace this with a real RTSP URL like "rtsp://user:password@ip:port/stream"
    # For local testing, you can use a video file like "sample.mp4"
    # If you don't have a video file, you can create a dummy one with OpenCV or ffmpeg.
    # For this example, we'll simulate a non-existent stream to test reconnection logic.
    
    # To test with a real video file (e.g., in the sandbox, upload a video first):
    # video_source = "sample.mp4"
    
    # To test with a non-existent stream (will trigger reconnection attempts):
    video_source = "rtsp://invalid.stream.url/live/ch0"

    print(f"Testing VideoStreamer with source: {video_source}")

    streamer = VideoStreamer(video_source, name="TestStream")
    streamer.start()

    try:
        start_time = time.time()
        while time.time() - start_time < 30: # Run for 30 seconds
            grabbed, frame = streamer.read()
            if grabbed and frame is not None:
                # Process frame here (e.g., display, analyze)
                # For this example, we just print a message
                # print(f"[{streamer.name}] Frame grabbed successfully. Shape: {frame.shape}")
                # If you have a display, you can uncomment these lines:
                # cv2.imshow(streamer.name, frame)
                # if cv2.waitKey(1) & 0xFF == ord("q"):
                #     break
                pass # Do nothing with the frame in headless mode
            else:
                logging.warning(f"[{streamer.name}] No frame grabbed.")
            time.sleep(0.1) # Simulate some processing time

    except KeyboardInterrupt:
        logging.info(f"[{streamer.name}] Test interrupted by user.")
    finally:
        streamer.stop()
        # cv2.destroyAllWindows() # Not needed in headless environment
        print(f"[{streamer.name}] Test finished.")

