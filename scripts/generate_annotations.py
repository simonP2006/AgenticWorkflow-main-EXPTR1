#!/usr/bin/env python3
"""
generate_annotations.py — Extract receipt images + generate annotation template JSON.

Per PRD §19-§21: Automates the preparation step for RDR annotation.
Extracts images from the input Excel, classifies by section, and outputs
a template JSON for Claude to fill in pixel coordinates.

Usage:
    python3 scripts/generate_annotations.py WK09_2026
    python3 scripts/generate_annotations.py WK10_2026
"""

import json
import io
import os
import sys
import zipfile
from datetime import datetime
from lxml import etree
from PIL import Image


# Section classification by from_row in Receipt sheet drawing2.xml
SECTION_BOUNDARIES = [
    (0, 30, "TOLLS"),
    (30, 120, "PARKING"),
    (120, 300, "DINNER"),
    (300, 400, "STAFF"),
    (400, 550, "TRAVEL"),
    (550, 9999, "TELEPHONE"),
]

NS_A = "http://schemas.openxmlformats.org/drawingml/2006/main"
NS_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def classify_section(from_row):
    """Classify image section by its row position in Receipt sheet."""
    for low, high, name in SECTION_BOUNDARIES:
        if low <= from_row < high:
            return name
    return "UNKNOWN"


def extract_and_classify(input_xlsx_path, week):
    """Extract receipt images, classify by section, generate template JSON."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    wk_num = week.replace("_2026", "").replace("WK", "").lower()
    ann_dir = os.path.join(base_dir, "research", "annotations")
    img_dir = os.path.join(ann_dir, f"wk{wk_num}-images")
    os.makedirs(img_dir, exist_ok=True)

    with zipfile.ZipFile(input_xlsx_path, 'r') as z:
        # 1. Parse drawing2.xml rels → rId→image mapping
        rels_data = z.read('xl/drawings/_rels/drawing2.xml.rels')
        rels_root = etree.fromstring(rels_data)
        rid_to_img = {}
        for rel in rels_root:
            rid = rel.get('Id', '')
            target = rel.get('Target', '')
            if 'image' in target.lower():
                rid_to_img[rid] = target.split('/')[-1]

        # 2. Parse drawing2.xml → image anchors
        drawing_data = z.read('xl/drawings/drawing2.xml')
        drawing_root = etree.fromstring(drawing_data)

        images = {}
        for anchor in drawing_root:
            if 'twoCellAnchor' not in anchor.tag:
                continue

            # Find <pic> element
            pic_el = None
            for child in anchor:
                tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
                if tag == 'pic':
                    pic_el = child
                    break
            if pic_el is None:
                continue

            # Get rId
            blip = pic_el.find(f'.//{{{NS_A}}}blip')
            if blip is None:
                continue
            rid = blip.get(f'{{{NS_R}}}embed', '')
            img_fname = rid_to_img.get(rid)
            if not img_fname:
                continue

            # Get from_row, from_col
            from_row = from_col = 0
            for el in anchor:
                tag = el.tag.split('}')[-1] if '}' in el.tag else el.tag
                if tag == 'from':
                    for ch in el:
                        ct = ch.tag.split('}')[-1] if '}' in ch.tag else ch.tag
                        if ct == 'row':
                            from_row = int(ch.text or 0)
                        elif ct == 'col':
                            from_col = int(ch.text or 0)

            # Get image pixel dimensions
            img_data = z.read(f'xl/media/{img_fname}')
            img = Image.open(io.BytesIO(img_data))
            w, h = img.size

            # Skip tiny images (logos, icons)
            if w < 200 or h < 100:
                continue

            # Classify section
            section = classify_section(from_row)

            # Save image to annotation images dir
            out_path = os.path.join(img_dir, img_fname)
            with open(out_path, 'wb') as f:
                f.write(img_data)

            images[img_fname] = {
                "section": section,
                "description": "",
                "dims": [w, h],
                "from_row": from_row,
                "from_col": from_col,
                "bboxes": []
            }

            print(f"  {img_fname:15s} {w:4d}x{h:<4d} row={from_row:3d} col={from_col:2d} → {section}")

    # 3. Sort by section order, then by row
    section_order = ["TOLLS", "PARKING", "DINNER", "STAFF", "TRAVEL", "TELEPHONE"]
    sorted_images = dict(sorted(
        images.items(),
        key=lambda x: (section_order.index(x[1]["section"]) if x[1]["section"] in section_order else 99,
                        x[1]["from_row"], x[1]["from_col"])
    ))

    # 4. Generate template JSON
    template = {
        "week": week,
        "generated_at": datetime.now().isoformat(),
        "generated_by": "generate_annotations.py",
        "note": "Fill in bboxes: [x1, y1, x2, y2] pixel coordinates for date and amount regions",
        "images": sorted_images,
    }

    template_path = os.path.join(ann_dir, f"wk{wk_num}-template.json")
    with open(template_path, 'w', encoding='utf-8') as f:
        json.dump(template, f, indent=2, ensure_ascii=False)

    print(f"\n  Template: {template_path}")
    print(f"  Images:   {img_dir}/ ({len(sorted_images)} receipt images)")
    print(f"\n  Next: Claude reads each image and fills in bboxes → save as wk{wk_num}.json")

    return template_path, img_dir, sorted_images


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/generate_annotations.py WK09_2026")
        sys.exit(1)

    week = sys.argv[1]
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    input_dir = os.path.join(base_dir, "raw-data", "input", week)
    input_xlsx = os.path.join(input_dir, "simon_park_T&E_WK00_2026.xlsx")

    if not os.path.exists(input_xlsx):
        print(f"ERROR: {input_xlsx} not found")
        sys.exit(1)

    print(f"Generating annotation template for {week}")
    extract_and_classify(input_xlsx, week)


if __name__ == "__main__":
    main()
