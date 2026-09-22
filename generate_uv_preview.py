import json
import struct
import sys
import os

try:
    from PIL import Image, ImageDraw
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "Pillow"])
    from PIL import Image, ImageDraw

def read_accessor(gltf, bin_data, accessor_idx):
    accessor = gltf['accessors'][accessor_idx]
    view_idx = accessor['bufferView']
    view = gltf['bufferViews'][view_idx]
    
    offset = view.get('byteOffset', 0) + accessor.get('byteOffset', 0)
    count = accessor['count']
    comp_type = accessor['componentType']
    type_str = accessor['type']
    
    # componentType: 5126 (FLOAT), 5123 (UNSIGNED_SHORT), 5125 (UNSIGNED_INT)
    # type: SCALAR, VEC2, VEC3
    
    format_char = 'f'
    comp_size = 4
    if comp_type == 5123:
        format_char = 'H'
        comp_size = 2
    elif comp_type == 5125:
        format_char = 'I'
        comp_size = 4
        
    num_comps = 1
    if type_str == 'VEC2': num_comps = 2
    elif type_str == 'VEC3': num_comps = 3
    elif type_str == 'VEC4': num_comps = 4
    
    fmt = '<' + (format_char * num_comps)
    stride = view.get('byteStride', comp_size * num_comps)
    
    data = []
    for i in range(count):
        idx = offset + i * stride
        chunk = bin_data[idx : idx + comp_size * num_comps]
        val = struct.unpack(fmt, chunk)
        data.append(val if num_comps > 1 else val[0])
    return data

def generate_uv_preview():
    filepath = 'client/public/models/player_lipsync.glb'
    tex_path = 'client/public/models/textures/baseColor.jpg'
    out_path = 'client/public/models/textures/baseColor_UV_preview.png'
    
    with open(filepath, 'rb') as f:
        magic = f.read(4)
        if magic != b'glTF':
            return
        version = struct.unpack('<I', f.read(4))[0]
        length = struct.unpack('<I', f.read(4))[0]

        # Read JSON
        chunk_length = struct.unpack('<I', f.read(4))[0]
        chunk_type = f.read(4)
        json_data = f.read(chunk_length).decode('utf-8')
        gltf = json.loads(json_data)

        # Read BIN
        bin_chunk_length = struct.unpack('<I', f.read(4))[0]
        bin_chunk_type = f.read(4)
        bin_data = f.read(bin_chunk_length)
        
    # Find Wolf3D_Skin primitive
    skin_prim = None
    for mesh in gltf.get('meshes', []):
        if 'Wolf3D_Head' in mesh.get('name', ''):
            skin_prim = mesh['primitives'][0]
            break
            
    if not skin_prim:
        print("Wolf3D_Skin not found")
        return
        
    # Extract UVs and Indices
    uv_acc_idx = skin_prim['attributes']['TEXCOORD_0']
    ind_acc_idx = skin_prim['indices']
    
    uvs = read_accessor(gltf, bin_data, uv_acc_idx)
    indices = read_accessor(gltf, bin_data, ind_acc_idx)
    
    # Load Image
    img = Image.open(tex_path).convert('RGBA')
    width, height = img.size
    
    # Draw wireframe
    draw = ImageDraw.Draw(img)
    
    # Triangles
    for i in range(0, len(indices), 3):
        i1, i2, i3 = indices[i], indices[i+1], indices[i+2]
        
        # UVs are (u, v) where u is [0,1] and v is [0,1] (bottom to top in GL coordinate system, but Pillow is top to bottom)
        # GLTF UV v is usually top-down (0 = top, 1 = bottom), let's check
        
        u1, v1 = uvs[i1]
        u2, v2 = uvs[i2]
        u3, v3 = uvs[i3]
        
        x1, y1 = u1 * width, v1 * height
        x2, y2 = u2 * width, v2 * height
        x3, y3 = u3 * width, v3 * height
        
        draw.line([(x1, y1), (x2, y2), (x3, y3), (x1, y1)], fill=(0, 255, 0, 128), width=1)
        
    img.save(out_path)
    print(f"Saved UV preview to {out_path}")

if __name__ == '__main__':
    generate_uv_preview()
