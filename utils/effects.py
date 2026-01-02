import numpy as np
from PIL import Image, ImageOps, ImageEnhance
from scipy.ndimage import convolve
import os
import uuid
from numba import jit

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

@jit(nopython=True, fastmath=True)
def find_vertical_seam(energy):
    """
    Find vertical seam with lowest energy using dynamic programming.
    Optimized with Numba.
    """
    r, c = energy.shape
    m = energy.copy()
    backtrack = np.zeros((r, c), dtype=np.int64) # Explicit type for numba

    for i in range(1, r):
        for j in range(c):
            # Handle edges
            if j == 0:
                idx = np.argmin(m[i-1, j:j+2])
                offset = j + idx
                min_energy = m[i-1, offset]
            elif j == c - 1:
                idx = np.argmin(m[i-1, j-1:j+1])
                offset = j - 1 + idx
                min_energy = m[i-1, offset]
            else:
                idx = np.argmin(m[i-1, j-1:j+2])
                offset = j - 1 + idx
                min_energy = m[i-1, offset]
            
            backtrack[i, j] = offset
            m[i, j] += min_energy

    # Backtrack to find the path
    seam = np.zeros(r, dtype=np.int64)
    j = np.argmin(m[-1])
    seam[-1] = j
    for i in range(r-2, -1, -1):
        j = backtrack[i+1, j]
        seam[i] = j
        
    return seam

@jit(nopython=True, fastmath=True)
def remove_vertical_seam(img_arr, seam):
    """
    Remove the vertical seam from the image.
    Optimized with Numba (manual loop instead of np.delete).
    """
    r, c, ch = img_arr.shape
    new_img = np.zeros((r, c - 1, ch), dtype=img_arr.dtype)
    
    for i in range(r):
        skip = seam[i]
        col_idx = 0
        for j in range(c):
            if j == skip:
                continue
            new_img[i, col_idx, 0] = img_arr[i, j, 0]
            new_img[i, col_idx, 1] = img_arr[i, j, 1]
            new_img[i, col_idx, 2] = img_arr[i, j, 2]
            col_idx += 1
            
    return new_img

def liquid_resize(image_path, scale=0.5):
    """
    Apply liquid resize (seam carving) effect on BOTH axes.
    scale: Target size percentage (e.g. 0.5 = 50% of original width AND height)
    """
    img = Image.open(image_path).convert("RGB")
    
    # 1. Resize for performance (CRITICAL for Render free tier)
    img = resize_image_keep_ratio(img, max_size=500)
    
    img_arr = np.array(img)
    
    # --- PHASE 1: Reduce Width ---
    h, w, _ = img_arr.shape
    target_w = int(w * scale)
    steps_w = w - target_w
    
    # Safety limit
    if steps_w > 200: steps_w = 200
        
    print(f"Liquid Resize Phase 1 (Width): removing {steps_w} seams...")
    
    for _ in range(steps_w):
        energy = calc_energy(img_arr)
        seam = find_vertical_seam(energy)
        img_arr = remove_vertical_seam(img_arr, seam)
        
    # --- PHASE 2: Reduce Height ---
    # Rotate image 90 degrees so we can use the same vertical seam logic
    img_arr = np.rot90(img_arr, k=1, axes=(0, 1))
    
    h_curr, w_curr, _ = img_arr.shape # Note: dimensions swapped
    # We want to reduce based on original height ratio
    target_h = int(h * scale) 
    steps_h = w_curr - target_h # We are reducing 'width' of rotated image
    
    # Safety limit
    if steps_h > 200: steps_h = 200
    
    print(f"Liquid Resize Phase 2 (Height): removing {steps_h} seams...")
    
    for _ in range(steps_h):
        energy = calc_energy(img_arr)
        seam = find_vertical_seam(energy)
        img_arr = remove_vertical_seam(img_arr, seam)

    # Rotate back
    img_arr = np.rot90(img_arr, k=-1, axes=(0, 1))

    result_img = Image.fromarray(np.uint8(img_arr))
    
    if not os.path.exists("assets/generated"):
        os.makedirs("assets/generated")
    
    output_path = f"assets/generated/{uuid.uuid4()}.jpg"
    result_img.save(output_path)
    return output_path

def deep_fry_effect(image_path):
    """
    Apply 'Deep Fried' effect: noise, extreme saturation/contrast, and jpeg artifacts.
    """
    img = Image.open(image_path).convert("RGB")
    
    # Resize slightly larger than liquid resize as this is faster
    img = resize_image_keep_ratio(img, max_size=800)
    
    # 1. Add Noise
    # Convert to numpy to add noise efficiently
    img_arr = np.array(img)
    noise = np.random.randint(0, 25, img_arr.shape, dtype='uint8') # Subtle noise
    # Add noise and clip to valid range
    img_arr = np.clip(img_arr.astype(int) + noise, 0, 255).astype('uint8')
    img = Image.fromarray(img_arr)
    
    # 2. Enhance Saturation (Fried colors)
    converter = ImageEnhance.Color(img)
    img = converter.enhance(3.0) # 3x Saturation
    
    # 3. Enhance Contrast (Deep burn)
    converter = ImageEnhance.Contrast(img)
    img = converter.enhance(2.0) # 2x Contrast
    
    # 4. Enhance Sharpness (Crispy edges)
    converter = ImageEnhance.Sharpness(img)
    img = converter.enhance(5.0) # 5x Sharpness
    
    if not os.path.exists("assets/generated"):
        os.makedirs("assets/generated")
    
    output_path = f"assets/generated/{uuid.uuid4()}.jpg"
    
    # 5. Save with low quality for JPEG artifacts
    img.save(output_path, "JPEG", quality=8)
    
    return output_path

@jit(nopython=True, fastmath=True)
def apply_swirl_numba(img_arr, radius, strength):
    """
    Apply a swirl distortion to the image center using Numba.
    """
    h, w, c = img_arr.shape
    cx, cy = w / 2, h / 2
    output = np.zeros_like(img_arr)

    for y in range(h):
        for x in range(w):
            dx = x - cx
            dy = y - cy
            distance = np.sqrt(dx*dx + dy*dy)

            if distance < radius:
                # Calculate angle
                angle = np.arctan2(dy, dx)
                # Add distortion (more rotation closer to center)
                distortion = strength * (1.0 - distance / radius)
                
                # Calculate source coordinates
                src_x = cx + distance * np.cos(angle + distortion)
                src_y = cy + distance * np.sin(angle + distortion)

                # Nearest neighbor interpolation
                sx = int(round(src_x))
                sy = int(round(src_y))

                # Boundary checks
                if 0 <= sx < w and 0 <= sy < h:
                    output[y, x, 0] = img_arr[sy, sx, 0]
                    output[y, x, 1] = img_arr[sy, sx, 1]
                    output[y, x, 2] = img_arr[sy, sx, 2]
                else:
                    output[y, x, 0] = img_arr[y, x, 0]
                    output[y, x, 1] = img_arr[y, x, 1]
                    output[y, x, 2] = img_arr[y, x, 2]
            else:
                # Outside radius, keep original
                output[y, x, 0] = img_arr[y, x, 0]
                output[y, x, 1] = img_arr[y, x, 1]
                output[y, x, 2] = img_arr[y, x, 2]
                
    return output

def warp_effect(image_path):
    """
    Apply a 'Swirl' warp effect to the center of the image.
    """
    img = Image.open(image_path).convert("RGB")
    
    # Resize for consistent speed
    img = resize_image_keep_ratio(img, max_size=600)
    img_arr = np.array(img)
    
    h, w, _ = img_arr.shape
    
    # Radius covers most of the image, Strength is how many radians to twist
    radius = min(h, w) * 0.9 / 2
    strength = 5.0 # Pretty strong swirl
    
    print(f"Applying Swirl Warp: {w}x{h}...")
    
    # Numba magic
    result_arr = apply_swirl_numba(img_arr, radius, strength)
    
    output_path = f"assets/generated/{uuid.uuid4()}.jpg"
    result_img.save(output_path)
    return output_path

def crispy_effect(image_path):
    """
    Apply 'Crispy' effect: extreme sharpness, high contrast, and increased brightness.
    """
    img = Image.open(image_path).convert("RGB")
    
    # Resize for consistent speed
    img = resize_image_keep_ratio(img, max_size=800)
    
    # 1. Enhance Sharpness (Extreme!)
    converter = ImageEnhance.Sharpness(img)
    img = converter.enhance(15.0) # Very high sharpness
    
    # 2. Enhance Contrast (Blow out blacks and whites)
    converter = ImageEnhance.Contrast(img)
    img = converter.enhance(3.0) # Very high contrast
    
    # 3. Enhance Brightness (Makes it more "blown out")
    converter = ImageEnhance.Brightness(img)
    img = converter.enhance(1.5) # A bit brighter

    if not os.path.exists("assets/generated"):
        os.makedirs("assets/generated")
    
    output_path = f"assets/generated/{uuid.uuid4()}.jpg"
    img.save(output_path) # No low JPEG quality here, as it's not deep fry
    
    return output_path
