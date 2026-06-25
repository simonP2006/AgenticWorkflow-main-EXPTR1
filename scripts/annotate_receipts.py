#!/usr/bin/env python3
"""
annotate_receipts.py — Red Dotted Rectangle annotation per PRD §19-§21.

V2: Copies the template RDR shape from the original WK00 Excel (§19(2)),
    then injects clones into xl/drawings/drawing2.xml at each annotation position.
    Images are NEVER modified — shapes overlay on top (§19(1)).

V1 (--preview only): PIL image overlay for visual review before production run.

Usage:
    python3 scripts/annotate_receipts.py WK09_2026              # V2: inject Excel shapes
    python3 scripts/annotate_receipts.py --preview WK09_2026     # V1: PIL preview images
"""

import copy
import json
import sys
import os
import io
import zipfile
from PIL import Image, ImageDraw
from lxml import etree


# ─── Constants ────────────────────────────────────────────────────────

NS_XDR = "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing"
NS_A = "http://schemas.openxmlformats.org/drawingml/2006/main"
NS_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


# ─── Per-Image Anchor Calibration ────────────────────────────────────
#
# Each image's own twoCellAnchor (from/to + xfrm) provides enough data
# to compute cell coordinates without a global EMU grid.
# This avoids cross-image xfrm inconsistencies and hardcoded column widths.

def _per_image_pixel_to_cell(px, py, img_w, img_h, anchor):
    """Convert pixel coords to cell coords using the image's own anchor data.

    Derives avg column width and row height from the image's from/to/xfrm,
    then walks from the 'from' cell to find the target cell.
    No global cumulative grid needed — immune to cross-image inconsistencies.
    """
    fc = anchor['from'].get('col', 0)
    fco = anchor['from'].get('colOff', 0)
    fr = anchor['from'].get('row', 0)
    fro = anchor['from'].get('rowOff', 0)
    tc = anchor['to'].get('col', 0)
    tco = anchor['to'].get('colOff', 0)
    tr = anchor['to'].get('row', 0)
    tro = anchor['to'].get('rowOff', 0)
    cx = anchor['xfrm']['cx']
    cy = anchor['xfrm']['cy']

    col_span = tc - fc
    row_span = tr - fr
    avg_col_w = (cx + fco - tco) / col_span if col_span > 0 else cx
    avg_row_h = (cy + fro - tro) / row_span if row_span > 0 else cy

    # pixel → EMU offset from image top-left
    dx = (px / img_w) * cx
    dy = (py / img_h) * cy

    # Walk columns from (fc, fco)
    first_col_remain = avg_col_w - fco
    if dx <= first_col_remain:
        res_col = fc
        res_col_off = int(fco + dx)
    else:
        remaining = dx - first_col_remain
        full_cols = int(remaining / avg_col_w)
        res_col = fc + 1 + full_cols
        res_col_off = int(remaining - full_cols * avg_col_w)

    # Walk rows from (fr, fro)
    first_row_remain = avg_row_h - fro
    if dy <= first_row_remain:
        res_row = fr
        res_row_off = int(fro + dy)
    else:
        remaining = dy - first_row_remain
        full_rows = int(remaining / avg_row_h)
        res_row = fr + 1 + full_rows
        res_row_off = int(remaining - full_rows * avg_row_h)

    return res_col, res_col_off, res_row, res_row_off


# ─── Drawing XML Parsing ─────────────────────────────────────────────

def _parse_image_anchors(drawing_xml_bytes, rels_xml_bytes):
    """Parse drawing2.xml + rels to build image_filename → anchor mapping.

    Returns: {image_filename: {from, to, xfrm, rid}} where xfrm = {x, y, cx, cy}
    """
    # Parse rels: rId → image filename
    rels_root = etree.fromstring(rels_xml_bytes)
    rid_to_img = {}
    for rel in rels_root:
        rid = rel.get('Id', '')
        target = rel.get('Target', '')
        if 'image' in target.lower():
            rid_to_img[rid] = target.split('/')[-1]

    # Parse drawing: find picture anchors
    root = etree.fromstring(drawing_xml_bytes)
    anchors = {}

    for anchor_el in root:
        if 'twoCellAnchor' not in anchor_el.tag:
            continue

        # Find <pic> element
        pic_el = None
        for child in anchor_el:
            tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
            if tag == 'pic':
                pic_el = child
                break
        if pic_el is None:
            continue

        # Get rId from blip
        blip = pic_el.find(f'.//{{{NS_A}}}blip')
        if blip is None:
            continue
        rid = blip.get(f'{{{NS_R}}}embed', '')
        img_fname = rid_to_img.get(rid)
        if not img_fname:
            continue

        # Parse from/to
        def parse_cell(el_tag):
            for el in anchor_el:
                t = el.tag.split('}')[-1] if '}' in el.tag else el.tag
                if t == el_tag:
                    vals = {}
                    for ch in el:
                        ct = ch.tag.split('}')[-1] if '}' in ch.tag else ch.tag
                        vals[ct] = int(ch.text or 0)
                    return vals
            return {}

        from_cell = parse_cell('from')
        to_cell = parse_cell('to')

        # Parse xfrm (off + ext)
        xfrm_el = pic_el.find(f'.//{{{NS_A}}}xfrm')
        xfrm = {'x': 0, 'y': 0, 'cx': 0, 'cy': 0}
        if xfrm_el is not None:
            off_el = xfrm_el.find(f'{{{NS_A}}}off')
            ext_el = xfrm_el.find(f'{{{NS_A}}}ext')
            if off_el is not None:
                xfrm['x'] = int(off_el.get('x', 0))
                xfrm['y'] = int(off_el.get('y', 0))
            if ext_el is not None:
                xfrm['cx'] = int(ext_el.get('cx', 0))
                xfrm['cy'] = int(ext_el.get('cy', 0))

        anchors[img_fname] = {
            'from': from_cell, 'to': to_cell, 'xfrm': xfrm, 'rid': rid
        }

    return anchors, root


# ─── Shape XML Builder (§19(2): copy template RDR) ───────────────────

def _get_max_shape_id(root):
    """Find the maximum cNvPr id in the drawing to avoid conflicts."""
    max_id = 0
    for el in root.iter():
        tag = el.tag.split('}')[-1] if '}' in el.tag else el.tag
        if tag == 'cNvPr':
            try:
                max_id = max(max_id, int(el.get('id', 0)))
            except ValueError:
                pass
    return max_id


def _extract_template_rdr(input_xlsx_path):
    """Extract the template RDR shape (직사각형 2) from the original WK00 file.

    Per PRD §19(2): the original Excel has a pre-made RDR shape in the
    PARKING/TOLLS section of the Receipt sheet. We copy this shape's XML
    as the template for all annotation shapes.

    Returns: lxml Element (the full twoCellAnchor element containing the shape).
    """
    with zipfile.ZipFile(input_xlsx_path, 'r') as z:
        drawing_xml = z.read('xl/drawings/drawing2.xml')

    root = etree.fromstring(drawing_xml)
    for anchor in root:
        if 'twoCellAnchor' not in anchor.tag:
            continue
        # Find <sp> (not <pic>)
        for child in anchor:
            tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
            if tag == 'sp':
                # Check for red dashed line (RDR signature)
                has_red = any(el.get('val') == 'FF0000'
                             for el in anchor.iter()
                             if el.tag.endswith('}srgbClr'))
                has_dash = any(el.get('val') == 'sysDash'
                              for el in anchor.iter()
                              if el.tag.endswith('}prstDash'))
                if has_red and has_dash:
                    print(f"  Template RDR found in input file")
                    return copy.deepcopy(anchor)

    raise RuntimeError("Template RDR shape not found in input file (§19(2))")


def _clone_rdr_shape(template_anchor, shape_id, from_cell, to_cell):
    """Clone the template RDR and reposition it at the given cell coordinates.

    from_cell/to_cell: (col, colOff, row, rowOff) tuples.
    """
    clone = copy.deepcopy(template_anchor)
    fc, fco, fr, fro = from_cell
    tc, tco, tr, tro = to_cell

    # Update from/to coordinates
    for el in clone:
        tag = el.tag.split('}')[-1] if '}' in el.tag else el.tag
        if tag == 'from':
            for ch in el:
                ct = ch.tag.split('}')[-1] if '}' in ch.tag else ch.tag
                if ct == 'col': ch.text = str(fc)
                elif ct == 'colOff': ch.text = str(fco)
                elif ct == 'row': ch.text = str(fr)
                elif ct == 'rowOff': ch.text = str(fro)
        elif tag == 'to':
            for ch in el:
                ct = ch.tag.split('}')[-1] if '}' in ch.tag else ch.tag
                if ct == 'col': ch.text = str(tc)
                elif ct == 'colOff': ch.text = str(tco)
                elif ct == 'row': ch.text = str(tr)
                elif ct == 'rowOff': ch.text = str(tro)

    # Update shape id and name
    for el in clone.iter():
        tag = el.tag.split('}')[-1] if '}' in el.tag else el.tag
        if tag == 'cNvPr':
            el.set('id', str(shape_id))
            el.set('name', f'RDR_{shape_id}')
            break

    return clone


# ─── V2: XML Shape Injection ─────────────────────────────────────────

def inject_shapes(xlsx_path, annotations_map, input_xlsx_path=None):
    """Inject Red Dotted Rectangle shapes into Excel drawing XML.

    Per PRD §19: copies the template RDR shape from the original WK00 file,
    then clones it at each annotation position. Images are never modified.

    input_xlsx_path: path to the original WK00 template (for extracting the RDR shape).
    """
    tmp_path = xlsx_path + '.tmp'
    shape_count = 0

    # §19(2): Extract template RDR from original input file
    if input_xlsx_path is None:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        # Auto-detect: find WK*_2026 input directory
        input_dir = os.path.join(base_dir, 'raw-data', 'input')
        for d in sorted(os.listdir(input_dir)):
            candidate = os.path.join(input_dir, d, 'simon_park_T&E_WK00_2026.xlsx')
            if os.path.exists(candidate):
                input_xlsx_path = candidate
                break
    if not input_xlsx_path:
        raise FileNotFoundError("Cannot find original WK00 template for RDR extraction")

    template_rdr = _extract_template_rdr(input_xlsx_path)

    with zipfile.ZipFile(xlsx_path, 'r') as z:
        # 1. Read drawing2.xml + rels
        drawing_path = 'xl/drawings/drawing2.xml'
        rels_path = 'xl/drawings/_rels/drawing2.xml.rels'
        drawing_xml = z.read(drawing_path)
        rels_xml = z.read(rels_path)

        # 2. Parse image anchors (per-image calibration source)
        img_anchors, drawing_root = _parse_image_anchors(drawing_xml, rels_xml)
        print(f"  Parsed {len(img_anchors)} image anchors")

        # 3. Get max existing shape ID
        next_id = _get_max_shape_id(drawing_root) + 1

        # 4. For each annotation, convert pixel → cell coords using per-image anchor
        for img_name, bboxes in annotations_map.items():
            anchor = img_anchors.get(img_name)
            if not anchor:
                print(f"  WARNING: No anchor for {img_name}, skipping")
                continue

            # Get image pixel dimensions
            img_data = z.read(f'xl/media/{img_name}')
            img = Image.open(io.BytesIO(img_data))
            img_w, img_h = img.size

            for bbox in bboxes:
                px1, py1, px2, py2 = bbox

                from_cell = _per_image_pixel_to_cell(px1, py1, img_w, img_h, anchor)
                to_cell = _per_image_pixel_to_cell(px2, py2, img_w, img_h, anchor)

                shape_el = _clone_rdr_shape(template_rdr, next_id, from_cell, to_cell)
                drawing_root.append(shape_el)
                next_id += 1
                shape_count += 1

            print(f"  {img_name}: {len(bboxes)} shapes injected")

        # 5. Serialize modified drawing XML
        modified_drawing = etree.tostring(
            drawing_root, xml_declaration=True,
            encoding='UTF-8', standalone=True, pretty_print=True
        )

        # 6. Write new ZIP with modified drawing2.xml
        with zipfile.ZipFile(tmp_path, 'w') as zout:
            for item in z.infolist():
                if item.filename == drawing_path:
                    zout.writestr(item, modified_drawing)
                else:
                    zout.writestr(item, z.read(item.filename))

    os.replace(tmp_path, xlsx_path)
    print(f"  Total: {shape_count} RDR shapes injected (images preserved)")
    return shape_count


# ─── V1: PIL Drawing (preview only) ──────────────────────────────────

def draw_dashed_line(draw, start, end, color=(255, 0, 0), dash_len=8, gap_len=5, width=2):
    """Draw a dashed line from start to end."""
    x1, y1 = start
    x2, y2 = end
    dx = x2 - x1
    dy = y2 - y1
    length = (dx ** 2 + dy ** 2) ** 0.5
    if length == 0:
        return
    ux, uy = dx / length, dy / length
    pos = 0
    while pos < length:
        dash_end = min(pos + dash_len, length)
        sx = x1 + ux * pos
        sy = y1 + uy * pos
        ex = x1 + ux * dash_end
        ey = y1 + uy * dash_end
        draw.line([(int(sx), int(sy)), (int(ex), int(ey))], fill=color, width=width)
        pos += dash_len + gap_len


def draw_dashed_rectangle(img, bbox, color=(255, 0, 0), dash_len=8, gap_len=5, width=2):
    """Draw a dashed rectangle on an image."""
    draw = ImageDraw.Draw(img)
    x1, y1, x2, y2 = bbox
    draw_dashed_line(draw, (x1, y1), (x2, y1), color, dash_len, gap_len, width)
    draw_dashed_line(draw, (x2, y1), (x2, y2), color, dash_len, gap_len, width)
    draw_dashed_line(draw, (x2, y2), (x1, y2), color, dash_len, gap_len, width)
    draw_dashed_line(draw, (x1, y2), (x1, y1), color, dash_len, gap_len, width)


def annotate_image_bytes(data, bboxes):
    """Annotate an image (bytes) with dashed rectangles. Returns PNG bytes."""
    img = Image.open(io.BytesIO(data))
    if img.mode in ('P', 'L'):
        img = img.convert('RGBA')
    for bbox in bboxes:
        draw_dashed_rectangle(img, bbox)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()


def preview_annotations(xlsx_path, annotations_map, preview_dir):
    """Save annotated images to a directory for visual review (V1 PIL)."""
    os.makedirs(preview_dir, exist_ok=True)
    with zipfile.ZipFile(xlsx_path, 'r') as z:
        for img_name, bboxes in annotations_map.items():
            zip_path = f"xl/media/{img_name}"
            if zip_path not in z.namelist():
                print(f"  WARNING: {img_name} not found in Excel")
                continue
            data = z.read(zip_path)
            annotated = annotate_image_bytes(data, bboxes)
            out_path = os.path.join(preview_dir, f"annotated_{img_name}")
            with open(out_path, 'wb') as f:
                f.write(annotated)
            print(f"  Preview: {out_path} ({len(bboxes)} rectangles)")


# ─── Annotation Configurations ────────────────────────────────────────

# WK07_2026 annotations
# image2  (742x385): Toll history "기간별 사용내역" — §19(1) date groups
# image3  (282x578): Parking receipt 센트럴파크 — §19(1)
# image4  (353x825): Spot Mart 2026-02-09 21:29 8,400 — Mon DINNER §19(2)
# image5  (348x633): Starbucks 2026-02-09 13:27 23,400 — Mon TRAVEL §19(4)
# image6  (352x777): Pandora 2026-02-10 20:54 10,000 — Tue DINNER §19(2)
# image7  (344x526): Starbucks 2026-02-11 18:51 10,900 — Wed DINNER §19(2)
# image8  (347x586): Paris Baguette 2026-02-11 08:54 7,290 — Wed TRAVEL §19(4)
# image9  (377x749): 까치화방 2026-02-12 10:10 12,500 — Thu TRAVEL §19(4)
# image10 (371x782): Spot Mart 2026-02-12 20:05 9,500 — Thu DINNER §19(2)
# image11 (413x600): 폴 바셋 2026-02-09 09:08 5,500 — Mon STAFF §19(3)
# image12 (743x827): SK Telecom phone bill — TELEPHONE §19(5)

WK07_ANNOTATIONS = {
    "image2.png": [
        (3, 155, 739, 205),
        (3, 205, 739, 258),
        (3, 258, 739, 313),
        (3, 313, 739, 375),
    ],
    "image3.png": [
        (12, 272, 270, 294),
        (12, 398, 270, 420),
    ],
    "image4.png": [
        (8, 178, 345, 200),
        (8, 348, 345, 382),
    ],
    "image5.png": [
        (8, 100, 340, 120),
        (8, 248, 340, 282),
    ],
    "image6.png": [
        (8, 198, 344, 220),
        (8, 365, 344, 398),
    ],
    "image7.png": [
        (8, 96, 336, 115),
        (8, 235, 336, 268),
    ],
    "image8.png": [
        (8, 143, 339, 165),
        (8, 440, 339, 468),
    ],
    "image9.png": [
        (8, 175, 370, 198),
        (8, 438, 370, 465),
    ],
    "image10.png": [
        (8, 175, 363, 200),
        (8, 345, 363, 380),
    ],
    "image11.png": [
        (8, 93, 405, 115),
        (8, 345, 405, 375),
    ],
    "image12.png": [
        (32, 96, 90, 115),
        (95, 96, 208, 115),
        (190, 245, 345, 290),
        (440, 235, 720, 258),
    ],
}

# WK06_2026 annotations (grid-calibrated)
WK06_ANNOTATIONS = {
    "image2.png": [
        (8, 98, 325, 120),
        (8, 255, 325, 290),
    ],
    "image3.png": [
        (8, 125, 341, 148),
        (8, 398, 341, 425),
    ],
    "image4.png": [
        (8, 190, 333, 212),
        (8, 345, 333, 378),
    ],
    "image5.png": [
        (8, 193, 330, 218),
        (8, 338, 330, 370),
    ],
    "image6.png": [
        (8, 146, 330, 168),
        (8, 428, 330, 458),
    ],
    "image7.png": [
        (8, 98, 400, 120),
        (8, 345, 400, 375),
    ],
    "image8.png": [
        (8, 98, 372, 120),
        (8, 722, 372, 750),
    ],
    "image9.png": [
        (8, 98, 406, 120),
        (8, 675, 406, 705),
    ],
    "image10.png": [
        (3, 153, 740, 207),
        (3, 207, 740, 282),
        (3, 282, 740, 310),
        (3, 310, 740, 370),
    ],
}

# WK08_2026 annotations (grid-calibrated)
WK08_ANNOTATIONS = {
    "image5.png": [
        (3, 155, 740, 208),
        (3, 208, 740, 288),
    ],
    "image2.png": [
        (8, 198, 288, 222),
        (8, 298, 288, 325),
    ],
    "image3.png": [
        (8, 118, 306, 142),
        (8, 370, 306, 398),
    ],
    "image4.png": [
        (8, 118, 300, 142),
        (8, 374, 300, 402),
    ],
}

# WK09_2026 annotations — Excel internal image names (verified against input template)
# Mapping: annotation names from extract_images.py → Excel internal xl/media/ names
# image14.png (746x441):  Toll history "기간별 사용내역" — §20(1), row 0 col 6
# image6.png  (554x1084): Parking 트릴파크 (02/27, 5000) — §20(1), row 34
# image2.png  (666x1290): Dinner 아디지/보나비 (02/24, 10200) — §20(2), row 126
# image7.png  (694x1172): Dinner Spot Mart (02/25, 11300) — §20(2), row 126
# image3.png  (646x700):  Staff Starbucks (02/24, 9700) — §20(3), row 306
# image4.png  (700x818):  Staff Starbucks (02/25, 9500) — §20(3), row 306
# image11.png (780x1080): Staff 폴 바셋 평택 (02/25, 14200) — §20(3), row 305
# image8.png  (758x1898): Travel 폴 바셋 DSR (02/23 Mon, 26300) — §20(4), row 406
# image9.png  (734x1470): Travel 폴 바셋 DSR (02/24 Tue, 16800) — §20(4), row 407
# image10.png (806x1384): Travel 폴 바셋 DSR (02/25 Wed, 10800) — §20(4), row 408
# image12.png (756x1704): Travel 폴 바셋 DSR (02/26 Thu, 23400) — §20(4), row 480
# image5.png  (758x1524): Travel 까치지맘방 (02/27 Fri, 20900) — §20(4), row 479
# image13.png (766x1414): Travel 폴 바셋 평택 (02/27 Fri, 15200) — §20(4), row 480
WK09_ANNOTATIONS = {
    # §20(1) PARKING/TOLLS — toll history date groups (746x441, 10 rows, 5 dates)
    "image14.png": [
        (3, 137, 743, 221),    # Feb 23 Mon (3 entries: rows 10-8)
        (3, 221, 743, 277),    # Feb 24 Tue (2 entries: rows 7-6)
        (3, 277, 743, 333),    # Feb 25 Wed (2 entries: rows 5-4)
        (3, 333, 743, 361),    # Feb 26 Thu (1 entry: row 3)
        (3, 361, 743, 417),    # Feb 27 Fri (2 entries: rows 2-1)
    ],
    # §20(1) PARKING — 트릴파크 parking receipt (554x1084): 진입일시 + 결제금액
    "image6.png": [
        (12, 488, 540, 522),   # 입: 2026.02.27 09:04
        (12, 660, 540, 698),   # 결: 5,000 원
    ],
    # §20(2) DINNER — 아디지/보나비 Tue (666x1290): 일시 + 결제금액
    "image2.png": [
        (8, 490, 658, 530),    # 2026. 02. 24 18:54
        (8, 870, 658, 910),    # 신용카드 10,200
    ],
    # §20(2) DINNER — Spot Mart Wed (694x1172): 일시 + 결제금액
    "image7.png": [
        (8, 298, 686, 332),    # [등록] 2026/02/25(수) 19:33
        (8, 538, 686, 578),    # 합 계 11,300 원
    ],
    # §20(3) STAFF — Starbucks Tue (646x700): 일시 + 결제금액
    "image3.png": [
        (8, 128, 638, 155),    # [매장#4423 POS 02] 2026-02-24 12:53:38
        (8, 428, 638, 470),    # 결 제 금 액 9,700
    ],
    # §20(3) STAFF — Starbucks Wed 2nd (700x818): 일시 + 결제금액
    "image4.png": [
        (8, 142, 692, 172),    # [매장#4423 POS 02] 2026-02-25 14:44:58
        (8, 510, 692, 555),    # 결 제 금 액 9,500
    ],
    # §20(3) STAFF — 폴 바셋 평택 Wed 1st (780x1080): 일시 + 총 결제금액
    "image11.png": [
        (8, 188, 772, 225),    # 2026/02/25 10:19:11(수)
        (8, 575, 772, 618),    # 총 결제금액 14,200
    ],
    # §20(4) TRAVEL — 폴 바셋 DSR Mon (758x1898): 일시 + 총 결제금액
    "image8.png": [
        (8, 175, 750, 212),    # 2026/02/23 09:16:18(월)
        (8, 1454, 750, 1494),  # 총 결제금액 26,300
    ],
    # §20(4) TRAVEL — 폴 바셋 DSR Tue (734x1470): 일시 + 총 결제금액
    "image9.png": [
        (8, 175, 726, 212),    # 2026/02/24 09:29:08(화)
        (8, 1026, 726, 1066),  # 총 결제금액 16,800
    ],
    # §20(4) TRAVEL — 폴 바셋 DSR Wed (806x1384): 일시 + 총 결제금액
    "image10.png": [
        (8, 180, 798, 218),    # 2026/02/25 09:17:57(수)
        (8, 885, 798, 925),    # 총 결제금액 10,800
    ],
    # §20(4) TRAVEL — 폴 바셋 DSR Thu (756x1704): 일시 + 총 결제금액
    "image12.png": [
        (8, 175, 748, 212),    # 2026/02/26 09:25:39(목)
        (8, 1260, 748, 1300),  # 총 결제금액 23,400
    ],
    # §20(4) TRAVEL — 까치지맘방 Fri (758x1524): 일시 + 판매금액
    "image5.png": [
        (8, 140, 750, 175),    # 2026-02-27 09:55
        (8, 570, 750, 610),    # 판매금액 20,900
    ],
    # §20(4) TRAVEL — 폴 바셋 평택 Fri (766x1414): 일시 + 총 결제금액
    "image13.png": [
        (8, 188, 758, 225),    # 2026/02/27 11:22:42(금)
        (8, 964, 758, 1007),   # 총 결제금액 15,200
    ],
}


# ─── Main ─────────────────────────────────────────────────────────────

WEEK_ANNOTATIONS = {
    "WK06_2026": WK06_ANNOTATIONS,
    "WK07_2026": WK07_ANNOTATIONS,
    "WK08_2026": WK08_ANNOTATIONS,
    "WK09_2026": WK09_ANNOTATIONS,
}


def _load_annotations_json(week, base_dir):
    """Load annotations from JSON file (research/annotations/wk**.json).

    Returns dict {image_name: [(x1,y1,x2,y2), ...]} or None if not found.
    JSON files are auto-generated by generate_annotations.py + Claude vision.
    """
    wk_num = week.replace("_2026", "").replace("WK", "").lower()
    json_path = os.path.join(base_dir, "research", "annotations", f"wk{wk_num}.json")
    if not os.path.exists(json_path):
        return None

    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    annotations = {}
    for img_name, info in data.get("images", {}).items():
        bboxes = info.get("bboxes", [])
        if bboxes:
            annotations[img_name] = [
                tuple(b["coords"]) if isinstance(b, dict) else tuple(b)
                for b in bboxes
            ]

    if annotations:
        print(f"  Loaded annotations from JSON: {json_path}")
        print(f"  Images: {len(annotations)}, Rectangles: {sum(len(v) for v in annotations.values())}")
    return annotations if annotations else None


# ─── P0-1: Deterministic bbox sanity-check guard ──────────────────────
# Rule source: PRD §20 / WK_workflow.md Step 6 / wk.md phase3. Previously
# enforced only in prompt text — MEMORY records WK09 over-generating 83
# bboxes (normal ~29). This code makes the rule deterministic (절대 기준 1).

# Sections where every receipt image must carry exactly 2 bboxes
# (일시 + 결제금액). 0 is allowed: image legitimately skipped (non-receipt).
_STRICT_2BBOX_SECTIONS = {"DINNER", "STAFF", "TRAVEL", "PARKING"}
_BBOX_GLOBAL_HARD_CAP = 80      # > this → spec violation (WK09 bug produced 83)
_BBOX_GLOBAL_WARN = 50          # > this → warn (expected ~25-35)
_BBOX_TOLLS_PER_IMAGE_CAP = 10  # sanity cap for a single TOLLS image


def _distinct_toll_dates(base_dir):
    """Best-effort: distinct toll dates from ocr-results.json (TOLLS bound).
    Returns int or None when unavailable."""
    p = os.path.join(base_dir, "research", "ocr-results.json")
    if not os.path.exists(p):
        return None
    try:
        with open(p, "r", encoding="utf-8") as f:
            ocr = json.load(f)
        dates = {t.get("date")
                 for t in ocr.get("parking_tolls", {}).get("toll_history", [])}
        dates.discard(None)
        return len(dates) or None
    except Exception:
        return None


def _load_annotations_raw(week, base_dir):
    """Load raw images dict from wk**.json (keeps section/bboxes/dims).
    Returns dict, or None if the JSON file is absent (hardcoded-fallback)."""
    wk_num = week.replace("_2026", "").replace("WK", "").lower()
    json_path = os.path.join(base_dir, "research", "annotations",
                             f"wk{wk_num}.json")
    if not os.path.exists(json_path):
        return None
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f).get("images", {})


def validate_bbox_counts(images_raw, toll_dates=None):
    """Deterministic bbox sanity-check (§20).

    Returns (violations, warnings) — lists of str.
    violations = hard spec breach (block). warnings = review only.
    """
    violations, warnings = [], []
    total = 0
    for name, info in (images_raw or {}).items():
        section = (info.get("section") or "").upper()
        n = len(info.get("bboxes", []) or [])
        total += n
        dims = (info.get("dims") or [0, 0]) + [0, 0]
        w, h = dims[0], dims[1]

        # Logo/small images should have been filtered by generate_annotations.py
        if n > 0 and w and h and w < 200 and h < 100:
            violations.append(
                f"{name}: {n} bbox on logo/small image ({w}x{h}) — "
                f"must be excluded (§20)")
            continue

        if section in _STRICT_2BBOX_SECTIONS:
            if n not in (0, 2):
                violations.append(
                    f"{name} [{section}]: {n} bboxes — expected exactly 2 "
                    f"(일시+결제금액), or 0 if skipped (§20)")
        elif section == "TELEPHONE":
            if n not in (0, 4, 8):  # 4 per page, up to 2 pages
                warnings.append(
                    f"{name} [TELEPHONE]: {n} bboxes — expected 4/page (§20(5))")
        elif section == "TOLLS":
            if n > _BBOX_TOLLS_PER_IMAGE_CAP:
                violations.append(
                    f"{name} [TOLLS]: {n} bboxes exceeds per-image cap "
                    f"{_BBOX_TOLLS_PER_IMAGE_CAP}")
            elif toll_dates is not None and n > toll_dates:
                warnings.append(
                    f"{name} [TOLLS]: {n} bboxes > {toll_dates} distinct toll "
                    f"dates — possible over-segmentation")

    if total > _BBOX_GLOBAL_HARD_CAP:
        violations.append(
            f"TOTAL {total} bboxes exceeds hard cap {_BBOX_GLOBAL_HARD_CAP} "
            f"— spec violation (expected ~25-35)")
    elif total > _BBOX_GLOBAL_WARN:
        warnings.append(
            f"TOTAL {total} bboxes > {_BBOX_GLOBAL_WARN} — review (~25-35)")

    return violations, warnings


def _run_bbox_guard(week, base_dir, hard):
    """Run guard against wk**.json. Returns True if OK to proceed.

    hard=True: violations → return False (caller exits 1, triggers Step 6 redo).
    hard=False (hardcoded fallback): violations downgraded to warnings.
    """
    images_raw = _load_annotations_raw(week, base_dir)
    if images_raw is None:
        print("  bbox guard: no JSON (hardcoded fallback) — skipped")
        return True
    violations, warnings = validate_bbox_counts(
        images_raw, _distinct_toll_dates(base_dir))
    for msg in warnings:
        print(f"  bbox guard WARNING: {msg}")
    if violations:
        if hard:
            print("  bbox sanity-check FAILED:")
            for v in violations:
                print(f"    ✗ {v}")
            return False
        for v in violations:
            print(f"  bbox guard WARNING (fallback): {v}")
    else:
        print("  bbox sanity-check PASSED")
    return True


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/annotate_receipts.py "
              "[--preview|--generate|--check-only] WK06_2026|...")
        sys.exit(1)

    preview = "--preview" in sys.argv
    generate = "--generate" in sys.argv
    check_only = "--check-only" in sys.argv
    force = "--force" in sys.argv
    week = [a for a in sys.argv[1:] if not a.startswith("--")][0]

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # --check-only: run the deterministic bbox guard and exit (CI/regression).
    if check_only:
        ok = _run_bbox_guard(week, base_dir, hard=True)
        sys.exit(0 if ok else 1)

    # --generate: delegate to generate_annotations.py
    if generate:
        import subprocess
        gen_script = os.path.join(base_dir, "scripts", "generate_annotations.py")
        sys.exit(subprocess.call([sys.executable, gen_script, week]))

    wk_num = week.replace("_2026", "").replace("WK", "")
    xlsx_name = f"simon_park_T&E_WK{wk_num}_2026.xlsx"
    xlsx_path = os.path.join(base_dir, "raw-data", "output", xlsx_name)

    if not os.path.exists(xlsx_path):
        print(f"ERROR: {xlsx_path} not found")
        sys.exit(1)

    # Priority: JSON file > hardcoded dict
    annotations = _load_annotations_json(week, base_dir)
    from_json = annotations is not None
    if annotations is None:
        annotations = WEEK_ANNOTATIONS.get(week)
        if annotations:
            print(f"  Using hardcoded annotations (fallback)")

    if not annotations:
        print(f"ERROR: No annotations found for {week}")
        print(f"  Run: python3 scripts/annotate_receipts.py --generate {week}")
        sys.exit(1)

    total_rects = sum(len(v) for v in annotations.values())
    print(f"Processing {week}: {xlsx_path}")
    print(f"  Images: {len(annotations)}, Rectangles: {total_rects}")

    # P0-1: deterministic bbox sanity-check before injection.
    # JSON path → hard (block + exit 1 so Step 6 is redone).
    # Hardcoded fallback → soft (legacy, warnings only). --force bypasses.
    if not preview and not force:
        if not _run_bbox_guard(week, base_dir, hard=from_json):
            print("  Aborting injection. Fix Step 6 bboxes, or pass "
                  "--force to override.")
            sys.exit(1)

    if preview:
        preview_dir = os.path.join(base_dir, "research", f"{week.lower()}_preview")
        preview_annotations(xlsx_path, annotations, preview_dir)
        print(f"  Preview saved to: {preview_dir}")
    else:
        # §19(2): Locate the original WK00 template for RDR shape extraction
        input_dir = os.path.join(base_dir, "raw-data", "input", week)
        input_xlsx = os.path.join(input_dir, "simon_park_T&E_WK00_2026.xlsx")
        if not os.path.exists(input_xlsx):
            print(f"ERROR: Input template not found: {input_xlsx}")
            sys.exit(1)

        count = inject_shapes(xlsx_path, annotations, input_xlsx_path=input_xlsx)
        print(f"  Done. {xlsx_path} updated with {count} RDR shapes (§19 template copy).")


if __name__ == "__main__":
    main()
