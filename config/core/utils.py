from io import BytesIO

from PIL import Image


def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def compute_phash(image_file, hash_size=8):
    img = Image.open(image_file)
    img = img.convert('L').resize((hash_size + 1, hash_size), Image.LANCZOS)
    pixels = list(img.getdata())
    diff = []
    for row in range(hash_size):
        for col in range(hash_size):
            idx = row * (hash_size + 1) + col
            diff.append(pixels[idx] > pixels[idx + 1])
    bits = sum(2 ** i for i, bit in enumerate(diff) if bit)
    return f'{bits:016x}'


def hamming_distance(hash1, hash2):
    if len(hash1) != len(hash2):
        return 100
    xor = int(hash1, 16) ^ int(hash2, 16)
    return bin(xor).count('1')
