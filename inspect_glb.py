import json
import struct
import sys

def inspect_glb(filepath):
    with open(filepath, 'rb') as f:
        # Read GLB Header (12 bytes)
        magic = f.read(4)
        if magic != b'glTF':
            print("Not a valid GLB file")
            return
        version = struct.unpack('<I', f.read(4))[0]
        length = struct.unpack('<I', f.read(4))[0]

        # Read JSON Chunk header (8 bytes)
        chunk_length = struct.unpack('<I', f.read(4))[0]
        chunk_type = f.read(4)
        if chunk_type != b'JSON':
            print("First chunk is not JSON")
            return

        # Read JSON Data
        json_data = f.read(chunk_length).decode('utf-8')
        gltf = json.loads(json_data)

        # Print out the required details
        print("=== GLTF INSPECTION ===")
        
        # Nodes
        print("\n--- NODES ---")
        for i, node in enumerate(gltf.get('nodes', [])):
            if 'name' in node and ('Wolf3D' in node['name'] or 'Eye' in node['name']):
                print(f"Node: {node['name']}")
                if 'mesh' in node:
                    mesh = gltf['meshes'][node['mesh']]
                    print(f"  -> Mesh: {mesh.get('name', 'unnamed')}")
                    
                    if 'primitives' in mesh:
                        prim = mesh['primitives'][0]
                        # Material
                        if 'material' in prim:
                            mat = gltf['materials'][prim['material']]
                            print(f"  -> Material: {mat.get('name', 'unnamed')}")
                            
                            pbr = mat.get('pbrMetallicRoughness', {})
                            if 'baseColorTexture' in pbr:
                                tex_index = pbr['baseColorTexture']['index']
                                tex = gltf['textures'][tex_index]
                                image_index = tex.get('source')
                                if image_index is not None:
                                    image = gltf['images'][image_index]
                                    print(f"  -> Base Color Texture: {image.get('name', 'unnamed')}, uri: {image.get('uri', 'embedded')}, mime: {image.get('mimeType', 'unknown')}")

                        # Morph Targets
                        if 'targets' in prim:
                            print(f"  -> Morph Targets Count: {len(prim['targets'])}")
                            if 'extras' in mesh and 'targetNames' in mesh['extras']:
                                print(f"  -> Target Names: {mesh['extras']['targetNames'][:5]}... ({len(mesh['extras']['targetNames'])} total)")

if __name__ == '__main__':
    inspect_glb('client/public/models/player_lipsync.glb')
