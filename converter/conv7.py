import os
import cv2
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image, ImageTk, ImageEnhance, ImageDraw, ImageFont
import threading
import numpy as np
import math

# --- Globals ---
video = None
video_path = None
frame_preview = None
threshold_val = 150
is_playing = False
zoom_factor = 1.0
zoom_offset_x = 0.5
zoom_offset_y = 0.5
pan_x, pan_y = 0, 0
drag_start = None
total_frames = 0
current_frame = 0
fps = 25

# Crop region (normalized 0-1)
crop_x1, crop_y1, crop_x2, crop_y2 = 0.0, 0.0, 1.0, 1.0

# Timeline trim
trim_start = 0
trim_end = 0

# Image adjustments
brightness_val = 1.0
contrast_val = 1.0
saturation_val = 1.0

# Output settings
output_width = 128
output_height = 64

# Export state
is_exporting = False

# Flag to prevent recursive slider updates
updating_sliders = False

# Video mode
current_mode = "Normal"

# Text overlay settings
text_overlay = ""
text_pos_x = 0.5
text_pos_y = 0.9
text_font_size = 10
text_rotation = 0
text_appear_frame = 0
text_disappear_frame = -1  # -1 means show until end

# --- Resolution Options ---
RESOLUTIONS = {
    "128x64 (Standard)": (128, 64, 8),
    "128x32 (Small)": (128, 32, 4),
}

# --- Video Modes ---
VIDEO_MODES = ["Normal", "Invert", "Dither", "Edge Detect", "High Contrast", "Posterize"]

# --- Color Scheme (Clean Dark Theme) ---
BG_DARK = "#1e1e1e"
BG_MEDIUM = "#2a2a2a"
BG_LIGHT = "#363636"
BG_BUTTON = "#404040"
TEXT_PRIMARY = "#e0e0e0"
TEXT_SECONDARY = "#808080"
ACCENT_BLUE = "#3794ff"
SLIDER_TROUGH = "#333333"

# --- Functions ---
def open_video():
    global video, video_path, total_frames, current_frame, fps, trim_start, trim_end, updating_sliders
    global text_appear_frame, text_disappear_frame
    video_path = filedialog.askopenfilename(filetypes=[("Video Files", "*.mp4;*.avi;*.mov;*.mkv;*.webm")])
    if not video_path:
        return
    video = cv2.VideoCapture(video_path)
    total_frames = int(video.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = video.get(cv2.CAP_PROP_FPS) or 25
    current_frame = 0
    trim_start = 0
    trim_end = total_frames - 1
    text_appear_frame = 0
    text_disappear_frame = total_frames - 1
    
    updating_sliders = True
    
    video_slider.config(to=max(1, total_frames - 1))
    trim_start_slider.config(to=max(1, total_frames - 1))
    trim_end_slider.config(to=max(1, total_frames - 1))
    text_appear_slider.config(to=max(1, total_frames - 1))
    text_disappear_slider.config(to=max(1, total_frames - 1))
    video_slider.set(0)
    trim_start_slider.set(0)
    trim_end_slider.set(total_frames - 1)
    text_appear_slider.set(0)
    text_disappear_slider.set(total_frames - 1)
    
    updating_sliders = False
    
    duration = total_frames / fps
    status_label.config(text=f"Loaded: {os.path.basename(video_path)}")
    info_label.config(text=f"{total_frames} frames | {duration:.1f}s | {fps:.0f} FPS")
    
    # Set default export path to video directory
    export_path_var.set(os.path.dirname(video_path))
    
    base_name = os.path.splitext(os.path.basename(video_path))[0]
    export_name_entry.delete(0, tk.END)
    export_name_entry.insert(0, base_name)
    
    update_trim_info()
    preview_frame()

def apply_video_mode(img, mode):
    """Apply video mode/theme to the image (PIL Image in L mode)"""
    arr = np.array(img)
    
    if mode == "Invert":
        arr = 255 - arr
    elif mode == "Dither":
        h, w = arr.shape
        arr = arr.astype(np.float32)
        for y in range(h - 1):
            for x in range(1, w - 1):
                old_pixel = arr[y, x]
                new_pixel = 255 if old_pixel > 127 else 0
                arr[y, x] = new_pixel
                error = old_pixel - new_pixel
                arr[y, x + 1] = np.clip(arr[y, x + 1] + error * 7 / 16, 0, 255)
                arr[y + 1, x - 1] = np.clip(arr[y + 1, x - 1] + error * 3 / 16, 0, 255)
                arr[y + 1, x] = np.clip(arr[y + 1, x] + error * 5 / 16, 0, 255)
                arr[y + 1, x + 1] = np.clip(arr[y + 1, x + 1] + error * 1 / 16, 0, 255)
        arr = arr.astype(np.uint8)
    elif mode == "Edge Detect":
        img_cv = arr.astype(np.uint8)
        edges = cv2.Canny(img_cv, 50, 150)
        arr = edges
    elif mode == "High Contrast":
        arr = np.clip((arr.astype(np.float32) - 128) * 2 + 128, 0, 255).astype(np.uint8)
    elif mode == "Posterize":
        levels = 4
        arr = (arr // (256 // levels)) * (256 // levels)
        arr = arr.astype(np.uint8)
    
    return Image.fromarray(arr)

def add_text_overlay(img, text, pos_x, pos_y, font_size, rotation, frame_idx, appear, disappear):
    """Add text overlay to PIL Image with position, rotation, and timing"""
    if not text:
        return img
    
    # Check if text should appear at this frame
    if frame_idx < appear or (disappear >= 0 and frame_idx > disappear):
        return img
    
    # Calculate animation fade (first 5 frames)
    alpha = 1.0
    fade_frames = 5
    if frame_idx - appear < fade_frames:
        alpha = (frame_idx - appear + 1) / fade_frames
    
    w, h = img.size
    
    # Work on a copy of the original image
    result = img.copy()
    draw = ImageDraw.Draw(result)
    
    try:
        font = ImageFont.truetype("arial.ttf", font_size)
    except:
        try:
            font = ImageFont.truetype("Arial.ttf", font_size)
        except:
            font = ImageFont.load_default()
    
    # Get text bounding box
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    
    # Calculate text position
    tx = int(pos_x * w) - text_w // 2
    ty = int(pos_y * h) - text_h // 2
    
    # Clamp to image bounds
    tx = max(0, min(w - text_w, tx))
    ty = max(0, min(h - text_h, ty))
    
    # If rotation is needed, create a rotated text image and paste it
    if rotation != 0:
        # Create a larger transparent layer for text
        txt_size = max(text_w, text_h) * 2 + 10
        txt_layer = Image.new("L", (txt_size, txt_size), 0)
        txt_draw = ImageDraw.Draw(txt_layer)
        
        # Draw text in center of layer
        txt_x = (txt_size - text_w) // 2
        txt_y = (txt_size - text_h) // 2
        
        # Draw outline (black)
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                if dx != 0 or dy != 0:
                    txt_draw.text((txt_x + dx, txt_y + dy), text, fill=0, font=font)
        
        # Draw text (white with alpha)
        txt_draw.text((txt_x, txt_y), text, fill=int(255 * alpha), font=font)
        
        # Rotate the text layer
        txt_layer = txt_layer.rotate(rotation, resample=Image.Resampling.BILINEAR, expand=False)
        
        # Calculate paste position (centered on target position)
        paste_x = int(pos_x * w) - txt_size // 2
        paste_y = int(pos_y * h) - txt_size // 2
        
        # Create mask from the rotated text
        txt_arr = np.array(txt_layer)
        result_arr = np.array(result)
        
        # Paste only where text pixels exist
        for py in range(txt_size):
            for px in range(txt_size):
                dest_x = paste_x + px
                dest_y = paste_y + py
                if 0 <= dest_x < w and 0 <= dest_y < h:
                    if txt_arr[py, px] > 10:
                        result_arr[dest_y, dest_x] = txt_arr[py, px]
        
        return Image.fromarray(result_arr)
    else:
        # No rotation - draw directly
        # Draw outline (black)
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                if dx != 0 or dy != 0:
                    draw.text((tx + dx, ty + dy), text, fill=0, font=font)
        
        # Draw text (white with alpha)
        draw.text((tx, ty), text, fill=int(255 * alpha), font=font)
        
        return result

def get_processed_frame(frame_idx, for_export=False):
    global video, threshold_val, zoom_factor, zoom_offset_x, zoom_offset_y
    global crop_x1, crop_y1, crop_x2, crop_y2
    global brightness_val, contrast_val, saturation_val, output_width, output_height
    global current_mode, text_overlay, text_pos_x, text_pos_y, text_font_size
    global text_rotation, text_appear_frame, text_disappear_frame
    
    if not video:
        return None
    
    video.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
    ret, frame = video.read()
    if not ret or frame is None:
        return None
    
    h, w = frame.shape[:2]
    
    # Apply crop first
    x1 = int(crop_x1 * w)
    y1 = int(crop_y1 * h)
    x2 = int(crop_x2 * w)
    y2 = int(crop_y2 * h)
    
    x1, x2 = max(0, min(x1, x2)), min(w, max(x1, x2))
    y1, y2 = max(0, min(y1, y2)), min(h, max(y1, y2))
    
    if x2 - x1 < 10 or y2 - y1 < 10:
        x1, y1, x2, y2 = 0, 0, w, h
    
    frame = frame[y1:y2, x1:x2]
    
    # Apply zoom with position offset
    if zoom_factor > 1.0:
        zh, zw = frame.shape[:2]
        new_w = int(zw / zoom_factor)
        new_h = int(zh / zoom_factor)
        
        max_offset_x = zw - new_w
        max_offset_y = zh - new_h
        zx1 = int(zoom_offset_x * max_offset_x)
        zy1 = int(zoom_offset_y * max_offset_y)
        zx2 = zx1 + new_w
        zy2 = zy1 + new_h
        
        zx1 = max(0, zx1)
        zy1 = max(0, zy1)
        zx2 = min(zw, zx2)
        zy2 = min(zh, zy2)
        
        frame = frame[zy1:zy2, zx1:zx2]
    
    # Convert to PIL for adjustments
    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    img = Image.fromarray(frame_rgb)
    
    if brightness_val != 1.0:
        enhancer = ImageEnhance.Brightness(img)
        img = enhancer.enhance(brightness_val)
    
    if contrast_val != 1.0:
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(contrast_val)
    
    if saturation_val != 1.0:
        enhancer = ImageEnhance.Color(img)
        img = enhancer.enhance(saturation_val)
    
    img = img.convert('L')
    img = img.resize((output_width, output_height), Image.Resampling.LANCZOS)
    
    # Apply video mode before threshold
    if current_mode not in ["Normal", "Dither"]:
        img = apply_video_mode(img, current_mode)
    
    arr = np.array(img)
    
    if current_mode == "Dither":
        img = apply_video_mode(Image.fromarray(arr), "Dither")
        arr = np.array(img)
        _, arr = cv2.threshold(arr, 127, 255, cv2.THRESH_BINARY)
    else:
        _, arr = cv2.threshold(arr, threshold_val, 255, cv2.THRESH_BINARY)
    
    if current_mode == "Invert":
        arr = 255 - arr
    
    # Add text overlay
    result_img = Image.fromarray(arr)
    result_img = add_text_overlay(
        result_img, text_overlay, text_pos_x, text_pos_y, 
        text_font_size, text_rotation, frame_idx,
        text_appear_frame, text_disappear_frame
    )
    
    return np.array(result_img)

def preview_frame():
    global video, pan_x, pan_y, current_frame, output_width, output_height, updating_sliders
    
    if not video or updating_sliders:
        return
    
    processed = get_processed_frame(current_frame, for_export=False)
    if processed is None:
        return
    
    img = Image.fromarray(processed)
    
    preview_scale = 4
    w, h = img.size
    img = img.resize((w * preview_scale, h * preview_scale), Image.Resampling.NEAREST)
    
    canvas_w = preview_canvas.winfo_width() or 540
    canvas_h = preview_canvas.winfo_height() or 280
    bg = Image.new("L", (canvas_w, canvas_h), 30)
    
    px = (canvas_w - img.size[0]) // 2 + pan_x
    py = (canvas_h - img.size[1]) // 2 + pan_y
    bg.paste(img, (px, py))
    
    img_tk = ImageTk.PhotoImage(bg)
    preview_canvas.delete("all")
    preview_canvas.create_image(0, 0, anchor="nw", image=img_tk)
    preview_canvas.image = img_tk
    
    if fps > 0:
        time_pos = current_frame / fps
        frame_info_label.config(text=f"Frame: {current_frame} | Time: {time_pos:.2f}s")

def export_dat():
    global video_path, is_exporting, trim_start, trim_end, output_width, output_height
    
    if not video_path:
        messagebox.showerror("Error", "No video loaded!")
        return
    
    if is_exporting:
        messagebox.showwarning("Warning", "Export already in progress!")
        return
    
    export_dir = export_path_var.get()
    export_name = export_name_entry.get().strip()
    
    if not export_name:
        export_name = "output"
    
    if not export_dir:
        export_dir = os.path.dirname(video_path) or os.getcwd()
    
    outfile = os.path.join(export_dir, export_name + ".dat")
    pages = output_height // 8
    
    def do_export():
        global is_exporting
        is_exporting = True
        
        root.after(0, lambda: export_btn.config(state="disabled"))
        root.after(0, lambda: progress_bar.configure(value=0))
        
        total_export_frames = trim_end - trim_start + 1
        fcount = 0
        
        try:
            with open(outfile, "wb") as f:
                for frame_idx in range(trim_start, trim_end + 1):
                    if not is_exporting:
                        break
                    
                    processed = get_processed_frame(frame_idx, for_export=True)
                    if processed is None:
                        continue
                    
                    ba = bytearray()
                    for page in range(pages):
                        for col in range(output_width):
                            byte = 0
                            bit = 1
                            for y in range(8):
                                row = page * 8 + y
                                if row < output_height and processed[row][col]:
                                    byte |= bit
                                bit <<= 1
                            ba.append(byte)
                    f.write(bytes(ba))
                    fcount += 1
                    
                    progress = (fcount / total_export_frames) * 100
                    root.after(0, lambda p=progress: progress_bar.configure(value=p))
                    root.after(0, lambda fc=fcount, tf=total_export_frames: 
                              export_status_label.config(text=f"Exporting: {fc}/{tf}"))
            
            root.after(0, lambda: status_label.config(text=f"Exported {fcount} frames"))
            root.after(0, lambda: messagebox.showinfo("Success", f"Exported {fcount} frames!\n\nSaved to:\n{outfile}"))
        
        except Exception as e:
            root.after(0, lambda: messagebox.showerror("Export Error", str(e)))
        
        finally:
            is_exporting = False
            root.after(0, lambda: export_btn.config(state="normal"))
            root.after(0, lambda: export_status_label.config(text=""))
            root.after(0, lambda: progress_bar.configure(value=0))
    
    thread = threading.Thread(target=do_export, daemon=True)
    thread.start()

def cancel_export():
    global is_exporting
    is_exporting = False

def browse_export_path():
    path = filedialog.askdirectory()
    if path:
        export_path_var.set(path)

def play_video():
    global is_playing
    if not video:
        return
    is_playing = True
    play_btn.config(text="Pause")
    update_video()

def stop_video():
    global is_playing
    is_playing = False
    play_btn.config(text="Play")

def toggle_play():
    if is_playing:
        stop_video()
    else:
        play_video()

def update_video():
    global is_playing, current_frame, trim_start, trim_end, updating_sliders
    if is_playing and video:
        current_frame += 1
        if current_frame > trim_end:
            current_frame = trim_start
        
        updating_sliders = True
        video_slider.set(current_frame)
        updating_sliders = False
        
        preview_frame()
        delay = int(1000 / fps) if fps > 0 else 40
        root.after(delay, update_video)

def set_threshold(val):
    global threshold_val, updating_sliders
    if updating_sliders:
        return
    threshold_val = int(float(val))
    threshold_value_label.config(text=str(threshold_val))
    preview_frame()

def set_brightness(val):
    global brightness_val, updating_sliders
    if updating_sliders:
        return
    brightness_val = float(val)
    brightness_value_label.config(text=f"{brightness_val:.2f}")
    preview_frame()

def set_contrast(val):
    global contrast_val, updating_sliders
    if updating_sliders:
        return
    contrast_val = float(val)
    contrast_value_label.config(text=f"{contrast_val:.2f}")
    preview_frame()

def set_saturation(val):
    global saturation_val, updating_sliders
    if updating_sliders:
        return
    saturation_val = float(val)
    saturation_value_label.config(text=f"{saturation_val:.2f}")
    preview_frame()

def zoom_in():
    global zoom_factor
    zoom_factor = min(zoom_factor + 0.25, 5.0)
    zoom_value_label.config(text=f"{zoom_factor:.2f}x")
    preview_frame()

def zoom_out():
    global zoom_factor
    zoom_factor = max(zoom_factor - 0.25, 1.0)
    zoom_value_label.config(text=f"{zoom_factor:.2f}x")
    preview_frame()

def reset_zoom():
    global zoom_factor, zoom_offset_x, zoom_offset_y, pan_x, pan_y
    zoom_factor = 1.0
    zoom_offset_x = 0.5
    zoom_offset_y = 0.5
    pan_x, pan_y = 0, 0
    zoom_value_label.config(text=f"{zoom_factor:.2f}x")
    zoom_pos_label.config(text="Center")
    preview_frame()

def move_zoom(dx, dy):
    global zoom_offset_x, zoom_offset_y
    zoom_offset_x = max(0.0, min(1.0, zoom_offset_x + dx))
    zoom_offset_y = max(0.0, min(1.0, zoom_offset_y + dy))
    update_zoom_pos_label()
    preview_frame()

def update_zoom_pos_label():
    global zoom_offset_x, zoom_offset_y
    h_pos = "L" if zoom_offset_x < 0.4 else ("R" if zoom_offset_x > 0.6 else "")
    v_pos = "T" if zoom_offset_y < 0.4 else ("B" if zoom_offset_y > 0.6 else "")
    
    if h_pos and v_pos:
        pos_text = f"{v_pos}{h_pos}"
    elif h_pos or v_pos:
        pos_text = h_pos or v_pos
    else:
        pos_text = "Center"
    
    zoom_pos_label.config(text=pos_text)

def start_pan(event):
    global drag_start
    drag_start = (event.x, event.y)

def do_pan(event):
    global drag_start, pan_x, pan_y
    if drag_start:
        dx = event.x - drag_start[0]
        dy = event.y - drag_start[1]
        pan_x += dx
        pan_y += dy
        drag_start = (event.x, event.y)
        preview_frame()

def stop_pan(event):
    global drag_start
    drag_start = None

def set_frame(val):
    global current_frame, updating_sliders
    if updating_sliders:
        return
    current_frame = int(float(val))
    preview_frame()

def set_trim_start(val):
    global trim_start, trim_end, updating_sliders
    if updating_sliders:
        return
    trim_start = int(float(val))
    if trim_start > trim_end:
        updating_sliders = True
        trim_end_slider.set(trim_start)
        trim_end = trim_start
        updating_sliders = False
    update_trim_info()

def set_trim_end(val):
    global trim_end, trim_start, updating_sliders
    if updating_sliders:
        return
    trim_end = int(float(val))
    if trim_end < trim_start:
        updating_sliders = True
        trim_start_slider.set(trim_end)
        trim_start = trim_end
        updating_sliders = False
    update_trim_info()

def update_trim_info():
    global trim_start, trim_end, fps
    if fps > 0:
        duration = (trim_end - trim_start + 1) / fps
        frames = trim_end - trim_start + 1
        trim_info_label.config(text=f"{frames} frames | {duration:.2f}s")

def set_trim_preset(seconds):
    global trim_start, trim_end, fps, current_frame, updating_sliders
    if not video:
        return
    frames = int(seconds * fps)
    trim_start = current_frame
    trim_end = min(current_frame + frames - 1, total_frames - 1)
    
    updating_sliders = True
    trim_start_slider.set(trim_start)
    trim_end_slider.set(trim_end)
    updating_sliders = False
    
    update_trim_info()

def go_to_trim_start():
    global current_frame, trim_start, updating_sliders
    current_frame = trim_start
    updating_sliders = True
    video_slider.set(current_frame)
    updating_sliders = False
    preview_frame()

def go_to_trim_end():
    global current_frame, trim_end, updating_sliders
    current_frame = trim_end
    updating_sliders = True
    video_slider.set(current_frame)
    updating_sliders = False
    preview_frame()

def update_crop_left(val):
    global crop_x1, updating_sliders
    if updating_sliders:
        return
    crop_x1 = float(val) / 100
    preview_frame()

def update_crop_right(val):
    global crop_x2, updating_sliders
    if updating_sliders:
        return
    crop_x2 = float(val) / 100
    preview_frame()

def update_crop_top(val):
    global crop_y1, updating_sliders
    if updating_sliders:
        return
    crop_y1 = float(val) / 100
    preview_frame()

def update_crop_bottom(val):
    global crop_y2, updating_sliders
    if updating_sliders:
        return
    crop_y2 = float(val) / 100
    preview_frame()

def reset_crop():
    global crop_x1, crop_y1, crop_x2, crop_y2, updating_sliders
    crop_x1, crop_y1, crop_x2, crop_y2 = 0.0, 0.0, 1.0, 1.0
    
    updating_sliders = True
    crop_left_slider.set(0)
    crop_right_slider.set(100)
    crop_top_slider.set(0)
    crop_bottom_slider.set(100)
    updating_sliders = False
    
    preview_frame()

def set_resolution(event=None):
    global output_width, output_height
    res = resolution_var.get()
    if res in RESOLUTIONS:
        output_width, output_height, _ = RESOLUTIONS[res]
        preview_frame()

def set_video_mode(event=None):
    global current_mode
    current_mode = mode_var.get()
    preview_frame()

def update_text_overlay(event=None):
    global text_overlay
    text_overlay = text_entry.get()
    preview_frame()

def set_text_pos_x(val):
    global text_pos_x, updating_sliders
    if updating_sliders:
        return
    text_pos_x = float(val) / 100
    text_x_value_label.config(text=f"{int(float(val))}%")
    preview_frame()

def set_text_pos_y(val):
    global text_pos_y, updating_sliders
    if updating_sliders:
        return
    text_pos_y = float(val) / 100
    text_y_value_label.config(text=f"{int(float(val))}%")
    preview_frame()

def set_text_size(val):
    global text_font_size, updating_sliders
    if updating_sliders:
        return
    text_font_size = int(float(val))
    text_size_value_label.config(text=str(text_font_size))
    preview_frame()

def set_text_rotation(val):
    global text_rotation, updating_sliders
    if updating_sliders:
        return
    text_rotation = int(float(val))
    text_rotation_value_label.config(text=f"{text_rotation}")
    preview_frame()

def set_text_appear(val):
    global text_appear_frame, updating_sliders
    if updating_sliders:
        return
    text_appear_frame = int(float(val))
    preview_frame()

def set_text_disappear(val):
    global text_disappear_frame, updating_sliders
    if updating_sliders:
        return
    text_disappear_frame = int(float(val))
    preview_frame()

def reset_adjustments():
    global brightness_val, contrast_val, saturation_val, threshold_val, updating_sliders
    brightness_val = 1.0
    contrast_val = 1.0
    saturation_val = 1.0
    threshold_val = 150
    
    updating_sliders = True
    brightness_slider.set(1.0)
    contrast_slider.set(1.0)
    saturation_slider.set(1.0)
    threshold_slider.set(150)
    updating_sliders = False
    
    brightness_value_label.config(text="1.00")
    contrast_value_label.config(text="1.00")
    saturation_value_label.config(text="1.00")
    threshold_value_label.config(text="150")
    
    preview_frame()

# --- GUI Setup ---
root = tk.Tk()
root.title("Video to .DAT Converter for OLED Display")
root.geometry("720x850")
root.configure(bg=BG_DARK)
root.minsize(650, 600)

# Style configuration
style = ttk.Style()
style.theme_use('clam')

# Configure styles - clean dark theme
style.configure(".", background=BG_DARK, foreground=TEXT_PRIMARY, font=("Segoe UI", 9))
style.configure("TFrame", background=BG_DARK)
style.configure("TLabel", background=BG_DARK, foreground=TEXT_PRIMARY)
style.configure("TButton", background=BG_BUTTON, foreground=TEXT_PRIMARY, borderwidth=0, padding=(10, 5))
style.map("TButton", background=[("active", BG_LIGHT), ("pressed", ACCENT_BLUE)])
style.configure("Small.TButton", padding=(6, 3), font=("Segoe UI", 8))
style.configure("TScale", background=BG_DARK, troughcolor=SLIDER_TROUGH, sliderthickness=12, sliderrelief="flat")
style.map("TScale", background=[("active", BG_LIGHT)])
style.configure("TCombobox", fieldbackground=BG_MEDIUM, background=BG_BUTTON, foreground=TEXT_PRIMARY, 
                arrowcolor=TEXT_SECONDARY, borderwidth=0)
style.map("TCombobox", fieldbackground=[("readonly", BG_MEDIUM)], selectbackground=[("readonly", BG_LIGHT)])
style.configure("Horizontal.TProgressbar", troughcolor=SLIDER_TROUGH, background=ACCENT_BLUE, borderwidth=0)
style.configure("TEntry", fieldbackground=BG_MEDIUM, foreground=TEXT_PRIMARY, insertcolor=TEXT_PRIMARY, borderwidth=0)
style.configure("TScrollbar", background=BG_MEDIUM, troughcolor=BG_DARK, borderwidth=0, arrowcolor=TEXT_SECONDARY)
style.map("TScrollbar", background=[("active", BG_LIGHT)])

# Combobox dropdown colors
root.option_add("*TCombobox*Listbox*Background", BG_MEDIUM)
root.option_add("*TCombobox*Listbox*Foreground", TEXT_PRIMARY)
root.option_add("*TCombobox*Listbox*selectBackground", BG_LIGHT)
root.option_add("*TCombobox*Listbox*selectForeground", TEXT_PRIMARY)

# === MAIN LAYOUT ===

# Top frame (FIXED - does not scroll)
top_frame = tk.Frame(root, bg=BG_DARK)
top_frame.pack(fill="x", padx=15, pady=10)

# Header
header_frame = tk.Frame(top_frame, bg=BG_DARK)
header_frame.pack(fill="x", pady=(0, 10))

title_label = tk.Label(header_frame, text="Video to OLED .DAT Converter", font=("Segoe UI", 13, "bold"), 
                       bg=BG_DARK, fg=ACCENT_BLUE)
title_label.pack(side="left")

# File controls
file_frame = tk.Frame(top_frame, bg=BG_DARK)
file_frame.pack(fill="x", pady=(0, 8))

open_btn = ttk.Button(file_frame, text="Open Video", command=open_video)
open_btn.pack(side="left", padx=(0, 10))

status_label = tk.Label(file_frame, text="No video loaded", font=("Segoe UI", 9), bg=BG_DARK, fg=TEXT_SECONDARY)
status_label.pack(side="left", padx=5)

info_label = tk.Label(file_frame, text="", font=("Segoe UI", 9), bg=BG_DARK, fg=ACCENT_BLUE)
info_label.pack(side="right", padx=5)

# Preview area
preview_container = tk.Frame(top_frame, bg=BG_MEDIUM)
preview_container.pack(fill="x")

preview_canvas = tk.Canvas(preview_container, width=540, height=270, bg="#1a1a1a", highlightthickness=0)
preview_canvas.pack(padx=3, pady=3, fill="x", expand=True)

preview_canvas.bind("<ButtonPress-1>", start_pan)
preview_canvas.bind("<B1-Motion>", do_pan)
preview_canvas.bind("<ButtonRelease-1>", stop_pan)

# Preview controls
preview_controls = tk.Frame(top_frame, bg=BG_DARK)
preview_controls.pack(fill="x", pady=(8, 0))

play_btn = ttk.Button(preview_controls, text="Play", command=toggle_play, width=7)
play_btn.pack(side="left", padx=(0, 10))

frame_info_label = tk.Label(preview_controls, text="Frame: 0 | Time: 0.00s", font=("Segoe UI", 9), 
                            bg=BG_DARK, fg=TEXT_PRIMARY)
frame_info_label.pack(side="right")

# Video slider
video_slider = ttk.Scale(top_frame, from_=0, to=100, orient="horizontal", command=set_frame)
video_slider.pack(fill="x", pady=(8, 0))

# === SCROLLABLE CONTROLS ===
controls_canvas = tk.Canvas(root, bg=BG_DARK, highlightthickness=0)
scrollbar = ttk.Scrollbar(root, orient="vertical", command=controls_canvas.yview)
scrollable_frame = tk.Frame(controls_canvas, bg=BG_DARK)

scrollable_frame.bind("<Configure>", lambda e: controls_canvas.configure(scrollregion=controls_canvas.bbox("all")))
controls_window = controls_canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")

def on_canvas_configure(event):
    controls_canvas.itemconfig(controls_window, width=event.width - 4)

controls_canvas.bind("<Configure>", on_canvas_configure)
controls_canvas.configure(yscrollcommand=scrollbar.set)

def on_mousewheel(event):
    controls_canvas.yview_scroll(int(-1*(event.delta/120)), "units")

def on_mousewheel_linux(event):
    if event.num == 4:
        controls_canvas.yview_scroll(-1, "units")
    elif event.num == 5:
        controls_canvas.yview_scroll(1, "units")

controls_canvas.bind_all("<MouseWheel>", on_mousewheel)
controls_canvas.bind_all("<Button-4>", on_mousewheel_linux)
controls_canvas.bind_all("<Button-5>", on_mousewheel_linux)

scrollbar.pack(side="right", fill="y")
controls_canvas.pack(side="left", fill="both", expand=True, padx=(15, 0), pady=(10, 15))

# Helper to create section headers
def create_section(parent, title):
    frame = tk.Frame(parent, bg=BG_DARK)
    frame.pack(fill="x", pady=(12, 6), padx=(0, 15))
    tk.Label(frame, text=title, font=("Segoe UI", 10, "bold"), bg=BG_DARK, fg=ACCENT_BLUE).pack(anchor="w")
    content = tk.Frame(frame, bg=BG_DARK)
    content.pack(fill="x", pady=(6, 0))
    return content

# === RESOLUTION & MODE ===
res_mode_section = create_section(scrollable_frame, "Output Settings")

res_row = tk.Frame(res_mode_section, bg=BG_DARK)
res_row.pack(fill="x", pady=2)

tk.Label(res_row, text="Resolution:", bg=BG_DARK, fg=TEXT_PRIMARY, width=10, anchor="w").pack(side="left")
resolution_var = tk.StringVar(value="128x64 (Standard)")
resolution_combo = ttk.Combobox(res_row, textvariable=resolution_var, values=list(RESOLUTIONS.keys()), state="readonly", width=16)
resolution_combo.pack(side="left", padx=(0, 20))
resolution_combo.bind("<<ComboboxSelected>>", set_resolution)

tk.Label(res_row, text="Mode:", bg=BG_DARK, fg=TEXT_PRIMARY, width=6, anchor="w").pack(side="left")
mode_var = tk.StringVar(value="Normal")
mode_combo = ttk.Combobox(res_row, textvariable=mode_var, values=VIDEO_MODES, state="readonly", width=14)
mode_combo.pack(side="left")
mode_combo.bind("<<ComboboxSelected>>", set_video_mode)

# === TEXT OVERLAY ===
text_section = create_section(scrollable_frame, "Text Overlay")

text_row1 = tk.Frame(text_section, bg=BG_DARK)
text_row1.pack(fill="x", pady=2)

tk.Label(text_row1, text="Text:", bg=BG_DARK, fg=TEXT_PRIMARY, width=10, anchor="w").pack(side="left")
text_entry = ttk.Entry(text_row1, width=40)
text_entry.pack(side="left", fill="x", expand=True)
text_entry.bind("<KeyRelease>", update_text_overlay)

# Text position X
text_row2 = tk.Frame(text_section, bg=BG_DARK)
text_row2.pack(fill="x", pady=2)

tk.Label(text_row2, text="Position X:", bg=BG_DARK, fg=TEXT_PRIMARY, width=10, anchor="w").pack(side="left")
text_x_slider = ttk.Scale(text_row2, from_=0, to=100, orient="horizontal", command=set_text_pos_x)
text_x_slider.pack(side="left", fill="x", expand=True, padx=(0, 5))
text_x_value_label = tk.Label(text_row2, text="50%", width=5, bg=BG_DARK, fg=TEXT_PRIMARY)
text_x_value_label.pack(side="left")

# Text position Y
text_row3 = tk.Frame(text_section, bg=BG_DARK)
text_row3.pack(fill="x", pady=2)

tk.Label(text_row3, text="Position Y:", bg=BG_DARK, fg=TEXT_PRIMARY, width=10, anchor="w").pack(side="left")
text_y_slider = ttk.Scale(text_row3, from_=0, to=100, orient="horizontal", command=set_text_pos_y)
text_y_slider.pack(side="left", fill="x", expand=True, padx=(0, 5))
text_y_value_label = tk.Label(text_row3, text="90%", width=5, bg=BG_DARK, fg=TEXT_PRIMARY)
text_y_value_label.pack(side="left")

# Font size and rotation
text_row4 = tk.Frame(text_section, bg=BG_DARK)
text_row4.pack(fill="x", pady=2)

tk.Label(text_row4, text="Size:", bg=BG_DARK, fg=TEXT_PRIMARY, width=10, anchor="w").pack(side="left")
text_size_slider = ttk.Scale(text_row4, from_=6, to=24, orient="horizontal", command=set_text_size)
text_size_slider.pack(side="left", fill="x", expand=True, padx=(0, 5))
text_size_value_label = tk.Label(text_row4, text="10", width=5, bg=BG_DARK, fg=TEXT_PRIMARY)
text_size_value_label.pack(side="left")

text_row5 = tk.Frame(text_section, bg=BG_DARK)
text_row5.pack(fill="x", pady=2)

tk.Label(text_row5, text="Rotation:", bg=BG_DARK, fg=TEXT_PRIMARY, width=10, anchor="w").pack(side="left")
text_rotation_slider = ttk.Scale(text_row5, from_=-180, to=180, orient="horizontal", command=set_text_rotation)
text_rotation_slider.pack(side="left", fill="x", expand=True, padx=(0, 5))
text_rotation_value_label = tk.Label(text_row5, text="0", width=5, bg=BG_DARK, fg=TEXT_PRIMARY)
text_rotation_value_label.pack(side="left")

# Text timing
text_row6 = tk.Frame(text_section, bg=BG_DARK)
text_row6.pack(fill="x", pady=2)

tk.Label(text_row6, text="Appear at:", bg=BG_DARK, fg=TEXT_PRIMARY, width=10, anchor="w").pack(side="left")
text_appear_slider = ttk.Scale(text_row6, from_=0, to=100, orient="horizontal", command=set_text_appear)
text_appear_slider.pack(side="left", fill="x", expand=True, padx=(0, 10))

tk.Label(text_row6, text="Hide at:", bg=BG_DARK, fg=TEXT_PRIMARY).pack(side="left")
text_disappear_slider = ttk.Scale(text_row6, from_=0, to=100, orient="horizontal", command=set_text_disappear)
text_disappear_slider.pack(side="left", fill="x", expand=True)

# Set initial text slider values AFTER labels exist
updating_sliders = True
text_x_slider.set(50)
text_y_slider.set(90)
text_size_slider.set(10)
text_rotation_slider.set(0)
updating_sliders = False

# === ZOOM ===
zoom_section = create_section(scrollable_frame, "Zoom")

zoom_row = tk.Frame(zoom_section, bg=BG_DARK)
zoom_row.pack(fill="x", pady=2)

tk.Label(zoom_row, text="Level:", bg=BG_DARK, fg=TEXT_PRIMARY, width=10, anchor="w").pack(side="left")
ttk.Button(zoom_row, text="-", command=zoom_out, width=3, style="Small.TButton").pack(side="left", padx=2)
zoom_value_label = tk.Label(zoom_row, text="1.00x", width=6, font=("Segoe UI", 9), bg=BG_DARK, fg=TEXT_PRIMARY)
zoom_value_label.pack(side="left", padx=5)
ttk.Button(zoom_row, text="+", command=zoom_in, width=3, style="Small.TButton").pack(side="left", padx=2)

tk.Label(zoom_row, text="   Position:", bg=BG_DARK, fg=TEXT_PRIMARY).pack(side="left", padx=(15, 5))
ttk.Button(zoom_row, text="<", command=lambda: move_zoom(-0.1, 0), width=2, style="Small.TButton").pack(side="left", padx=1)
ttk.Button(zoom_row, text="^", command=lambda: move_zoom(0, -0.1), width=2, style="Small.TButton").pack(side="left", padx=1)
ttk.Button(zoom_row, text="v", command=lambda: move_zoom(0, 0.1), width=2, style="Small.TButton").pack(side="left", padx=1)
ttk.Button(zoom_row, text=">", command=lambda: move_zoom(0.1, 0), width=2, style="Small.TButton").pack(side="left", padx=1)
zoom_pos_label = tk.Label(zoom_row, text="Center", width=8, font=("Segoe UI", 9), bg=BG_DARK, fg=TEXT_SECONDARY)
zoom_pos_label.pack(side="left", padx=(8, 0))
ttk.Button(zoom_row, text="Reset", command=reset_zoom, width=6, style="Small.TButton").pack(side="right")

# === TIMELINE ===
trim_section = create_section(scrollable_frame, "Timeline Trim")

trim_row1 = tk.Frame(trim_section, bg=BG_DARK)
trim_row1.pack(fill="x", pady=2)

tk.Label(trim_row1, text="Start:", bg=BG_DARK, fg=TEXT_PRIMARY, width=10, anchor="w").pack(side="left")
trim_start_slider = ttk.Scale(trim_row1, from_=0, to=100, orient="horizontal", command=set_trim_start)
trim_start_slider.pack(side="left", fill="x", expand=True)

trim_row2 = tk.Frame(trim_section, bg=BG_DARK)
trim_row2.pack(fill="x", pady=2)

tk.Label(trim_row2, text="End:", bg=BG_DARK, fg=TEXT_PRIMARY, width=10, anchor="w").pack(side="left")
trim_end_slider = ttk.Scale(trim_row2, from_=0, to=100, orient="horizontal", command=set_trim_end)
trim_end_slider.pack(side="left", fill="x", expand=True)

trim_row3 = tk.Frame(trim_section, bg=BG_DARK)
trim_row3.pack(fill="x", pady=(6, 0))

tk.Label(trim_row3, text="Presets:", bg=BG_DARK, fg=TEXT_SECONDARY).pack(side="left", padx=(0, 8))
for sec in [1, 3, 5, 10, 30]:
    ttk.Button(trim_row3, text=f"{sec}s", command=lambda s=sec: set_trim_preset(s), width=4, style="Small.TButton").pack(side="left", padx=2)

ttk.Button(trim_row3, text="Go End", command=go_to_trim_end, width=7, style="Small.TButton").pack(side="right", padx=2)
ttk.Button(trim_row3, text="Go Start", command=go_to_trim_start, width=7, style="Small.TButton").pack(side="right", padx=2)

trim_info_label = tk.Label(trim_section, text="0 frames | 0.00s", font=("Segoe UI", 9), bg=BG_DARK, fg=ACCENT_BLUE)
trim_info_label.pack(anchor="w", pady=(6, 0))

# === CROP ===
crop_section = create_section(scrollable_frame, "Crop")

crop_row1 = tk.Frame(crop_section, bg=BG_DARK)
crop_row1.pack(fill="x", pady=2)

tk.Label(crop_row1, text="Left:", bg=BG_DARK, fg=TEXT_PRIMARY, width=6, anchor="w").pack(side="left")
crop_left_slider = ttk.Scale(crop_row1, from_=0, to=99, orient="horizontal", command=update_crop_left)
crop_left_slider.pack(side="left", fill="x", expand=True, padx=(0, 10))
crop_left_slider.set(0)

tk.Label(crop_row1, text="Right:", bg=BG_DARK, fg=TEXT_PRIMARY, width=6, anchor="w").pack(side="left")
crop_right_slider = ttk.Scale(crop_row1, from_=1, to=100, orient="horizontal", command=update_crop_right)
crop_right_slider.pack(side="left", fill="x", expand=True)
crop_right_slider.set(100)

crop_row2 = tk.Frame(crop_section, bg=BG_DARK)
crop_row2.pack(fill="x", pady=2)

tk.Label(crop_row2, text="Top:", bg=BG_DARK, fg=TEXT_PRIMARY, width=6, anchor="w").pack(side="left")
crop_top_slider = ttk.Scale(crop_row2, from_=0, to=99, orient="horizontal", command=update_crop_top)
crop_top_slider.pack(side="left", fill="x", expand=True, padx=(0, 10))
crop_top_slider.set(0)

tk.Label(crop_row2, text="Bottom:", bg=BG_DARK, fg=TEXT_PRIMARY, width=6, anchor="w").pack(side="left")
crop_bottom_slider = ttk.Scale(crop_row2, from_=1, to=100, orient="horizontal", command=update_crop_bottom)
crop_bottom_slider.pack(side="left", fill="x", expand=True)
crop_bottom_slider.set(100)

ttk.Button(crop_section, text="Reset Crop", command=reset_crop, style="Small.TButton").pack(anchor="w", pady=(6, 0))

# === IMAGE ADJUSTMENTS ===
adjust_section = create_section(scrollable_frame, "Image Adjustments")

# Threshold
adj_row1 = tk.Frame(adjust_section, bg=BG_DARK)
adj_row1.pack(fill="x", pady=2)
tk.Label(adj_row1, text="Threshold:", bg=BG_DARK, fg=TEXT_PRIMARY, width=10, anchor="w").pack(side="left")
threshold_slider = ttk.Scale(adj_row1, from_=0, to=255, orient="horizontal", command=set_threshold)
threshold_slider.pack(side="left", fill="x", expand=True, padx=(0, 5))
threshold_value_label = tk.Label(adj_row1, text="150", width=5, bg=BG_DARK, fg=TEXT_PRIMARY)
threshold_value_label.pack(side="left")

# Brightness
adj_row2 = tk.Frame(adjust_section, bg=BG_DARK)
adj_row2.pack(fill="x", pady=2)
tk.Label(adj_row2, text="Brightness:", bg=BG_DARK, fg=TEXT_PRIMARY, width=10, anchor="w").pack(side="left")
brightness_slider = ttk.Scale(adj_row2, from_=0.1, to=3.0, orient="horizontal", command=set_brightness)
brightness_slider.pack(side="left", fill="x", expand=True, padx=(0, 5))
brightness_value_label = tk.Label(adj_row2, text="1.00", width=5, bg=BG_DARK, fg=TEXT_PRIMARY)
brightness_value_label.pack(side="left")

# Contrast
adj_row3 = tk.Frame(adjust_section, bg=BG_DARK)
adj_row3.pack(fill="x", pady=2)
tk.Label(adj_row3, text="Contrast:", bg=BG_DARK, fg=TEXT_PRIMARY, width=10, anchor="w").pack(side="left")
contrast_slider = ttk.Scale(adj_row3, from_=0.1, to=3.0, orient="horizontal", command=set_contrast)
contrast_slider.pack(side="left", fill="x", expand=True, padx=(0, 5))
contrast_value_label = tk.Label(adj_row3, text="1.00", width=5, bg=BG_DARK, fg=TEXT_PRIMARY)
contrast_value_label.pack(side="left")

# Saturation
adj_row4 = tk.Frame(adjust_section, bg=BG_DARK)
adj_row4.pack(fill="x", pady=2)
tk.Label(adj_row4, text="Saturation:", bg=BG_DARK, fg=TEXT_PRIMARY, width=10, anchor="w").pack(side="left")
saturation_slider = ttk.Scale(adj_row4, from_=0.0, to=3.0, orient="horizontal", command=set_saturation)
saturation_slider.pack(side="left", fill="x", expand=True, padx=(0, 5))
saturation_value_label = tk.Label(adj_row4, text="1.00", width=5, bg=BG_DARK, fg=TEXT_PRIMARY)
saturation_value_label.pack(side="left")

# Set initial slider values AFTER labels are created
updating_sliders = True
threshold_slider.set(150)
brightness_slider.set(1.0)
contrast_slider.set(1.0)
saturation_slider.set(1.0)
updating_sliders = False

ttk.Button(adjust_section, text="Reset Adjustments", command=reset_adjustments, style="Small.TButton").pack(anchor="w", pady=(6, 0))

# === EXPORT ===
export_section = create_section(scrollable_frame, "Export")

exp_row1 = tk.Frame(export_section, bg=BG_DARK)
exp_row1.pack(fill="x", pady=2)

tk.Label(exp_row1, text="Save to:", bg=BG_DARK, fg=TEXT_PRIMARY, width=10, anchor="w").pack(side="left")
export_path_var = tk.StringVar()
export_path_entry = ttk.Entry(exp_row1, textvariable=export_path_var)
export_path_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))
ttk.Button(exp_row1, text="Browse", command=browse_export_path, style="Small.TButton").pack(side="left")

exp_row2 = tk.Frame(export_section, bg=BG_DARK)
exp_row2.pack(fill="x", pady=2)

tk.Label(exp_row2, text="Filename:", bg=BG_DARK, fg=TEXT_PRIMARY, width=10, anchor="w").pack(side="left")
export_name_entry = ttk.Entry(exp_row2, width=25)
export_name_entry.insert(0, "output")
export_name_entry.pack(side="left", padx=(0, 5))
tk.Label(exp_row2, text=".dat", bg=BG_DARK, fg=TEXT_SECONDARY).pack(side="left")

exp_row3 = tk.Frame(export_section, bg=BG_DARK)
exp_row3.pack(fill="x", pady=(8, 2))

export_btn = ttk.Button(exp_row3, text="Export to .DAT", command=export_dat)
export_btn.pack(side="left", padx=(0, 8))

ttk.Button(exp_row3, text="Cancel", command=cancel_export, style="Small.TButton").pack(side="left")

export_status_label = tk.Label(exp_row3, text="", bg=BG_DARK, fg=ACCENT_BLUE)
export_status_label.pack(side="right", padx=5)

progress_bar = ttk.Progressbar(export_section, orient="horizontal", mode="determinate")
progress_bar.pack(fill="x", pady=(6, 0))

# Footer
footer = tk.Frame(scrollable_frame, bg=BG_DARK)
footer.pack(fill="x", padx=(0, 15), pady=(15, 10))
tk.Label(footer, text="Drag preview to pan | All effects apply to exported file", 
         font=("Segoe UI", 8), bg=BG_DARK, fg=TEXT_SECONDARY).pack()

# Start the app
root.mainloop()
