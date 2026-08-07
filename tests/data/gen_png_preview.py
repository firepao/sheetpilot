import struct
import zlib

def create_png(width, height, output_path):
    """创建一个简单的 PNG 文件"""
    
    def write_chunk(f, chunk_type, data):
        f.write(struct.pack('>I', len(data)))
        f.write(chunk_type)
        f.write(data)
        crc = zlib.crc32(chunk_type + data) & 0xffffffff
        f.write(struct.pack('>I', crc))
    
    with open(output_path, 'wb') as f:
        # PNG signature
        f.write(b'\x89PNG\r\n\x1a\n')
        
        # IHDR chunk
        ihdr_data = struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)
        write_chunk(f, b'IHDR', ihdr_data)
        
        # IDAT chunk (image data)
        raw_data = b''
        for y in range(height):
            raw_data += b'\x00'  # filter byte
            for x in range(width):
                # Create a simple gradient pattern
                r = int(255 * x / max(width - 1, 1))
                g = int(255 * y / max(height - 1, 1))
                b = 128
                raw_data += bytes([r, g, b])
        
        compressed = zlib.compress(raw_data)
        write_chunk(f, b'IDAT', compressed)
        
        # IEND chunk
        write_chunk(f, b'IEND', b'')

# 创建一个 800x600 的 PNG 预览文件
output_path = r"D:\bitexcel\SheetPilot\tests\data\result\UV_DEMO_I3_dirty_orders_preview1.png"
create_png(800, 600, output_path)
print(f"PNG preview created at: {output_path}")
