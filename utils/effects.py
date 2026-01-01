import numpy as np
from PIL import Image, ImageOps
from scipy.ndimage import convolve
import os
import uuid

def resize_image_keep_ratio(image, max_size=600):
    """
    Resizes the image so that the longest side is at most max_size.
    Maintains aspect ratio.
    """
    w, h = image.size
    if max(w, h) <= max_size:
        return image
    
    if w > h:
        new_w = max_size
        new_h = int(h * (max_size / w))
    else:
        new_h = max_size
        new_w = int(w * (max_size / h))
        
    return image.resize((new_w, new_h), Image.Resampling.LANCZOS)

def calc_energy(img_arr):
    """
    Calculate energy map using simple gradient magnitude.
    img_arr: numpy array (H, W, 3) or (H, W)
    """
    if len(img_arr.shape) == 3:
        # Convert to grayscale for energy calculation
        gray = np.mean(img_arr, axis=2)
    else:
        gray = img_arr

    # Sobel-like filters
    dx = np.array([[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]])
    dy = np.array([[-1, -2, -1], [0, 0, 0], [1, 2, 1]])

    energy_x = convolve(gray, dx)
    energy_y = convolve(gray, dy)
    
    return np.abs(energy_x) + np.abs(energy_y)

def find_vertical_seam(energy):
    """
    Find vertical seam with lowest energy using dynamic programming.
    """
    r, c = energy.shape
    m = energy.copy()
    backtrack = np.zeros_like(m, dtype=int)

    for i in range(1, r):
        for j in range(c):
            # Handle edges
            if j == 0:
                idx = np.argmin(m[i-1, j:j+2])
                backtrack[i, j] = j + idx
                min_energy = m[i-1, j + idx]
            elif j == c - 1:
                idx = np.argmin(m[i-1, j-1:j+1])
                backtrack[i, j] = j - 1 + idx
                min_energy = m[i-1, j - 1 + idx]
            else:
                idx = np.argmin(m[i-1, j-1:j+2])
                backtrack[i, j] = j - 1 + idx
                min_energy = m[i-1, j - 1 + idx]
            
            m[i, j] += min_energy

    # Backtrack to find the path
    seam = np.zeros(r, dtype=int)
    j = np.argmin(m[-1])
    seam[-1] = j
    for i in range(r-2, -1, -1):
        j = backtrack[i+1, j]
        seam[i] = j
        
    return seam

def remove_vertical_seam(img_arr, seam):
    r, c, _ = img_arr.shape
    new_img = np.zeros((r, c - 1, 3), dtype=img_arr.dtype)
    for i in range(r):
        j = seam[i]
        new_img[i, :, :] = np.delete(img_arr[i, :, :], j, axis=0)
    return new_img

def liquid_resize(image_path, scale=0.5):
    """
    Apply liquid resize (seam carving) effect.
    scale: Target width percentage (e.g. 0.5 = 50% of original width)
    """
    img = Image.open(image_path).convert("RGB")
    
    # 1. Resize for performance (CRITICAL for Render free tier)
    img = resize_image_keep_ratio(img, max_size=500)
    
    img_arr = np.array(img)
    h, w, _ = img_arr.shape
    
    target_w = int(w * scale)
    steps = w - target_w
    
    # Safety limit to avoid timeout
    if steps > 200: 
        steps = 200
        
    print(f"Applying liquid resize: {w}x{h} -> removing {steps} seams...")
    
    for _ in range(steps):
        energy = calc_energy(img_arr)
        seam = find_vertical_seam(energy)
        img_arr = remove_vertical_seam(img_arr, seam)

    result_img = Image.fromarray(np.uint8(img_arr))
    
    if not os.path.exists("assets/generated"):
        os.makedirs("assets/generated")
    
    output_path = f"assets/generated/{uuid.uuid4()}.jpg"
    result_img.save(output_path)
    return output_path
