import json
import struct
import io
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
    view_idx = accessor.get('bufferView')
    if view_idx is None:
        return []
    view = gltf['bufferViews'][view_idx]
    
    offset = view.get('byteOffset', 0) + accessor.get('byteOffset', 0)
    count = accessor['count']
    comp_type = accessor['componentType']
    type_str = accessor['type']
    
    format_char = 'f'
    comp_size = 4
    if comp_type == 5123:
        format_char = 'H'
        comp_size = 2
    elif comp_type == 5125:
        format_char = 'I'
        comp_size = 4
    elif comp_type == 5122:
        format_char = 'h'
        comp_size = 2
    elif comp_type == 5121:
        format_char = 'B'
        comp_size = 1
    elif comp_type == 5120:
        format_char = 'b'
        comp_size = 1
        
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
        if len(chunk) < comp_size * num_comps:
            break
        val = struct.unpack(fmt, chunk)
        data.append(val if num_comps > 1 else val[0])
    return data

def main():
    filepath = 'client/public/models/player_lipsync.glb'
    out_path = 'client/public/models/textures/baseColor_UV_preview.png'
    out_base = 'client/public/models/textures/baseColor_skin.jpg'
    
    os.makedirs('client/public/models/textures', exist_ok=True)
    
    with open(filepath, 'rb') as f:
        magic = f.read(4)
        if magic != b'glTF':
            print("Invalid GLB")
            return
        struct.unpack('<I', f.read(4))[0]
        struct.unpack('<I', f.read(4))[0]

        # Read JSON
        chunk_length = struct.unpack('<I', f.read(4))[0]
        chunk_type = f.read(4)
        json_data = f.read(chunk_length).decode('utf-8')
        gltf = json.loads(json_data)

        # Read BIN
        bin_chunk_length = struct.unpack('<I', f.read(4))[0]
        bin_chunk_type = f.read(4)
        bin_data = f.read(bin_chunk_length)
        
    # 1. Find Wolf3D_Head mesh and primitive
    skin_prim = None
    mesh_name = ""
    for mesh in gltf.get('meshes', []):
        if 'Wolf3D_Head' in mesh.get('name', ''):
            skin_prim = mesh['primitives'][0]
            mesh_name = mesh.get('name')
            break
            
    if not skin_prim:
        print("Wolf3D_Head not found")
        return
        
    mat_idx = skin_prim.get('material')
    mat = gltf['materials'][mat_idx]
    mat_name = mat.get('name', 'unnamed')
    
    # 2. Get the correct texture image for Wolf3D_Skin
    pbr = mat.get('pbrMetallicRoughness', {})
    if 'baseColorTexture' not in pbr:
        print("No baseColorTexture found for Wolf3D_Skin")
        return
        
    tex_idx = pbr['baseColorTexture']['index']
    tex = gltf['textures'][tex_idx]
    img_idx = tex['source']
    img_def = gltf['images'][img_idx]
    
    view_idx = img_def['bufferView']
    view = gltf['bufferViews'][view_idx]
    offset = view.get('byteOffset', 0)
    length = view['byteLength']
    
    img_bytes = bin_data[offset : offset + length]
    
    # Save the true baseColor for skin
    with open(out_base, 'wb') as fb:
        fb.write(img_bytes)
        
    # Load image in Pillow
    img = Image.open(io.BytesIO(img_bytes)).convert('RGBA')
    width, height = img.size
    
    # 3. Extract UVs and Indices
    uv_acc_idx = skin_prim['attributes'].get('TEXCOORD_0')
    ind_acc_idx = skin_prim.get('indices')
    
    uvs = read_accessor(gltf, bin_data, uv_acc_idx) if uv_acc_idx is not None else []
    indices = read_accessor(gltf, bin_data, ind_acc_idx) if ind_acc_idx is not None else []
    
    if not uvs or not indices:
        print("Missing UVs or indices")
        return
        
    # 4. Draw wireframe
    draw = ImageDraw.Draw(img)
    
    for i in range(0, len(indices), 3):
        i1, i2, i3 = indices[i], indices[i+1], indices[i+2]
        
        # GLTF UVs: (0,0) is top-left in most texture space, but let's draw directly
        u1, v1 = uvs[i1]
        u2, v2 = uvs[i2]
        u3, v3 = uvs[i3]
        
        # GLTF uses bottom-left for origin usually? Actually WebGL uses bottom-left, GLTF uses top-left.
        # But texture coords are usually (u, v) where v=0 is top. If it looks upside down, we can flip it later.
        
        x1, y1 = u1 * width, v1 * height
        x2, y2 = u2 * width, v2 * height
        x3, y3 = u3 * width, v3 * height
        
        draw.line([(x1, y1), (x2, y2), (x3, y3), (x1, y1)], fill=(0, 255, 0, 128), width=1)
        
    img.save(out_path)
    
    print(f"baseColor dimensions: {width}x{height}")
    print(f"number of UV coordinates: {len(uvs)}")
    print(f"mesh name: {mesh_name}")
    print(f"material name: {mat_name}")
    print(f"output dimensions: {img.size[0]}x{img.size[1]}")

if __name__ == '__main__':
    main()
