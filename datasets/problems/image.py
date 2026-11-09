import numpy as np
from PIL import Image, ImageFilter

PHOTO = Image.fromarray(
    np.random.default_rng(0).integers(0, 256, (P["side"], P["side"], 3), dtype=np.uint8)
)


def initial():
    return 0.0


def work(x, i):
    edited = PHOTO.rotate(x, resample=Image.Resampling.BILINEAR)
    edited = edited.filter(ImageFilter.GaussianBlur(P["blur"]))
    small = edited.resize((P["side"] // 4, P["side"] // 4), Image.Resampling.LANCZOS)
    brightness = float(np.asarray(small.convert("L")).mean())
    return round(brightness % 45.0, 3)


def combine(xs):
    return round(sum(xs) / len(xs), 3)


def digest(x):
    return f"{x:.3f}"
