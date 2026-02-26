"""Global video processor and background task reference (avoids circular imports)."""

# Set from main after creating VideoProcessor
video_processor = None
frame_processing_task = None


def set_video_processor(vp):
    global video_processor
    video_processor = vp


def set_frame_processing_task(task):
    global frame_processing_task
    frame_processing_task = task
