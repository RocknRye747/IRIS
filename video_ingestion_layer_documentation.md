# Lift Bot: Video Ingestion Layer Documentation

## 1. Introduction

The Video Ingestion Layer is a critical component of the Lift Bot platform, responsible for reliably acquiring video streams from various sources, primarily existing CCTV and security cameras utilizing RTSP (Real-Time Streaming Protocol) or ONVIF (Open Network Video Interface Forum) standards. This layer ensures a continuous and stable supply of video frames to the downstream pose estimation and ergonomic analysis modules, even in the presence of network interruptions or camera disconnections. Its design prioritizes robustness, efficiency, and ease of integration.

## 2. Design Principles

The design of the Video Ingestion Layer is guided by several core principles to ensure the Lift Bot system is resilient and performs optimally:

*   **Robustness:** The system must be able to handle intermittent network issues, camera disconnections, and other common streaming problems without crashing or requiring manual intervention. This is achieved through automatic reconnection attempts and comprehensive error logging.
*   **Efficiency:** Video processing is computationally intensive. To prevent bottlenecks, video frame acquisition must be non-blocking, allowing other system components to operate concurrently. This is accomplished using multi-threading.
*   **Modularity:** The video ingestion logic is encapsulated within a dedicated class, `VideoStreamer`, making it reusable, testable, and easily integrated into the larger Lift Bot architecture.
*   **Observability:** Clear logging provides insights into the status of each video stream, aiding in debugging and operational monitoring.

## 3. `VideoStreamer` Class Overview

The `VideoStreamer` class is the primary component of the Video Ingestion Layer. It is designed to abstract away the complexities of video stream management, providing a simple interface for starting, reading from, and stopping video sources.

### Class Attributes

| Attribute                  | Type    | Description                                                                                              | Default Value |
| :------------------------- | :------ | :------------------------------------------------------------------------------------------------------- | :------------ |
| `source_url`               | `str`   | The URL of the video stream (e.g., RTSP URL, local video file path).                                     | N/A           |
| `name`                     | `str`   | A human-readable name for the stream, used in logging.                                                   | "VideoStreamer" |
| `cap`                      | `cv2.VideoCapture` | The OpenCV VideoCapture object for the stream.                                                           | `None`        |
| `grabbed`                  | `bool`  | Indicates if the last frame was successfully grabbed.                                                    | `False`       |
| `frame`                    | `numpy.ndarray` | The most recently grabbed video frame.                                                                   | `None`        |
| `running`                  | `bool`  | Flag indicating if the stream is actively running.                                                       | `False`       |
| `read_lock`                | `threading.Lock` | A lock to ensure thread-safe access to `grabbed` and `frame`.                                            | N/A           |
| `thread`                   | `threading.Thread` | The separate thread responsible for continuously reading frames.                                         | `None`        |
| `reconnect_attempts`       | `int`   | Counter for current reconnection attempts.                                                               | `0`           |
| `max_reconnect_attempts`   | `int`   | Maximum number of reconnection attempts before stopping the stream.                                      | `5`           |
| `reconnect_delay_seconds`  | `int`   | Delay in seconds between reconnection attempts.                                                          | `5`           |

### Class Methods

*   **`__init__(self, source_url: str, name: str = "VideoStreamer")`**: Constructor to initialize the streamer with a source URL and an optional name.
*   **`start(self)`**: Initiates the video stream. It opens the `cv2.VideoCapture` object and starts a new thread (`_update`) to continuously read frames. Returns `self` for context manager compatibility.
*   **`_open_capture(self)`**: Internal method to attempt opening the `cv2.VideoCapture` object. Handles initial frame reading and updates `grabbed` and `frame`.
*   **`_update(self)`**: The target function for the reading thread. It continuously tries to read frames. If the stream is lost, it attempts to reconnect up to `max_reconnect_attempts` times with a `reconnect_delay_seconds` pause between attempts. It ensures thread-safe access to `grabbed` and `frame` using `read_lock`.
*   **`read(self)`**: Returns the latest `grabbed` status and a copy of the `frame`. This method is thread-safe.
*   **`stop(self)`**: Gracefully stops the video stream, signals the reading thread to terminate, waits for its completion, and releases the `cv2.VideoCapture` object.
*   **`__enter__(self)`**: Enables the use of `VideoStreamer` with Python's `with` statement, automatically calling `start()`.
*   **`__exit__(self, exc_type, exc_val, exc_tb)`**: Automatically calls `stop()` when exiting a `with` block, ensuring resources are properly released.

## 4. Error Handling and Reconnection

The `VideoStreamer` is designed for resilience in dynamic network environments. Key aspects of its error handling include:

*   **Automatic Reconnection:** If the video stream connection is lost (e.g., `cap.isOpened()` returns `False` or `cap.read()` fails to grab a frame), the `_update` thread automatically attempts to re-establish the connection. It tries up to `max_reconnect_attempts` times, pausing for `reconnect_delay_seconds` between each attempt.
*   **Graceful Shutdown:** If the maximum number of reconnection attempts is reached, the stream is gracefully stopped, and a critical error is logged, preventing indefinite blocking or resource consumption.
*   **Thread Safety:** A `threading.Lock` (`self.read_lock`) is used to protect access to the `grabbed` status and `frame` data, preventing race conditions between the reading thread and any other thread attempting to access the frame.
*   **Logging:** Detailed `logging.info`, `logging.warning`, and `logging.error` messages provide real-time feedback on the stream's status, connection attempts, and any encountered issues.

## 5. Usage

Using the `VideoStreamer` class is straightforward, especially with the `with` statement for proper resource management.

### Example: Initializing and Reading from a Stream

```python
import cv2
import time
from video_streamer import VideoStreamer

# Replace with your actual RTSP/ONVIF URL or video file path
# For testing reconnection, you can use an invalid URL.
video_source_url = "rtsp://your_camera_ip:port/stream" 
# video_source_url = "sample.mp4" # For a local video file

print(f"Attempting to stream from: {video_source_url}")

# Using the VideoStreamer with a 'with' statement ensures proper start/stop
with VideoStreamer(video_source_url, name="MyCameraFeed") as streamer:
    if not streamer.cap or not streamer.cap.isOpened():
        print(f"Failed to open stream from {video_source_url}. Check URL or camera status.")
    else:
        print("Streamer started. Reading frames...")
        start_time = time.time()
        while (time.time() - start_time) < 60: # Run for 60 seconds
            grabbed, frame = streamer.read()

            if grabbed and frame is not None:
                # Process the frame here
                # For example, pass it to the Lift Bot analyzer
                # lift_bot_analyzer.process_frame(frame)
                
                # In a headless environment, you would not display the frame.
                # For local debugging with a display, you could uncomment:
                # cv2.imshow("Live Feed", frame)
                # if cv2.waitKey(1) & 0xFF == ord("q"):
                #     break
                pass # Placeholder for actual frame processing
            else:
                print("No frame available. Stream might be temporarily down or ended.")
            
            time.sleep(0.03) # Simulate processing time, adjust as needed

print("Streamer stopped. Application finished.")
```

### Integration with `lift_bot_analyzer.py`

The `VideoStreamer` class is designed to seamlessly replace the `cv2.VideoCapture` object in `lift_bot_analyzer.py`. The `main` function of `lift_bot_analyzer.py` can be modified to accept a `video_source_url` and initialize `VideoStreamer` accordingly, passing frames to the pose estimation and tracking pipeline.

## 6. Best Practices Applied

*   **Coding Best Practices:**
    *   **Modularity and Encapsulation:** The `VideoStreamer` class encapsulates all logic related to video ingestion, keeping the codebase clean and maintainable.
    *   **Clear Naming Conventions:** Variables, methods, and classes are named descriptively to enhance readability.
    *   **Docstrings and Comments:** Comprehensive docstrings explain the purpose and usage of classes and methods, while inline comments clarify complex logic.
*   **Programming Best Practices:**
    *   **Concurrency with Threading:** Utilizing a separate thread for video capture prevents the main application from blocking, ensuring a responsive and efficient system. [1]
    *   **Resource Management:** The `__enter__` and `__exit__` methods (context manager protocol) ensure that video capture resources are always properly initialized and released, even if errors occur. [2]
    *   **Robust Error Handling:** Explicit reconnection logic and error logging make the system resilient to common streaming failures.
*   **Data Science Best Practices (Indirectly):**
    *   **Reliable Data Source:** A robust video ingestion layer is fundamental for providing a consistent and reliable stream of data (video frames) to the data science (pose estimation, ergonomic analysis) components. Without reliable input, the accuracy and effectiveness of the AI models would be compromised.

## 7. References

[1] Python `threading` module documentation: [https://docs.python.org/3/library/threading.html](https://docs.python.org/3/library/threading.html)
[2] Python `with` statement and context managers: [https://docs.python.org/3/reference/compound_stmts.html#the-with-statement](https://docs.python.org/3/reference/compound_stmts.html#the-with-statement)

