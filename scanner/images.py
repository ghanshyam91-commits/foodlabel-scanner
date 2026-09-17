"""Validate image content and strip EXIF metadata before sending to the provider."""
import io
import warnings
from PIL import Image, ImageOps, UnidentifiedImageError
from pillow_heif import register_heif_opener

register_heif_opener()

MAX_BYTES = 8 * 1024 * 1024
MAX_PIXELS = 30_000_000
class ImageInputError(ValueError):
    pass

def prepare_image(data: bytes) -> bytes:
    if not data or len(data) > MAX_BYTES:
        raise ImageInputError('Choose a photo smaller than 8 MB.')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as check:
                if check.format not in {'JPEG', 'PNG', 'WEBP', 'HEIF'}:
                    raise ImageInputError('Use a JPEG, PNG, WebP, HEIC or HEIF image.')
                if check.width * check.height > MAX_PIXELS:
                    raise ImageInputError('Image is too large. Crop to the ingredient label first.')
                check.verify()
            with Image.open(io.BytesIO(data)) as image:
                if image.width < 160 or image.height < 160:
                    raise ImageInputError('Photo is too small to read. Take a closer, sharper photo.')
                image = ImageOps.exif_transpose(image)
                if image.mode in {'RGBA', 'LA'} or 'transparency' in image.info:
                    rgba = image.convert('RGBA')
                    background = Image.new('RGBA', rgba.size, 'white')
                    image = Image.alpha_composite(background, rgba).convert('RGB')
                else:
                    image = image.convert('RGB')
                image.thumbnail((2400, 2400), Image.Resampling.LANCZOS)
                output = io.BytesIO()
                image.save(output, format='JPEG', quality=92, optimize=True)
                return output.getvalue()
    except ImageInputError:
        raise
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombWarning, Image.DecompressionBombError) as exc:
        raise ImageInputError('This photo could not be read. Try another JPEG or PNG.') from exc
