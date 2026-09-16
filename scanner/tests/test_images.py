import io
import unittest
from PIL import Image
from scanner.images import prepare_image, ImageInputError, MAX_BYTES

def image_bytes(size=(300,300), fmt='PNG', mode='RGB'):
    b=io.BytesIO();Image.new(mode,size).save(b,format=fmt);return b.getvalue()
class ImageTests(unittest.TestCase):
    def test_png_to_jpeg(self):
        with Image.open(io.BytesIO(prepare_image(image_bytes()))) as im:self.assertEqual(im.format,'JPEG')
    def test_invalid_file(self):
        with self.assertRaises(ImageInputError):prepare_image(b'<script>bad</script>')
    def test_empty_file(self):
        with self.assertRaises(ImageInputError):prepare_image(b'')
    def test_size_limit(self):
        with self.assertRaises(ImageInputError):prepare_image(b'x'*(MAX_BYTES+1))
    def test_small_image(self):
        with self.assertRaises(ImageInputError):prepare_image(image_bytes((40,40)))
    def test_gif_rejected(self):
        with self.assertRaises(ImageInputError):prepare_image(image_bytes(fmt='GIF'))
    def test_large_dimensions_rejected(self):
        with self.assertRaises(ImageInputError):prepare_image(image_bytes((6000,6000),mode='1'))
    def test_downscale(self):
        with Image.open(io.BytesIO(prepare_image(image_bytes((3000,2000))))) as im:self.assertEqual(im.size,(2400,1600))
    def test_transparency_flattened(self):
        with Image.open(io.BytesIO(prepare_image(image_bytes(mode='RGBA')))) as im:self.assertEqual(im.mode,'RGB');self.assertEqual(im.getpixel((0,0)),(255,255,255))
    def test_exif_removed(self):
        b=io.BytesIO();im=Image.new('RGB',(300,300));exif=Image.Exif();exif[270]='private metadata';im.save(b,format='JPEG',exif=exif)
        with Image.open(io.BytesIO(prepare_image(b.getvalue()))) as clean:self.assertFalse(clean.getexif())
