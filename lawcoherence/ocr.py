import io


def ocr_pdf(path, dpi=250, lang="ara"):
    import fitz
    import pytesseract
    from PIL import Image
    pages = []
    for page in fitz.open(path):
        png = page.get_pixmap(dpi=dpi).tobytes("png")
        pages.append(pytesseract.image_to_string(Image.open(io.BytesIO(png)), lang=lang))
    return "\n".join(pages)
