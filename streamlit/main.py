import streamlit as st
from streamlit_image_comparison import image_comparison
import PIL.Image
import io
import hashlib
import random
import numpy as np
import piexif
import tempfile

# Include your functions here (shortened for readability)
def image_to_bytes(image, exif_data=None):
    byte_arr = io.BytesIO()
    if exif_data:
        image.save(byte_arr, format='JPEG', quality=85, exif=exif_data)
    else:
        image.save(byte_arr, format='JPEG', quality=85)
    return byte_arr.getvalue()

def calculate_hash(image_bytes):
    return hashlib.sha256(image_bytes).hexdigest()

def exploit_compression_artifacts(image, quality):
    buffer = io.BytesIO()
    image.save(buffer, format='JPEG', quality=quality)
    buffer.seek(0)
    compressed_image = PIL.Image.open(buffer)
    return compressed_image.copy()

def modify_lsb(image):
    img_array = np.array(image, dtype=np.uint8)
    noise = np.random.randint(0, 2, img_array.shape, dtype=np.uint8)
    modified_array = (img_array & 0xFE) | noise
    modified_image = PIL.Image.fromarray(modified_array, mode=image.mode)
    return modified_image

def add_noise(image):
    np_image = np.array(image)
    noise = np.random.normal(0, 10, np_image.shape)
    np_image = np.clip(np_image + noise, 0, 255).astype(np.uint8)
    return PIL.Image.fromarray(np_image)

def modify_exif_metadata(image):
    """
    Modifies EXIF metadata to include random comments.
    """
    error_logged = False
    try:
        # Extract EXIF data from the image object directly or initialize an object for EXIF with some common fields
        exif_data = image.info.get('exif', b'')
        exif_dict = piexif.load(exif_data) if exif_data else {"0th": {}, "Exif": {}, "GPS": {}, "Interop": {}, "1st": {}, "thumbnail": None}
        
        # Modify the EXIF data randomly
        modifications = [
            ('0th', piexif.ImageIFD.XPComment, str(random.random()).encode('utf-16')),
            ('Exif', piexif.ExifIFD.UserComment, f"Modification {random.randint(0, 1000)}".encode('utf-16'))
        ]
        
        # Apply the modifications
        for ifd, tag, value in modifications:
            if ifd in exif_dict:
                exif_dict[ifd][tag] = value

        # Dump the EXIF data and return it
        exif_bytes = piexif.dump(exif_dict)
        return exif_bytes

    except Exception as e:
        if not error_logged:
            print(f"Error modifying EXIF: {e}")
            error_logged = True
        return None

def modify_input_image(image, temperature):
    quality = max(10, int(85 - (temperature * 5)))
    compressed_image = exploit_compression_artifacts(image, quality)
    lsb_modified_image = modify_lsb(compressed_image)
    noise_modified_image = add_noise(lsb_modified_image)
    exif_data = modify_exif_metadata(noise_modified_image)
    return noise_modified_image, exif_data

def simulated_annealing(image, desired_prefix, temperature=1.0, cooling_rate=0.99, max_iterations=1):
    """
    Applies simulated annealing to modify an image until its hash matches a desired prefix.
    """
    original_image = image.copy()
    original_image_bytes = image_to_bytes(original_image)
    original_hash = calculate_hash(original_image_bytes)

    target_prefix = desired_prefix
    current_image = original_image
    current_temperature = temperature
    iteration = 0

    while iteration < max_iterations:
        iteration += 1
        modified_image, exif_data = modify_input_image(current_image, current_temperature)

        modified_image_bytes = image_to_bytes(modified_image, exif_data=exif_data)
        modified_hash = calculate_hash(modified_image_bytes)

        if modified_hash.startswith(target_prefix):
                return modified_image, calculate_hash(image_to_bytes(modified_image))  # Return the best image and its hash


        current_temperature *= cooling_rate

    return modified_image, calculate_hash(image_to_bytes(modified_image))  # Return the best image and its hash

def save_and_provide_download_button(image, filename="modified_image.jpg"):
    image.save(filename)
    with open(filename, "rb") as file:
        st.download_button(
            label="Download Modified Image",
            data=file,
            file_name=filename,
            mime="image/jpeg",
        )
# Streamlit App Code
st.markdown("# Hash Spoofer 👨‍🔧 by [Stephanie Mukami](https://github.com/stephmukami)")
st.markdown("---")
st.markdown("""
### 🔎 Quick Guide
Upload a JPEG/JPG image, input a valid hex string of your choice, and press the button spoof.
This will create the hash of the input image and generate the closest matching hash that starts
with a prefix of your hash string. You will be able to download the modified image as well.
""", unsafe_allow_html=True)

st.markdown("""It might take a few seconds to run""", unsafe_allow_html=True)
st.markdown("---")

text_input = st.text_input('Hexadecimal String', placeholder="0x24")
file = st.file_uploader("Pick a JPEG/JPG file")

if file and text_input:
    try:
        if not text_input.startswith('0x'):
            st.error("Hexadecimal string must start with '0x'")
        else:
            int(text_input, 16)  # Validate hex string

            input_image = PIL.Image.open(file)
            if input_image.format not in ('JPEG', 'JPG'):
                st.error("Only JPEG/JPG files are supported.")
            else:
                st.image(input_image, caption="Original Image", use_container_width=True)

                with st.spinner("Processing..."):
                    result_image, result_hash = simulated_annealing(input_image, text_input)

                st.success("Image processed successfully!")

                # Calculate and display hashes
                input_image_bytes = image_to_bytes(input_image)
                original_hash = calculate_hash(input_image_bytes)

                st.markdown(f"**Original Hash:** `{original_hash}`")
                st.markdown(f"**Result Hash:** `{result_hash}`")

                # Provide download button for modified image
                with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as temp_file:
                    result_image.save(temp_file.name)
                    st.download_button(
                        label="Download Modified Image",
                        data=open(temp_file.name, "rb"),
                        file_name="modified_image.jpg",
                        mime="image/jpeg",
                    )

    except Exception as e:
        st.error(f"An error occurred: {e}")
