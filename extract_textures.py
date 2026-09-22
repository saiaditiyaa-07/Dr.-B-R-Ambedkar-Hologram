import json
import struct
import os

def extract_textures(filepath, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    with open(filepath, 'rb') as f:
        magic = f.read(4)
        if magic != b'glTF':
            return
        version = struct.unpack('<I', f.read(4))[0]
        length = struct.unpack('<I', f.read(4))[0]

        # Read JSON Chunk
        chunk_length = struct.unpack('<I', f.read(4))[0]
        chunk_type = f.read(4)
        json_data = f.read(chunk_length).decode('utf-8')
        gltf = json.loads(json_data)

        # Read BIN Chunk
        bin_chunk_length = struct.unpack('<I', f.read(4))[0]
        bin_chunk_type = f.read(4)
        if bin_chunk_type != b'BIN\x00':
            return
        
        bin_data = f.read(bin_chunk_length)

        # Extract images
        if 'images' in gltf:
            for i, image in enumerate(gltf['images']):
                if 'bufferView' in image:
                    view_idx = image['bufferView']
                    view = gltf['bufferViews'][view_idx]
                    offset = view.get('byteOffset', 0)
                    length = view['byteLength']
                    img_bytes = bin_data[offset : offset + length]
                    
                    mime = image.get('mimeType', 'image/jpeg')
                    ext = '.jpg' if 'jpeg' in mime else '.png'
                    name = image.get('name', f'texture_{i}')
                    if not name.strip():
                        name = f'texture_{i}'
                    
                    out_path = os.path.join(out_dir, f"{name}{ext}")
                    with open(out_path, 'wb') as img_f:
                        img_f.write(img_bytes)
                    print(f"Extracted {name}{ext}")

if __name__ == '__main__':
    extract_textures('client/public/models/player_lipsync.glb', 'client/public/models/textures')
