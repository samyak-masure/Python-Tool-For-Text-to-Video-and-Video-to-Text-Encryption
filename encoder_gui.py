import tkinter as tk
from tkinter import scrolledtext, filedialog, messagebox
import math
from PIL import Image, ImageTk
import os
import imageio
import glob
import threading
import time
import random

# --- Global Variables for GUI Elements and State ---
status_label = None
canvas = None
encode_button = None
play_button = None
stop_button = None

animation_running = False
video_playback_running = False
video_player_frames = []
current_video_frame_index = 0
video_player_fps = 10 # Default playback FPS, will be updated from encoding FPS
_tk_photo_image = None # Keep a reference to avoid PhotoImage garbage collection

# === Encoder Core Logic Functions (Steps 1-5) ===

def step1_get_text(text_widget):
    """Gets text from the Tkinter text widget."""
    original_text = text_widget.get("1.0", tk.END).strip()
    if not original_text:
        messagebox.showwarning("Input Error", "Please enter some text to encode.")
        return None
    update_status(f"Successfully got text (length: {len(original_text)}).")
    return original_text

def step2_convert_to_binary(original_text):
    """Converts text to binary and saves metadata (original binary length)."""
    if original_text is None: return None, None
    update_status("\n--- Step 2: Converting Text to Binary ---")
    try:
        byte_data = original_text.encode('utf-8')
        update_status(f"Text encoded into {len(byte_data)} bytes using UTF-8.")
    except Exception as e:
        update_status(f"Error encoding text to bytes: {e}")
        return None, None

    binary_string_list = []
    for byte in byte_data:
        binary_representation = format(byte, '08b')
        binary_string_list.append(binary_representation)
    binary_string = "".join(binary_string_list)

    update_status(f"Successfully converted text to a binary string.")
    update_status(f"Binary String (first 50 chars): {binary_string[:50]}...")
    update_status(f"Total length of binary string: {len(binary_string)} bits")

    original_binary_length = len(binary_string)
    metadata_filename = 'metadata.txt'
    try:
        with open(metadata_filename, 'w') as meta_file:
            meta_file.write(str(original_binary_length))
        update_status(f"Saved original binary length ({original_binary_length}) to {metadata_filename}")
    except Exception as e:
        update_status(f"Error saving metadata file: {e}")
    update_status("-----------------------------------------")
    return binary_string, original_binary_length

def step3_plan_visual_representation(binary_string):
    """Plans visual representation based on binary string length."""
    if binary_string is None: return None
    update_status("\n--- Step 3: Planning the Visual Representation ---")
    
    frame_width_cfg = 100
    frame_height_cfg = 100
    grid_size_cfg = 10
    bits_per_frame_cfg = grid_size_cfg * grid_size_cfg
    pixel_size_cfg = frame_width_cfg // grid_size_cfg

    if bits_per_frame_cfg > 0 and len(binary_string) > 0:
        num_frames_cfg = math.ceil(len(binary_string) / bits_per_frame_cfg)
    elif len(binary_string) == 0:
        num_frames_cfg = 0
        update_status("Warning: The binary string is empty. No frames will be generated.")
    else:
        num_frames_cfg = 0
        update_status("Error: bits_per_frame is zero. Cannot proceed.")

    update_status(f"Frame size: {frame_width_cfg}x{frame_height_cfg} pixels")
    update_status(f"Each frame will represent {bits_per_frame_cfg} bits.")
    update_status(f"Calculated number of frames needed: {num_frames_cfg}")
    update_status("-------------------------------------------------")
    
    plan = {
        "frame_width": frame_width_cfg, "frame_height": frame_height_cfg,
        "grid_size": grid_size_cfg, "bits_per_frame": bits_per_frame_cfg,
        "pixel_size": pixel_size_cfg, "num_frames": num_frames_cfg
    }
    return plan

def step4_generate_frames(binary_string, plan, root_window):
    """Generates image frames with placeholder animation."""
    global animation_running
    if binary_string is None or plan is None: return False
    if plan["num_frames"] == 0: return False

    update_status("\n--- Step 4: Generating Image Frames ---")
    output_frame_folder = 'output_frames'
    os.makedirs(output_frame_folder, exist_ok=True)
    update_status(f"Frames will be saved in folder: '{output_frame_folder}/'")

    black = 0
    white = 255
    background_color = 128
    
    frame_width = plan["frame_width"]
    frame_height = plan["frame_height"]
    bits_per_frame = plan["bits_per_frame"]
    grid_size = plan["grid_size"]
    pixel_size = plan["pixel_size"]
    num_frames = plan["num_frames"]

    animation_running = True
    # Ensure animate_placeholder_encoder is called in the main thread if it modifies GUI
    root_window.after(0, lambda: animate_placeholder_encoder(root_window))


    total_frames_generated = 0
    for i in range(num_frames):
        start_index = i * bits_per_frame
        end_index = start_index + bits_per_frame
        binary_chunk = binary_string[start_index:end_index]

        if len(binary_chunk) < bits_per_frame:
            padding_needed = bits_per_frame - len(binary_chunk)
            binary_chunk += '0' * padding_needed

        img_pil = Image.new('L', (frame_width, frame_height), color=background_color)
        pixels = img_pil.load()
        bit_index = 0
        for row_idx in range(grid_size):
            for col_idx in range(grid_size):
                if bit_index < len(binary_chunk):
                    bit = binary_chunk[bit_index]
                    color = black if bit == '0' else white
                    x_start, y_start = col_idx * pixel_size, row_idx * pixel_size
                    for x_px in range(x_start, x_start + pixel_size):
                        for y_px in range(y_start, y_start + pixel_size):
                            if x_px < frame_width and y_px < frame_height:
                                 pixels[x_px, y_px] = color
                bit_index += 1
        
        frame_filename = os.path.join(output_frame_folder, f'frame_{i:04d}.png')
        img_pil.save(frame_filename)
        total_frames_generated += 1

        if total_frames_generated % 20 == 0 or total_frames_generated == num_frames:
            # Update status from the main thread
            final_msg = f"Generated frame {total_frames_generated}/{num_frames}: {frame_filename}"
            root_window.after(0, lambda msg=final_msg: update_status(msg))
            # Giving GUI a chance to process events - use with caution for responsiveness
            # For truly long tasks, a queue between thread and GUI is better
            # root_window.update_idletasks() # This call from a thread can be problematic
            time.sleep(0.01) # Small sleep to yield processing

    animation_running = False 
    root_window.after(0, lambda: update_status("\nFrame generation complete."))
    root_window.after(0, lambda: update_status("-------------------------------------"))
    return True

def step5_compile_video(plan):
    """Compiles frames into video using imageio and returns video filename."""
    global video_player_fps
    if plan is None or plan["num_frames"] == 0: return None
    
    update_status("\n--- Step 5: Compiling Frames into Video (Using imageio - Simplest) ---")
    output_video_file = 'output_video_imageio.mp4'
    fps_cfg = 20 # FPS for encoding (e.g., for 30-sec video from 600 frames)
    video_player_fps = fps_cfg # Sync playback FPS with encoding FPS
    output_frame_folder = 'output_frames' 

    frame_pattern = os.path.join(output_frame_folder, 'frame_*.png')
    frame_files = glob.glob(frame_pattern)
    frame_files.sort()

    if not frame_files:
        update_status("Error: No frames found to compile video.")
        return None
    
    update_status(f"Found {len(frame_files)} frames to compile using imageio at {fps_cfg} FPS.")
    
    try:
        update_status(f"Initializing imageio writer for: {output_video_file}...")
        writer = imageio.get_writer(
            output_video_file, fps=fps_cfg, format='FFMPEG', mode='I'
        )
        update_status("Writer initialized. Writing frames...")
        frames_written_count = 0
        for frame_file in frame_files:
            try:
                image = imageio.imread(frame_file)
                writer.append_data(image)
                frames_written_count += 1
            except Exception as read_err:
                update_status(f"    -> ERROR reading/appending frame {frame_file}: {read_err}")
        
        writer.close()
        update_status("\nVideo compilation complete using imageio.")
        update_status(f"Total frames appended: {frames_written_count}/{len(frame_files)}")
        return output_video_file # Return the filename on success
    except Exception as e:
        update_status(f"\nAn error occurred during imageio video compilation: {e}")
        if "Cannot find executable" in str(e) or "No such file or directory" in str(e):
             update_status("  -> Error suggests FFmpeg not found. Run: `pip install imageio-ffmpeg`")
        return None

# --- GUI Specific Functions ---

def update_status(message):
    """Appends a message to the status label in the GUI."""
    if status_label:
        current_time = time.strftime("%H:%M:%S")
        status_label.config(state=tk.NORMAL)
        status_label.insert(tk.END, f"[{current_time}] {message}\n")
        status_label.see(tk.END)
        status_label.config(state=tk.DISABLED)

def animate_placeholder_encoder(root_window):
    """Simple placeholder animation for the encoder canvas."""
    global canvas, animation_running
    if not canvas: return # Canvas might not exist yet if called too early

    if not animation_running:
        canvas.delete("all")
        try: # Try to get canvas dimensions
            c_width = canvas.winfo_width()
            c_height = canvas.winfo_height()
            if c_width > 1 and c_height > 1: # Check if dimensions are valid
                 canvas.create_text(c_width//2, c_height//2, 
                                   text="Video Generation Complete", font=("Arial", 10), tags="placeholder_text")
            else: # Fallback if dimensions not ready
                 canvas.create_text(150, 150, text="Video Gen Complete", font=("Arial", 10), tags="placeholder_text")
        except tk.TclError: pass # Window might be closing
        return

    canvas.delete("all")
    canvas_width = canvas.winfo_width()
    canvas_height = canvas.winfo_height()
    if canvas_width <=1 or canvas_height <=1: # Dimensions not ready
        canvas_width, canvas_height = 300, 300 # Use defaults

    for _ in range(10):
        x1 = random.randint(0, canvas_width - 30 if canvas_width > 30 else 0)
        y1 = random.randint(0, canvas_height - 30 if canvas_height > 30 else 0)
        x2 = x1 + random.randint(5, 30)
        y2 = y1 + random.randint(5, 30)
        color_choices = ["#FF0000", "#00FF00", "#0000FF", "#FFFF00", "#FF00FF", "#00FFFF", "#555555", "#AAAAAA"]
        color = random.choice(color_choices)
        canvas.create_rectangle(x1, y1, x2, y2, fill=color, outline="")
    
    root_window.after(100, lambda: animate_placeholder_encoder(root_window))

# --- Video Playback Functions ---
_tk_photo_image = None # Keep a reference to avoid garbage collection

def play_next_video_frame(root_window):
    global video_playback_running, canvas, video_player_frames, current_video_frame_index, _tk_photo_image, video_player_fps

    if not video_playback_running or not video_player_frames or not canvas:
        root_window.after(0, stop_video_playback)
        return

    if current_video_frame_index < len(video_player_frames):
        frame_pil_original = video_player_frames[current_video_frame_index]
        
        canvas_width = canvas.winfo_width()
        canvas_height = canvas.winfo_height()

        # Fallback if canvas dimensions aren't ready (should be rare at this point)
        if canvas_width <= 1: canvas_width = 300 
        if canvas_height <= 1: canvas_height = 300

        # ===> RESIZE THE FRAME TO FIT THE CANVAS <===
        # Use PIL's resize method. Image.LANCZOS is a high-quality downsampling filter,
        # Image.NEAREST would give a pixelated look if upscaling,
        # Image.BILINEAR or Image.BICUBIC are good general-purpose resamplers.
        # For upscaling small images like ours, NEAREST will preserve the blocky look,
        # while BILINEAR/BICUBIC will try to smooth it. Let's try NEAREST for the pixelated effect.
        try:
            frame_pil_resized = frame_pil_original.resize((canvas_width, canvas_height), Image.Resampling.NEAREST)
        except Exception as e:
            print(f"Error resizing frame: {e}") # Should not happen with valid images
            frame_pil_resized = frame_pil_original # Fallback to original if resize fails

        # Convert PIL Image to Tkinter PhotoImage
        _tk_photo_image = ImageTk.PhotoImage(frame_pil_resized) 
        
        canvas.delete("all") 
        # Display the resized image at canvas origin (0,0)
        canvas.create_image(0, 0, anchor=tk.NW, image=_tk_photo_image)
        
        current_video_frame_index += 1
        
        delay_ms = int(1000 / video_player_fps) if video_player_fps > 0 else 100
        root_window.after(delay_ms, lambda: play_next_video_frame(root_window))
    else:
        root_window.after(0, lambda: update_status("Video playback finished."))
        root_window.after(0, stop_video_playback)

# Other playback functions (start_video_playback, stop_video_playback) and GUI setup remain the same

def start_video_playback(video_filename, root_window):
    global video_playback_running, video_player_frames, current_video_frame_index, animation_running
    global play_button, stop_button # Ensure access to button widgets

    if animation_running: 
        animation_running = False
        # Give animation a moment to stop, then clear canvas
        root_window.after(110, lambda: canvas.delete("all") if canvas else None)


    if not os.path.exists(video_filename):
        messagebox.showerror("Playback Error", f"Video file not found: {video_filename}")
        return

    try:
        update_status(f"Loading video for playback: {video_filename}")
        reader = imageio.get_reader(video_filename)
        video_player_frames.clear() # Clear previous frames
        for frame_data in reader:
            video_player_frames.append(Image.fromarray(frame_data))
        reader.close()
        
        if not video_player_frames:
            messagebox.showerror("Playback Error", "Video contains no frames or could not be read.")
            return

        update_status(f"Video loaded. Total frames: {len(video_player_frames)}. Playback FPS: {video_player_fps}")
        video_playback_running = True
        current_video_frame_index = 0
        if play_button: play_button.config(state=tk.DISABLED)
        if stop_button: stop_button.config(state=tk.NORMAL)
        # Start playback loop (ensure it's called from main thread)
        root_window.after(0, lambda: play_next_video_frame(root_window))

    except Exception as e:
        messagebox.showerror("Playback Error", f"Error loading or playing video: {e}")
        update_status(f"Error during video playback setup: {e}")
        root_window.after(0, stop_video_playback)


def stop_video_playback():
    """Stops video playback, resets state, and updates GUI elements."""
    global video_playback_running, canvas, play_button, stop_button

    video_playback_running = False

    if play_button: play_button.config(state=tk.NORMAL)
    if stop_button: stop_button.config(state=tk.DISABLED)

    if canvas:
        canvas.delete("all")
        try:
            c_width = canvas.winfo_width()
            c_height = canvas.winfo_height()
            if c_width > 1 and c_height > 1:
                 canvas.create_text(c_width//2, c_height//2, 
                                   text="Video Area\n(Playback Stopped or Ready)", 
                                   justify=tk.CENTER, font=("Arial", 10), tags="placeholder_text")
            else:
                 canvas.create_text(150, 150, text="Video Area\n(Stopped/Ready)", 
                                   justify=tk.CENTER, font=("Arial", 10), tags="placeholder_text")
        except tk.TclError: pass
            
    # update_status("Video playback stopped.") # Can be a bit noisy if called often

def run_encoding_process_threaded(text_widget, root_window):
    """Runs the full encoding process in a separate thread."""
    def target():
        global animation_running, encode_button, play_button, stop_button # Access globals
        
        # Ensure GUI updates happen in the main thread
        def gui_update(task, *args):
            root_window.after(0, lambda: task(*args))

        gui_update(lambda: encode_button.config(state=tk.DISABLED) if encode_button else None)
        gui_update(lambda: play_button.config(state=tk.DISABLED) if play_button else None)
        gui_update(lambda: stop_button.config(state=tk.DISABLED) if stop_button else None)
        
        gui_update(lambda: status_label.config(state=tk.NORMAL))
        gui_update(lambda: status_label.delete('1.0', tk.END))
        gui_update(lambda: status_label.config(state=tk.DISABLED))
        gui_update(stop_video_playback) # Stop any ongoing playback

        original_text = step1_get_text(text_widget) # This function already calls update_status
        if original_text is None:
            gui_update(lambda: encode_button.config(state=tk.NORMAL) if encode_button else None)
            return

        binary_string, _ = step2_convert_to_binary(original_text)
        if binary_string is None:
            gui_update(lambda: encode_button.config(state=tk.NORMAL) if encode_button else None)
            return

        plan = step3_plan_visual_representation(binary_string)
        if plan is None or plan["num_frames"] == 0:
            gui_update(lambda: encode_button.config(state=tk.NORMAL) if encode_button else None)
            return
            
        frames_generated = step4_generate_frames(binary_string, plan, root_window)

        if not frames_generated:
            gui_update(lambda: update_status("Frame generation failed or was skipped."))
            gui_update(lambda: encode_button.config(state=tk.NORMAL) if encode_button else None)
            return

        video_filename = step5_compile_video(plan) 
        if video_filename:
            success_msg = f"\nSUCCESS! Video '{video_filename}' and 'metadata.txt' created."
            gui_update(lambda: update_status(success_msg))
            gui_update(lambda: messagebox.showinfo("Success", f"Video encoding process complete!\nVideo saved as: {video_filename}"))
            gui_update(lambda: play_button.config(state=tk.NORMAL) if play_button else None)
        else:
            gui_update(lambda: update_status("\nVideo compilation failed."))
            gui_update(lambda: messagebox.showerror("Error", "Video compilation failed."))

        gui_update(lambda: encode_button.config(state=tk.NORMAL) if encode_button else None)

    thread = threading.Thread(target=target)
    thread.daemon = True 
    thread.start()

# --- Main GUI Setup ---
def main_encoder_gui():
    global status_label, canvas, encode_button, play_button, stop_button
    
    root = tk.Tk()
    root.title("Text-to-Video Encoder")
    root.geometry("700x800") 

    input_frame = tk.Frame(root, pady=10)
    input_frame.pack(fill=tk.X)
    tk.Label(input_frame, text="Enter Text to Encode:").pack(side=tk.LEFT, padx=5)
    
    text_entry = scrolledtext.ScrolledText(root, wrap=tk.WORD, width=80, height=10, font=("Arial", 10))
    text_entry.pack(pady=5, padx=10, fill=tk.X)
    text_entry.insert(tk.INSERT, "Hello world! This is a test of the text to video system with GUI playback.") 

    display_control_frame = tk.Frame(root)
    display_control_frame.pack(pady=10, fill=tk.X, anchor='n') 

    tk.Label(display_control_frame, text="Preview Area:").pack(anchor='nw', padx=10, side=tk.TOP)
    canvas_frame = tk.Frame(display_control_frame) 
    canvas_frame.pack(side=tk.LEFT, padx=10, pady=5, anchor='nw')
    canvas = tk.Canvas(canvas_frame, width=300, height=300, bg="lightgrey", relief=tk.SUNKEN, borderwidth=2)
    canvas.pack() 
    
    root.update_idletasks() 
    
    main_controls_frame = tk.Frame(display_control_frame) 
    main_controls_frame.pack(side=tk.LEFT, padx=20, fill=tk.Y, expand=False, anchor='n')
    
    encode_button = tk.Button(main_controls_frame, text="Encode and Generate Video", 
                              command=lambda: run_encoding_process_threaded(text_entry, root), 
                              font=("Arial", 12), bg="#4CAF50", fg="white", padx=10, pady=5)
    encode_button.pack(pady=10, fill=tk.X, anchor='n')

    playback_controls_subframe = tk.Frame(main_controls_frame)
    playback_controls_subframe.pack(pady=10, fill=tk.X, anchor='n')

    tk.Label(playback_controls_subframe, text="Playback:").pack(anchor='w')

    play_button = tk.Button(playback_controls_subframe, text="Play Video",
                            command=lambda: start_video_playback('output_video_imageio.mp4', root),
                            font=("Arial", 10), state=tk.DISABLED) 
    play_button.pack(side=tk.LEFT, padx=5, pady=5)

    stop_button = tk.Button(playback_controls_subframe, text="Stop Video",
                            command=stop_video_playback, # Directly call the function
                            font=("Arial", 10), state=tk.DISABLED) 
    stop_button.pack(side=tk.LEFT, padx=5, pady=5)
    
    tk.Label(root, text="Process Status:").pack(anchor='w', padx=10, pady=(10,0))
    status_label = scrolledtext.ScrolledText(root, wrap=tk.WORD, width=80, height=15, font=("Arial", 9), state=tk.DISABLED, relief=tk.SUNKEN, borderwidth=2)
    status_label.pack(pady=5, padx=10, fill=tk.BOTH, expand=True)

    root.update_idletasks()
    stop_video_playback() # Initialize canvas text and button states

    root.mainloop()

if __name__ == "__main__":
    main_encoder_gui()