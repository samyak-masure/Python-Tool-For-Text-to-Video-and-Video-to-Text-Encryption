import tkinter as tk
from tkinter import scrolledtext, filedialog, messagebox, font as tkFont
import math
from PIL import Image, ImageTk
import os
import imageio # For playing the input video
import cv2     # For extracting frames and resizing
import glob
import numpy as np
import threading
import time
import random # Can be used for a placeholder animation on canvas if needed
import tempfile # Added for temporary directory
import shutil   # Added for removing the temporary directory

# --- Global Variables for GUI and State ---
status_label_decoder = None
canvas_decoder = None
decoded_text_widget = None
select_video_button = None
select_metadata_button = None
decode_button_decoder = None

# Playback variables for the input video
video_playback_running_decoder = False
video_player_frames_decoder = []
current_video_frame_index_decoder = 0
video_player_fps_decoder = 10 # Default, will be read from video if possible
_tk_photo_image_decoder = None

input_video_path_selected = ""
metadata_path_selected = ""

# --- Decoder Core Logic Functions (Steps 8, 9, 10 from your original decoder.py) ---

# Modified to accept output_frame_folder argument
def step8_extract_and_resize_frames(video_path, root_window, output_frame_folder):
    global canvas_decoder # To potentially display frames
    update_status_decoder("--- Step 8: Extracting AND RESIZING Frames ---")
    
    extracted_frame_folder = output_frame_folder # Use the provided temporary folder path
    TARGET_WIDTH = 100
    TARGET_HEIGHT = 100
    # os.makedirs(extracted_frame_folder, exist_ok=True) # Not needed, tempfile.mkdtemp creates the directory
    update_status_decoder(f"Resized frames will be saved to temporary folder: '{extracted_frame_folder}/'")

    video_capture = cv2.VideoCapture(video_path)
    if not video_capture.isOpened():
        update_status_decoder(f"Error: Could not open video file: {video_path}")
        return False, 0

    actual_frame_count = 0
    processed_frame_count = 0
    success = True
    update_status_decoder("Starting frame extraction and resizing loop...")

    while success:
        success, frame_original = video_capture.read()
        if success:
            actual_frame_count +=1
            try:
                frame_resized = cv2.resize(frame_original, (TARGET_WIDTH, TARGET_HEIGHT), interpolation=cv2.INTER_AREA)
                frame_filename = os.path.join(extracted_frame_folder, f'frame_{processed_frame_count:04d}.png')
                cv2.imwrite(frame_filename, frame_resized)
                processed_frame_count += 1

                if processed_frame_count % 50 == 0:
                     final_msg = f"Extracted & Resized: {processed_frame_count} frames..."
                     root_window.after(0, lambda msg=final_msg: update_status_decoder(msg))
                     time.sleep(0.01)
            except Exception as resize_err:
                update_status_decoder(f"  ERROR resizing/saving frame {actual_frame_count}: {resize_err}")
    
    video_capture.release()
    update_status_decoder(f"\nFrame extraction/resizing complete. Processed: {processed_frame_count} frames.")
    return True, processed_frame_count

# Modified to accept frames_input_folder argument
def step9_decode_frames_to_binary(num_extracted_frames, root_window, frames_input_folder):
    update_status_decoder("\n--- Step 9: Decoding Frames to Binary ---")
    if num_extracted_frames == 0:
        update_status_decoder("No frames were extracted, skipping binary decoding.")
        return None

    frame_width_cfg = 100
    frame_height_cfg = 100
    grid_size_cfg = 10
    pixel_size_cfg = frame_width_cfg // grid_size_cfg
    threshold_cfg = 128

    extracted_frame_folder = frames_input_folder # Use the provided temporary folder path
    extracted_frame_pattern = os.path.join(extracted_frame_folder, 'frame_*.png')
    extracted_frame_files = glob.glob(extracted_frame_pattern)
    extracted_frame_files.sort()

    reconstructed_binary_string = ""
    if not extracted_frame_files:
        update_status_decoder(f"Error: No frames found in '{extracted_frame_folder}'. Check permissions or extraction step.")
        return None
    
    update_status_decoder(f"Found {len(extracted_frame_files)} frames to decode from temp. Using threshold: {threshold_cfg}")

    for i, frame_file in enumerate(extracted_frame_files):
        try:
            img = Image.open(frame_file).convert('L')
            if img.width != frame_width_cfg or img.height != frame_height_cfg:
                update_status_decoder(f"  WARNING: Frame {frame_file} incorrect dimensions {img.size}. Skipping.")
                continue
            
            bits_this_frame = ""
            for row_idx in range(grid_size_cfg):
                for col_idx in range(grid_size_cfg):
                    x_start = col_idx * pixel_size_cfg
                    y_start = row_idx * pixel_size_cfg
                    box = (x_start, y_start, x_start + pixel_size_cfg, y_start + pixel_size_cfg)
                    bit_region = img.crop(box)
                    pixel_values = np.array(bit_region)
                    average_intensity = np.mean(pixel_values)
                    determined_bit = '1' if average_intensity > threshold_cfg else '0'
                    bits_this_frame += determined_bit
            reconstructed_binary_string += bits_this_frame
            if (i + 1) % 50 == 0 or (i + 1) == len(extracted_frame_files):
                final_msg = f"  Decoded frame {i+1}/{len(extracted_frame_files)} into binary..."
                root_window.after(0, lambda msg=final_msg: update_status_decoder(msg))
                time.sleep(0.01)
        except Exception as e:
            update_status_decoder(f"  ERROR processing frame {frame_file}: {e}")
    
    update_status_decoder(f"\nReconstructed Raw Binary Length: {len(reconstructed_binary_string)} bits")
    
    global metadata_path_selected
    final_binary_string = ""
    if not metadata_path_selected or not os.path.exists(metadata_path_selected):
        update_status_decoder(f"Error: Metadata file not selected or not found at '{metadata_path_selected}'. Cannot truncate.")
        return reconstructed_binary_string
        
    try:
        with open(metadata_path_selected, 'r') as meta_file:
            original_length = int(meta_file.read().strip())
        update_status_decoder(f"Read original length from metadata: {original_length} bits")
        if len(reconstructed_binary_string) >= original_length:
            final_binary_string = reconstructed_binary_string[:original_length]
            update_status_decoder(f"Truncated binary string to {len(final_binary_string)} bits.")
        else:
            update_status_decoder(f"Warning: Reconstructed length < expected. Using full string.")
            final_binary_string = reconstructed_binary_string
    except Exception as e:
        update_status_decoder(f"Error reading metadata: {e}. Using raw binary string.")
        return reconstructed_binary_string

    return final_binary_string


def step10_convert_to_text_and_display(final_binary_string, text_widget_output, root_window):
    global decoded_text_widget 
    update_status_decoder("\n--- Step 10: Converting Binary to Text & Displaying ---")
    if not final_binary_string:
        update_status_decoder("Error: Final binary string is empty.")
        return

    if len(final_binary_string) % 8 != 0:
        update_status_decoder(f"Warning: Final binary length ({len(final_binary_string)}) not multiple of 8.")
    num_bytes_to_process = len(final_binary_string) // 8
    
    byte_list = []
    for i in range(num_bytes_to_process):
        byte_chunk = final_binary_string[i*8 : (i+1)*8]
        try:
            byte_value = int(byte_chunk, 2)
            byte_list.append(byte_value)
        except ValueError:
            update_status_decoder(f"Error converting chunk '{byte_chunk}'. Replacing with 0.")
            byte_list.append(0)
            
    reconstructed_byte_data = bytes(byte_list)
    update_status_decoder(f"Reconstructed {len(reconstructed_byte_data)} bytes.")

    try:
        decoded_text_widget.config(state=tk.NORMAL, font=("Courier New", 14)) 
        decoded_text_widget.delete('1.0', tk.END) 
        
        temp_decoded_text = ""
        decoded_chunk_size = 10 
        
        current_byte_index = 0
        while current_byte_index < len(reconstructed_byte_data):
            decoded_char = ''
            # Try decoding 1 to 4 bytes for UTF-8
            for num_bytes_to_try in range(1, 5):
                if current_byte_index + num_bytes_to_try > len(reconstructed_byte_data):
                    break # Not enough bytes left
                bytes_segment = reconstructed_byte_data[current_byte_index : current_byte_index + num_bytes_to_try]
                try:
                    decoded_char = bytes_segment.decode('utf-8', errors='strict')
                    # Successfully decoded a character
                    temp_decoded_text += decoded_char
                    decoded_text_widget.insert(tk.END, decoded_char)
                    current_byte_index += num_bytes_to_try # Move index by number of bytes consumed
                    
                    if len(temp_decoded_text) % decoded_chunk_size == 0:
                        decoded_text_widget.see(tk.END)
                        root_window.update_idletasks()
                        time.sleep(0.005)
                    break # Exit inner loop (num_bytes_to_try)
                except UnicodeDecodeError:
                    if num_bytes_to_try == 4: # Max bytes tried, still failed
                        # Handle as an error or replacement
                        replacement_char = '�'
                        temp_decoded_text += replacement_char
                        decoded_text_widget.insert(tk.END, replacement_char)
                        current_byte_index += 1 # Skip one problematic byte
                        decoded_text_widget.see(tk.END)
                        root_window.update_idletasks()
                        time.sleep(0.005)
                        break # Exit inner loop
                    # else, continue to try with more bytes
            if not decoded_char and current_byte_index < len(reconstructed_byte_data): 
                # This case should ideally not be hit if the logic above is correct for all scenarios
                # but as a fallback, if no char was decoded and we haven't finished
                replacement_char = '?' # Fallback, should be rare
                temp_decoded_text += replacement_char
                decoded_text_widget.insert(tk.END, replacement_char)
                current_byte_index += 1 
                decoded_text_widget.see(tk.END)
                root_window.update_idletasks()
                time.sleep(0.005)


        decoded_text_widget.see(tk.END) # Ensure last part is visible
        root_window.update_idletasks()

        update_status_decoder("Successfully decoded and displayed text.")
        decoded_output_filename = 'decoded_text_from_gui.txt'
        with open(decoded_output_filename, 'w', encoding='utf-8') as f_out:
            f_out.write(temp_decoded_text)
        update_status_decoder(f"Decoded text also saved to '{decoded_output_filename}'")

    except Exception as e:
        update_status_decoder(f"Error during text decoding/display: {e}")
        decoded_text_widget.insert(tk.END, f"\n\n[DECODING ERROR: {e}]")
    finally:
        pass


# --- GUI Specific Functions ---
def update_status_decoder(message):
    if status_label_decoder:
        current_time = time.strftime("%H:%M:%S")
        status_label_decoder.config(state=tk.NORMAL)
        status_label_decoder.insert(tk.END, f"[{current_time}] {message}\n")
        status_label_decoder.see(tk.END)
        status_label_decoder.config(state=tk.DISABLED)

def select_video_file():
    global input_video_path_selected, video_player_frames_decoder
    filename = filedialog.askopenfilename(
        title="Select Video File",
        filetypes=(("MP4 files", "*.mp4"), ("AVI files", "*.avi"), ("All files", "*.*"))
    )
    if filename:
        input_video_path_selected = filename
        update_status_decoder(f"Video file selected: {filename}")
        try:
            reader = imageio.get_reader(input_video_path_selected)
            video_player_frames_decoder.clear()
            for frame_data in reader:
                video_player_frames_decoder.append(Image.fromarray(frame_data))
            reader.close()
            if video_player_frames_decoder:
                 update_status_decoder(f"Video preview loaded ({len(video_player_frames_decoder)} frames).")
                 if decode_button_decoder: decode_button_decoder.config(state=tk.NORMAL if metadata_path_selected else tk.DISABLED)
                 start_video_playback_decoder(root_window_decoder)
            else:
                update_status_decoder("Could not load frames from selected video for preview.")
        except Exception as e:
            update_status_decoder(f"Error loading video preview: {e}")


def select_metadata_file():
    global metadata_path_selected
    filename = filedialog.askopenfilename(
        title="Select Metadata File",
        filetypes=(("Text files", "*.txt"), ("All files", "*.*"))
    )
    if filename:
        metadata_path_selected = filename
        update_status_decoder(f"Metadata file selected: {filename}")
        if decode_button_decoder: decode_button_decoder.config(state=tk.NORMAL if input_video_path_selected else tk.DISABLED)

# --- Video Playback Functions for Decoder ---
def play_next_video_frame_decoder(root_window):
    global video_playback_running_decoder, canvas_decoder, video_player_frames_decoder 
    global current_video_frame_index_decoder, _tk_photo_image_decoder, video_player_fps_decoder

    if not video_playback_running_decoder or not video_player_frames_decoder or not canvas_decoder:
        root_window.after_idle(stop_video_playback_decoder) # Use after_idle for safety
        return

    if current_video_frame_index_decoder < len(video_player_frames_decoder):
        frame_pil_original = video_player_frames_decoder[current_video_frame_index_decoder]
        canvas_width = canvas_decoder.winfo_width()
        canvas_height = canvas_decoder.winfo_height()
        if canvas_width <= 1: canvas_width = 300
        if canvas_height <= 1: canvas_height = 300
        
        try:
            frame_pil_resized = frame_pil_original.resize((canvas_width, canvas_height), Image.Resampling.LANCZOS) # Changed to LANCZOS for better quality
            _tk_photo_image_decoder = ImageTk.PhotoImage(frame_pil_resized)
            canvas_decoder.delete("all")
            canvas_decoder.create_image(0, 0, anchor=tk.NW, image=_tk_photo_image_decoder)
        except Exception as e:
            pass 
        
        current_video_frame_index_decoder += 1
        delay_ms = int(1000 / video_player_fps_decoder) if video_player_fps_decoder > 0 else 100
        root_window.after(delay_ms, lambda: play_next_video_frame_decoder(root_window))
    else: 
        current_video_frame_index_decoder = 0 
        root_window.after(0, lambda: play_next_video_frame_decoder(root_window))

def start_video_playback_decoder(root_window):
    global video_playback_running_decoder, current_video_frame_index_decoder
    if not video_player_frames_decoder:
        update_status_decoder("No video frames loaded to play.")
        return
    video_playback_running_decoder = True
    current_video_frame_index_decoder = 0
    play_next_video_frame_decoder(root_window) # Direct call to start immediately

def stop_video_playback_decoder():
    global video_playback_running_decoder, canvas_decoder
    video_playback_running_decoder = False
    if canvas_decoder:
        canvas_decoder.delete("all")
        try:
            # Check if canvas is valid before getting dimensions
            if canvas_decoder.winfo_exists():
                c_width = canvas_decoder.winfo_width()
                c_height = canvas_decoder.winfo_height()
                if c_width > 1 and c_height > 1:
                    canvas_decoder.create_text(c_width//2, c_height//2, text="Video Preview Area", 
                                      justify=tk.CENTER, font=("Arial", 10))
                else: # Fallback if dimensions are not yet set
                    canvas_decoder.create_text(150, 150, text="Video Preview Area", justify=tk.CENTER, font=("Arial", 10))
        except tk.TclError: pass # Canvas might not exist if window is closing


# --- Main Decoding Process Function (Threaded) ---
# Modified to use temporary directory for frames
def run_decoding_process_threaded(root_window):
    global input_video_path_selected, metadata_path_selected, decode_button_decoder, decoded_text_widget

    def gui_update(task, *args):
        root_window.after(0, lambda: task(*args))

    def target():
        gui_update(lambda: decode_button_decoder.config(state=tk.DISABLED))
        gui_update(lambda: select_video_button.config(state=tk.DISABLED))
        gui_update(lambda: select_metadata_button.config(state=tk.DISABLED))

        gui_update(lambda: status_label_decoder.config(state=tk.NORMAL))
        gui_update(lambda: status_label_decoder.delete('1.0', tk.END))
        gui_update(lambda: status_label_decoder.config(state=tk.DISABLED))
        
        gui_update(lambda: decoded_text_widget.config(state=tk.NORMAL))
        gui_update(lambda: decoded_text_widget.delete('1.0', tk.END))
        gui_update(lambda: decoded_text_widget.config(state=tk.DISABLED))

        if not input_video_path_selected or not os.path.exists(input_video_path_selected):
            gui_update(lambda: update_status_decoder("Error: Input video file not selected or not found."))
            # Buttons will be re-enabled in finally block
            return
        if not metadata_path_selected or not os.path.exists(metadata_path_selected):
            gui_update(lambda: update_status_decoder("Error: Metadata file not selected or not found."))
            # Allow proceeding, step9 will warn about truncation. Buttons re-enabled in finally.
            # return # Do not return here, let it try, or enforce selection

        temp_frame_dir = None # To store the path of the temporary directory
        try:
            # Create a temporary directory for extracted frames
            temp_frame_dir = tempfile.mkdtemp(prefix="video_decoder_frames_")
            gui_update(lambda: update_status_decoder(f"Created temporary directory: {temp_frame_dir}"))

            # Step 8: Pass the temporary directory path
            extraction_success, num_frames = step8_extract_and_resize_frames(input_video_path_selected, root_window, temp_frame_dir)
            if not extraction_success:
                gui_update(lambda: update_status_decoder("Frame extraction failed. Stopping."))
                return # Exits target function, finally block will execute

            # Step 9: Pass the temporary directory path
            final_binary_string = step9_decode_frames_to_binary(num_frames, root_window, temp_frame_dir)
            if final_binary_string is None:
                gui_update(lambda: update_status_decoder("Binary decoding failed. Stopping."))
                return # Exits target function, finally block will execute

            # Step 10
            step10_convert_to_text_and_display(final_binary_string, decoded_text_widget, root_window)
            
            gui_update(lambda: update_status_decoder("\nDecoding process complete!"))
            gui_update(lambda: messagebox.showinfo("Success", "Decoding process complete! Check the text area and 'decoded_text_from_gui.txt'."))
        
        except Exception as e:
            # Log any other unexpected error during the process
            import traceback
            error_msg = f"An unexpected error occurred: {e}\n{traceback.format_exc()}"
            gui_update(lambda: update_status_decoder(error_msg))
            gui_update(lambda: messagebox.showerror("Error", f"An unexpected error occurred: {e}"))
            
        finally:
            # Clean up the temporary directory
            if temp_frame_dir and os.path.isdir(temp_frame_dir):
                try:
                    shutil.rmtree(temp_frame_dir)
                    gui_update(lambda: update_status_decoder(f"Successfully removed temporary directory: {temp_frame_dir}"))
                except Exception as e_cleanup:
                    gui_update(lambda: update_status_decoder(f"Error removing temporary directory {temp_frame_dir}: {e_cleanup}"))
            
            # Always re-enable buttons
            gui_update(lambda: decode_button_decoder.config(state=tk.NORMAL if input_video_path_selected and metadata_path_selected else tk.DISABLED))
            gui_update(lambda: select_video_button.config(state=tk.NORMAL))
            gui_update(lambda: select_metadata_button.config(state=tk.NORMAL))

    thread = threading.Thread(target=target)
    thread.daemon = True # Ensures thread exits when main program exits
    thread.start()

# --- Main GUI Setup for Decoder ---
root_window_decoder = None

def main_decoder_gui():
    global status_label_decoder, canvas_decoder, decoded_text_widget, root_window_decoder
    global select_video_button, select_metadata_button, decode_button_decoder

    root = tk.Tk()
    root_window_decoder = root 
    root.title("Video-to-Text Decoder")
    root.geometry("850x700")

    top_frame = tk.Frame(root, pady=10)
    top_frame.pack(fill=tk.X)

    select_video_button = tk.Button(top_frame, text="Select Video File (.mp4, .avi)", command=select_video_file, font=("Arial", 10))
    select_video_button.pack(side=tk.LEFT, padx=10, pady=5)

    select_metadata_button = tk.Button(top_frame, text="Select Metadata File (.txt)", command=select_metadata_file, font=("Arial", 10))
    select_metadata_button.pack(side=tk.LEFT, padx=5, pady=5)
    
    decode_button_decoder = tk.Button(top_frame, text="DECODE VIDEO", 
                                     command=lambda: run_decoding_process_threaded(root),
                                     font=("Arial", 12, "bold"), bg="#FF8C00", fg="white", padx=10, pady=5, state=tk.DISABLED)
    decode_button_decoder.pack(side=tk.LEFT, padx=10, pady=5)

    content_frame = tk.Frame(root)
    content_frame.pack(fill=tk.BOTH, expand=True, pady=5, padx=5)

    video_frame_container = tk.Frame(content_frame, bd=2, relief=tk.SUNKEN)
    video_frame_container.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
    tk.Label(video_frame_container, text="Video Preview:", font=("Arial", 10, "bold")).pack(anchor='nw')
    canvas_decoder = tk.Canvas(video_frame_container, bg="lightgrey")
    canvas_decoder.pack(fill=tk.BOTH, expand=True)
    
    # It's better to call this after the mainloop starts and canvas is surely visible
    # or ensure canvas dimensions are non-zero before drawing.
    # For simplicity, we'll call it once GUI is setup.
    root.after(100, stop_video_playback_decoder)


    text_frame_container = tk.Frame(content_frame, bd=2, relief=tk.SUNKEN)
    text_frame_container.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5)
    tk.Label(text_frame_container, text="Decoded Text:", font=("Arial", 10, "bold")).pack(anchor='nw')
    decoded_text_widget = scrolledtext.ScrolledText(text_frame_container, wrap=tk.WORD, 
                                                    font=("Arial", 10), state=tk.DISABLED)
    decoded_text_widget.pack(fill=tk.BOTH, expand=True)

    status_frame_container = tk.Frame(root, height=150, bd=2, relief=tk.SUNKEN)
    status_frame_container.pack(fill=tk.X, pady=5, padx=5, side=tk.BOTTOM)
    tk.Label(status_frame_container, text="Process Status:", font=("Arial", 10, "bold")).pack(anchor='nw')
    status_label_decoder = scrolledtext.ScrolledText(status_frame_container, wrap=tk.WORD, 
                                                     font=("Arial", 9), state=tk.DISABLED, height=8)
    status_label_decoder.pack(fill=tk.BOTH, expand=True)

    root.mainloop()

if __name__ == "__main__":
    main_decoder_gui()