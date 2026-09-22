import json
import struct

def list_animations(filepath):
    with open(filepath, 'rb') as f:
        magic = f.read(4)
        if magic != b'glTF':
            print("Not a valid GLB file")
            return
        struct.unpack('<I', f.read(4))[0]
        struct.unpack('<I', f.read(4))[0]

        chunk_length = struct.unpack('<I', f.read(4))[0]
        chunk_type = f.read(4)
        json_data = f.read(chunk_length).decode('utf-8')
        gltf = json.loads(json_data)

        if 'animations' in gltf:
            print("=== ANIMATIONS ===")
            for i, anim in enumerate(gltf['animations']):
                print(f"Animation {i}: {anim.get('name', 'unnamed')}")
        else:
            print("No animations found.")

if __name__ == '__main__':
    list_animations('client/public/models/animations.glb')
