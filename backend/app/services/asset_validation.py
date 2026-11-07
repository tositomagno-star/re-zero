from dataclasses import dataclass
from io import BytesIO
from pathlib import PurePosixPath
import warnings

from PIL import Image, UnidentifiedImageError

from app.core.config import get_settings

MAX_ASSET_BYTES = get_settings().asset_max_upload_bytes
MAX_IMAGE_DIMENSION = 8192
MAX_IMAGE_PIXELS = 40_000_000
MAX_ANIMATION_FRAMES = 500
MAX_TOTAL_FRAME_PIXELS = 100_000_000

_ALLOWED_TYPES = {
    ".png": ("PNG", "image/png"),
    ".jpg": ("JPEG", "image/jpeg"),
    ".jpeg": ("JPEG", "image/jpeg"),
    ".webp": ("WEBP", "image/webp"),
    ".gif": ("GIF", "image/gif"),
}


class AssetUploadTooLarge(ValueError):
    pass


class AssetMediaTypeError(ValueError):
    pass


@dataclass(frozen=True)
class ValidatedAssetImage:
    filename: str
    extension: str
    content_type: str
    width: int
    height: int
    analysis_metadata: dict[str, object]


def _frame_has_transparency(image: Image.Image) -> bool:
    if "A" in image.getbands():
        return image.getchannel("A").getextrema()[0] < 255
    transparency = image.info.get("transparency")
    if transparency is None:
        return False
    if image.mode == "P":
        histogram = image.histogram()
        if isinstance(transparency, int):
            return histogram[transparency] > 0
        if isinstance(transparency, bytes):
            return any(
                alpha < 255 and histogram[index] > 0
                for index, alpha in enumerate(transparency)
            )
    return True


def validate_asset_image(
    filename: str | None,
    content_type: str | None,
    data: bytes,
) -> ValidatedAssetImage:
    if not data:
        raise ValueError("O arquivo está vazio.")
    if len(data) > MAX_ASSET_BYTES:
        raise AssetUploadTooLarge("A imagem excede o limite configurado para upload.")
    if not filename:
        raise ValueError("O arquivo precisa ter uma extensão permitida.")

    basename = PurePosixPath(filename.replace("\\", "/")).name
    if (
        not basename
        or len(basename) > 255
        or any(ord(character) < 32 or ord(character) == 127 for character in basename)
    ):
        raise ValueError("O nome do arquivo é inválido.")

    extension = PurePosixPath(basename).suffix.lower()
    expected = _ALLOWED_TYPES.get(extension)
    if expected is None:
        raise AssetMediaTypeError("Formato não permitido. Envie PNG, JPG, JPEG, WebP ou GIF.")

    expected_format, expected_mime = expected
    submitted_mime = (content_type or "").split(";", maxsplit=1)[0].strip().lower()
    if submitted_mime != expected_mime:
        raise AssetMediaTypeError("O tipo MIME não corresponde à extensão do arquivo.")

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as image:
                actual_format = image.format
                width, height = image.size
                frame_count = getattr(image, "n_frames", 1)
                frame_durations: list[int | None] = []
                all_durations_known = True
                has_transparency = False
                loop_value = image.info.get("loop")
                if (
                    width < 1
                    or height < 1
                    or width > MAX_IMAGE_DIMENSION
                    or height > MAX_IMAGE_DIMENSION
                    or width * height > MAX_IMAGE_PIXELS
                ):
                    raise ValueError("As dimensões da imagem são inválidas ou excedem o limite.")
                if frame_count > MAX_ANIMATION_FRAMES:
                    raise ValueError("A animação excede o limite de 500 quadros.")
                if width * height * frame_count > MAX_TOTAL_FRAME_PIXELS:
                    raise ValueError("A animação excede o limite total de pixels.")
                for frame in range(frame_count):
                    image.seek(frame)
                    image.load()
                    has_transparency = has_transparency or _frame_has_transparency(image)
                    if actual_format == "GIF":
                        duration = image.info.get("duration")
                        if isinstance(duration, (int, float)) and duration >= 0:
                            frame_durations.append(int(duration))
                        else:
                            frame_durations.append(None)
                            all_durations_known = False
                gif_metadata: dict[str, object] | None = None
                if actual_format == "GIF":
                    gif_metadata = {
                        "frame_count": frame_count,
                        "total_duration_ms": (
                            sum(duration for duration in frame_durations if duration is not None)
                            if all_durations_known
                            else None
                        ),
                        "frame_durations_ms": frame_durations,
                        "loop": (
                            loop_value
                            if isinstance(loop_value, int) and loop_value >= 0
                            else None
                        ),
                    }
    except ValueError:
        raise
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as error:
        raise ValueError("A imagem excede os limites seguros de decodificação.") from error
    except (OSError, SyntaxError, UnidentifiedImageError) as error:
        raise ValueError("O conteúdo enviado não é uma imagem válida.") from error

    if actual_format != expected_format:
        raise ValueError("O conteúdo real do arquivo não corresponde à extensão informada.")

    return ValidatedAssetImage(
        filename=basename,
        extension=extension,
        content_type=expected_mime,
        width=width,
        height=height,
        analysis_metadata={
            "aspect_ratio": round(width / height, 6),
            "has_transparency": has_transparency,
            "gif": gif_metadata,
        },
    )
