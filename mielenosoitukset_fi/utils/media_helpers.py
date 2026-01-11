from __future__ import annotations

from typing import Any, Iterable, List


def _extract_value(obj: Any, key: str) -> Any:
    """Return attribute or dict value for obj."""
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _coerce_to_iterable(value: Any) -> Iterable[str]:
    """Normalize gallery field values to an iterable of strings."""
    if not value:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple, set)):
        return value
    return []


def get_demo_gallery_images(demo: Any, include_preview: bool = True) -> List[str]:
    """
    Collect gallery-worthy images for a demonstration, preserving order.

    Parameters
    ----------
    demo : dict or Demonstration
        Source demonstration data.
    include_preview : bool, optional
        Whether preview/screenshot images should be appended as fallbacks.
    """
    images: List[str] = []

    def _append(candidate: Any) -> None:
        for item in _coerce_to_iterable(candidate):
            if not item:
                continue
            normalized = item.strip()
            if normalized and normalized not in images:
                images.append(normalized)

    _append(_extract_value(demo, "gallery_images"))
    _append(_extract_value(demo, "images"))  # legacy field name
    _append(_extract_value(demo, "img"))
    _append(_extract_value(demo, "cover_picture"))
    _append(_extract_value(demo, "cover_image"))

    if include_preview:
        _append(_extract_value(demo, "preview_image"))

    return images


def get_demo_cover_image(demo: Any) -> str:
    """Return the preferred cover image URL for a demo."""
    images = get_demo_gallery_images(demo)
    if images:
        return images[0]
    return "#"

