# ruff: noqa: E501 -- the XML parts are written as one string each.
"""A deck built on the user's PowerPoint template: its slide layouts (title, section, title and
content, …) filled with titles, bullet points at levels, pictures and speaker notes; the
template's own sample slides can be dropped.

Placeholders are written without positions, so they take the layout's position, fonts and
colours; a picture goes into the layout's content area, beside the text when both are given.
"""

from __future__ import annotations

import os
import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from agent_workspace.office import xlsx
from agent_workspace.office.ooxml import A, OfficeError, P, Package, R, escape_attr, escape_text, q

_REL_ID = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
_PRESENTATION = "ppt/presentation.xml"
_SLIDE_TYPE = "application/vnd.openxmlformats-officedocument.presentationml.slide+xml"
_NOTES_TYPE = "application/vnd.openxmlformats-officedocument.presentationml.notesSlide+xml"
_IMAGE_TYPES = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "gif": "image/gif",
    "bmp": "image/bmp",
}
_NS = f'xmlns:a="{A}" xmlns:r="{R}" xmlns:p="{P}"'
_KINDS = {
    "title": ("title", "ctrTitle"),
    "section": ("secHead",),
    "content": ("obj", "tx"),
    "two": ("twoObj", "twoTxTwoObj"),
    "title_only": ("titleOnly",),
    "blank": ("blank",),
}
_NAMES = {
    "title": ("标题幻灯片", "title slide"),
    "section": ("节标题", "section header"),
    "content": ("标题和内容", "title and content"),
    "two": ("两栏内容", "two content"),
    "title_only": ("仅标题", "title only"),
    "blank": ("空白", "blank"),
}
_META = {"dt", "ftr", "sldNum", "hdr"}
_VERTICAL = {"vertTx", "vertTitleAndTx", "vertTitleAndTxOverChart"}


@dataclass
class Placeholder:
    type: str
    idx: str
    box: tuple[int, int, int, int] | None


@dataclass
class Layout:
    part: str
    name: str
    type: str
    placeholders: list[Placeholder] = field(default_factory=list)

    def find(self, *types: str) -> Placeholder | None:
        """The first placeholder of the first type given that the layout has."""
        for wanted in types:
            for placeholder in self.placeholders:
                if placeholder.type == wanted:
                    return placeholder
        return None


def _placeholders(root: ET.Element) -> list[Placeholder]:
    out = []
    for shape in root.iter(q(P, "sp")):
        ph = shape.find(f"{q(P, 'nvSpPr')}/{q(P, 'nvPr')}/{q(P, 'ph')}")
        if ph is None:
            continue
        box = None
        xfrm = shape.find(f"{q(P, 'spPr')}/{q(A, 'xfrm')}")
        if xfrm is not None:
            off, ext = xfrm.find(q(A, "off")), xfrm.find(q(A, "ext"))
            if off is not None and ext is not None:
                box = (
                    int(off.get("x", "0")),
                    int(off.get("y", "0")),
                    int(ext.get("cx", "0")),
                    int(ext.get("cy", "0")),
                )
        out.append(Placeholder(ph.get("type", "obj"), ph.get("idx", ""), box))
    return out


def open_template(data: bytes) -> Package:
    package = Package.read(data)
    if not package.has(_PRESENTATION):
        raise OfficeError("not a PowerPoint file (.pptx or .potx)")
    text = package.text("[Content_Types].xml")
    # A .potx template is saved as a presentation.
    package.set(
        "[Content_Types].xml",
        text.replace("presentationml.template.main+xml", "presentationml.presentation.main+xml"),
    )
    return package


def layouts(package: Package) -> list[Layout]:
    out = []
    for _rid, kind, target in package.relationships(_PRESENTATION):
        if not kind.endswith("/slideMaster"):
            continue
        master = package.resolve(_PRESENTATION, target)
        master_boxes = {
            placeholder.type: placeholder.box
            for placeholder in _placeholders(package.xml(master).root)
        }
        for _lrid, lkind, ltarget in package.relationships(master):
            if not lkind.endswith("/slideLayout"):
                continue
            part = package.resolve(master, ltarget)
            root = package.xml(part).root
            name = root.find(q(P, "cSld"))
            layout = Layout(
                part, name.get("name", "") if name is not None else "", root.get("type", "")
            )
            for placeholder in _placeholders(root):
                if placeholder.box is None:
                    placeholder.box = master_boxes.get(placeholder.type) or master_boxes.get("body")
                layout.placeholders.append(placeholder)
            out.append(layout)
    if not out:
        raise OfficeError("the template has no slide layouts")
    return out


def _content_types(layout: Layout) -> list[str]:
    return [item.type for item in layout.placeholders if item.type not in _META]


def _fits(layout: Layout, kind: str) -> bool:
    """Whether the layout's placeholders suit the kind of slide (templates often leave the
    layout type out, so its placeholders decide)."""
    if layout.type in _VERTICAL:
        return False
    types = _content_types(layout)
    titles = sum(item in ("title", "ctrTitle") for item in types)
    bodies = sum(item in ("body", "obj") for item in types)
    if kind == "title":
        return "ctrTitle" in types or ("title" in types and "subTitle" in types)
    if kind == "section":
        return (
            titles == 1 and types.count("body") == 1 and "obj" not in types and "pic" not in types
        )
    if kind == "two":
        return titles == 1 and bodies == 2
    if kind == "title_only":
        return titles == 1 and bodies == 0 and "pic" not in types and "subTitle" not in types
    if kind == "blank":
        return titles == 0 and bodies == 0
    return False


def choose_layout(available: list[Layout], wanted: str) -> Layout:
    """By layout name (as the template calls it), else by kind: title, section, content, two,
    title_only, blank — the layout's type, its usual names, then its placeholders."""
    for layout in available:
        if wanted and layout.name.casefold() == wanted.casefold():
            return layout
    kind = wanted if wanted in _KINDS else "content"
    for layout_type in _KINDS[kind]:
        for layout in available:
            if layout.type == layout_type:
                return layout
    for name in _NAMES[kind]:
        for layout in available:
            if layout.name.casefold() == name:
                return layout
    if kind == "content":
        ranked = [
            (rank, index)
            for index, layout in enumerate(available)
            if (rank := _content_rank(layout)) is not None
        ]
        if ranked:
            return available[min(ranked)[1]]
        # Nothing made for bullets: any layout with a title and a text area, not a vertical one.
        usable = [
            layout
            for layout in available
            if layout.type not in _VERTICAL and layout.find("title") and layout.find("obj", "body")
        ]
        return usable[0] if usable else available[0]
    for layout in available:
        if _fits(layout, kind):
            return layout
    return choose_layout(available, "title_only" if kind == "section" else "content")


def _content_rank(layout: Layout) -> int | None:
    """How well a layout takes a title and bullet points (lower is better), or None: one content
    area best, then one text area, then a content area beside captions or more areas."""
    other_names = {name for kind, names in _NAMES.items() if kind != "content" for name in names}
    if layout.type in _VERTICAL | {"secHead", "title", "titleOnly", "blank"}:
        return None
    if layout.name.casefold() in other_names:
        return None
    types = _content_types(layout)
    if "ctrTitle" in types or "subTitle" in types or types.count("title") != 1:
        return None
    objects, bodies = types.count("obj"), types.count("body")
    others = len(types) - 1 - objects - bodies
    if objects + bodies == 0:
        return None
    if objects == 1 and bodies == 0 and others == 0:
        return 0
    if bodies == 1 and objects == 0 and others == 0:
        return 1
    if objects == 1:
        return 2 + bodies + others
    return 10 + objects + bodies + others


def _image_size(data: bytes) -> tuple[int, int]:
    if data.startswith(b"\x89PNG"):
        return struct.unpack(">II", data[16:24])
    if data[:2] == b"\xff\xd8":
        index = 2
        while index + 9 < len(data):
            if data[index] != 0xFF:
                index += 1
                continue
            marker = data[index + 1]
            length = struct.unpack(">H", data[index + 2 : index + 4])[0]
            if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
                height, width = struct.unpack(">HH", data[index + 5 : index + 9])
                return width, height
            index += 2 + length
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return struct.unpack("<HH", data[6:10])
    if data[:2] == b"BM":
        width, height = struct.unpack("<ii", data[18:26])
        return width, abs(height)
    raise OfficeError("pictures must be PNG, JPEG, GIF or BMP")


def _runs(text: str) -> str:
    return "".join(
        ("<a:br/>" if index else "")
        + f'<a:r><a:rPr lang="zh-CN" altLang="en-US" dirty="0"/><a:t>{escape_text(line)}</a:t></a:r>'
        for index, line in enumerate(text.split("\n"))
    )


def _text_shape(
    shape_id: int,
    name: str,
    placeholder: Placeholder,
    paragraphs: str,
    box: tuple[int, int, int, int] | None = None,
) -> str:
    # An omitted type is "obj" (content); the layout's own attributes are copied as they are.
    attributes = (f' type="{placeholder.type}"' if placeholder.type != "obj" else "") + (
        f' idx="{placeholder.idx}"' if placeholder.idx else ""
    )
    position = (
        f'<a:xfrm><a:off x="{box[0]}" y="{box[1]}"/><a:ext cx="{box[2]}" cy="{box[3]}"/></a:xfrm>'
        if box
        else ""
    )
    return (
        f'<p:sp><p:nvSpPr><p:cNvPr id="{shape_id}" name="{escape_attr(name)}"/><p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr>'
        f"<p:nvPr><p:ph{attributes}/></p:nvPr></p:nvSpPr><p:spPr>{position}</p:spPr>"
        f"<p:txBody><a:bodyPr/><a:lstStyle/>{paragraphs}</p:txBody></p:sp>"
    )


def _bullets(items: list[Any], glyphs: bool = False) -> str:
    """Paragraphs at their levels; with glyphs, bullet characters of their own (a plain text
    box has none from the layout)."""
    out = []
    for item in items:
        if isinstance(item, (list, tuple)) and item:
            text, level = str(item[0]), int(item[1]) if len(item) > 1 else 0
        elif isinstance(item, dict):
            text, level = str(item.get("text", "")), int(item.get("level", 0))
        else:
            text, level = str(item), 0
        level = max(0, min(4, level))
        if glyphs:
            margin = 285750 * (level + 1)
            properties = (
                f'<a:pPr marL="{margin}" indent="-285750" lvl="{level}">'
                '<a:buFont typeface="Arial"/><a:buChar char="•"/></a:pPr>'
            )
        else:
            properties = f'<a:pPr lvl="{level}"/>' if level else ""
        out.append(f"<a:p>{properties}{_runs(text)}</a:p>")
    return "".join(out) or "<a:p/>"


def _free_text(shape_id: int, box: tuple[int, int, int, int], paragraphs: str) -> str:
    x, y, cx, cy = box
    return (
        f'<p:sp><p:nvSpPr><p:cNvPr id="{shape_id}" name="Text {shape_id}"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>'
        f'<p:spPr><a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/></p:spPr>'
        f'<p:txBody><a:bodyPr wrap="square"><a:normAutofit/></a:bodyPr><a:lstStyle/>{paragraphs}</p:txBody></p:sp>'
    )


def _picture(shape_id: int, rid: str, box: tuple[int, int, int, int], size: tuple[int, int]) -> str:
    x, y, cx, cy = box
    width, height = size
    scale = min(cx / width, cy / height)
    draw_w, draw_h = int(width * scale), int(height * scale)
    left, top = x + (cx - draw_w) // 2, y + (cy - draw_h) // 2
    return (
        f'<p:pic><p:nvPicPr><p:cNvPr id="{shape_id}" name="Picture {shape_id}"/><p:cNvPicPr><a:picLocks noChangeAspect="1"/></p:cNvPicPr><p:nvPr/></p:nvPicPr>'
        f'<p:blipFill><a:blip r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch></p:blipFill>'
        f'<p:spPr><a:xfrm><a:off x="{left}" y="{top}"/><a:ext cx="{draw_w}" cy="{draw_h}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr></p:pic>'
    )


def _drop_slides(package: Package) -> int:
    presentation = package.xml(_PRESENTATION)
    root = presentation.root
    listing = root.find(q(P, "sldIdLst"))
    removed = 0
    if listing is None:
        return 0
    for entry in list(listing):
        rid = entry.get(_REL_ID, "")
        target = next((t for r, _k, t in package.relationships(_PRESENTATION) if r == rid), None)
        listing.remove(entry)
        package.remove_relationship(_PRESENTATION, rid)
        if target:
            slide = package.resolve(_PRESENTATION, target)
            for _r, kind, notes_target in package.relationships(slide):
                if kind.endswith("/notesSlide"):
                    notes = package.resolve(slide, notes_target)
                    package.remove(notes)
                    package.remove(package.rels_name(notes))
                    package.drop_content_type(notes)
            package.remove(slide)
            package.remove(package.rels_name(slide))
            package.drop_content_type(slide)
        removed += 1
    # Sections and custom shows name the slides that are gone.
    for holder in (root.find(q(P, "extLst")),):
        if holder is None:
            continue
        for extension in list(holder):
            if extension.get("uri") == "{521415D9-36F7-43E2-AB2F-B90AF26B5E84}":
                holder.remove(extension)
    shows = root.find(q(P, "custShowLst"))
    if shows is not None:
        root.remove(shows)
    return removed


def _notes_master(package: Package) -> str | None:
    for _rid, kind, target in package.relationships(_PRESENTATION):
        if kind.endswith("/notesMaster"):
            return package.resolve(_PRESENTATION, target)
    return None


def _notes_xml(text: str) -> str:
    paragraphs = "".join(f"<a:p>{_runs(line)}</a:p>" for line in text.split("\n")) or "<a:p/>"
    return (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<p:notes {_NS}><p:cSld><p:spTree>'
        '<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr/>'
        '<p:sp><p:nvSpPr><p:cNvPr id="2" name="Slide Image 1"/><p:cNvSpPr><a:spLocks noGrp="1" noRot="1" noChangeAspect="1"/></p:cNvSpPr><p:nvPr><p:ph type="sldImg"/></p:nvPr></p:nvSpPr><p:spPr/></p:sp>'
        f'<p:sp><p:nvSpPr><p:cNvPr id="3" name="Notes Placeholder 2"/><p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr><p:nvPr><p:ph type="body" idx="1"/></p:nvPr></p:nvSpPr><p:spPr/><p:txBody><a:bodyPr/><a:lstStyle/>{paragraphs}</p:txBody></p:sp>'
        "</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:notes>"
    )


def build(
    template: bytes,
    slides: list[dict[str, Any]],
    pictures: dict[str, bytes],
    keep_template_slides: bool = False,
) -> tuple[bytes, dict[str, Any]]:
    """The deck: the template (its sample slides dropped unless kept) and the slides given."""
    package = open_template(template)
    available = layouts(package)
    dropped = 0 if keep_template_slides else _drop_slides(package)
    root = package.xml(_PRESENTATION).root
    listing = root.find(q(P, "sldIdLst"))
    if listing is None:
        listing = ET.Element(q(P, "sldIdLst"))
        masters = root.find(q(P, "sldMasterIdLst"))
        position = list(root).index(masters) + 1 if masters is not None else 0
        notes_list = root.find(q(P, "notesMasterIdLst"))
        if notes_list is not None:
            position = list(root).index(notes_list) + 1
        handout = root.find(q(P, "handoutMasterIdLst"))
        if handout is not None:
            position = list(root).index(handout) + 1
        root.insert(position, listing)
    next_id = max([int(entry.get("id", "255")) for entry in listing] + [255]) + 1
    number = 1
    while package.has(f"ppt/slides/slide{number}.xml"):
        number += 1
    media = 1
    notes_master = _notes_master(package)
    used: list[str] = []
    notes_skipped = 0
    charts = 0
    for slide in slides:
        kind = str(
            slide.get("layout")
            or ("title" if not slide.get("bullets") and slide.get("subtitle") else "content")
        )
        layout = choose_layout(available, kind)
        used.append(layout.name or layout.type)
        part = f"ppt/slides/slide{number}.xml"
        package.add_relationship(part, "slideLayout", "../" + layout.part.split("ppt/", 1)[1])
        shapes = []
        shape_id = 2
        title_placeholder = layout.find("title", "ctrTitle")
        if title_placeholder and slide.get("title"):
            shapes.append(
                _text_shape(
                    shape_id, "Title", title_placeholder, f"<a:p>{_runs(str(slide['title']))}</a:p>"
                )
            )
            shape_id += 1
        subtitle = layout.find("subTitle")
        if subtitle and slide.get("subtitle"):
            shapes.append(
                _text_shape(
                    shape_id, "Subtitle", subtitle, f"<a:p>{_runs(str(slide['subtitle']))}</a:p>"
                )
            )
            shape_id += 1
        body = layout.find("obj", "body")
        picture_name = slide.get("picture")
        if picture_name and picture_name not in pictures:
            raise OfficeError(f"the picture {picture_name} was not given")
        chart = slide.get("chart")
        if chart and picture_name:
            raise OfficeError("a slide takes a picture or a chart, not both")
        visual = bool(picture_name or chart)
        text_box = body.box if body else None
        picture_box = text_box
        bullets = slide.get("bullets") or []
        if not bullets and not subtitle and slide.get("subtitle"):
            bullets = [str(slide["subtitle"])]
        if visual and bullets and text_box:
            x, y, cx, cy = text_box
            text_box = (x, y, int(cx * 0.55), cy)
            picture_box = (x + int(cx * 0.58), y, int(cx * 0.42), cy)
        if body and bullets:
            shapes.append(
                _text_shape(
                    shape_id, "Content", body, _bullets(bullets), text_box if visual else None
                )
            )
            shape_id += 1
        elif bullets:
            # The layout has no text area: a text box where the content would go.
            box = _full_box(package)
            if visual:
                x, y, cx, cy = box
                box, picture_box = (
                    (x, y, int(cx * 0.55), cy),
                    (x + int(cx * 0.58), y, int(cx * 0.42), cy),
                )
            shapes.append(_free_text(shape_id, box, _bullets(bullets, glyphs=True)))
            shape_id += 1
        if picture_name:
            data = pictures[picture_name]
            extension = picture_name.rsplit(".", 1)[-1].lower()
            if extension not in _IMAGE_TYPES:
                raise OfficeError("pictures must be PNG, JPEG, GIF or BMP")
            while package.has(f"ppt/media/aw_image{media}.{extension}"):
                media += 1
            media_part = f"ppt/media/aw_image{media}.{extension}"
            package.set(media_part, data)
            package.default_type(extension, _IMAGE_TYPES[extension])
            rid = package.add_relationship(part, "image", f"../media/aw_image{media}.{extension}")
            box = picture_box or _full_box(package)
            shapes.append(_picture(shape_id, rid, box, _image_size(data)))
            shape_id += 1
        if chart:
            rid = _add_chart(package, part, chart)
            shapes.append(_chart_frame(shape_id, rid, picture_box or _full_box(package)))
            shape_id += 1
            charts += 1
        package.set(
            part,
            f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<p:sld {_NS}><p:cSld><p:spTree>'
            '<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
            '<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>'
            f"{''.join(shapes)}</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sld>",
        )
        package.content_type(part, _SLIDE_TYPE)
        if slide.get("notes"):
            if notes_master:
                notes_part = f"ppt/notesSlides/notesSlide{number}.xml"
                while package.has(notes_part):
                    notes_part = notes_part.replace(".xml", "a.xml")
                package.set(notes_part, _notes_xml(str(slide["notes"])))
                package.content_type(notes_part, _NOTES_TYPE)
                package.add_relationship(
                    notes_part, "notesMaster", "../" + notes_master.split("ppt/", 1)[1]
                )
                package.add_relationship(notes_part, "slide", f"../slides/slide{number}.xml")
                package.add_relationship(part, "notesSlide", "../" + notes_part.split("ppt/", 1)[1])
            else:
                notes_skipped += 1
        rid = package.add_relationship(_PRESENTATION, "slide", f"slides/slide{number}.xml")
        ET.SubElement(listing, q(P, "sldId"), {"id": str(next_id), _REL_ID: rid})
        next_id += 1
        number += 1
    details = {
        "slides": len(slides),
        "template_slides_dropped": dropped,
        "layouts_used": used,
        "layouts_available": [layout.name or layout.type for layout in available],
    }
    if notes_skipped:
        details["notes_skipped"] = f"{notes_skipped} (the template has no notes master)"
    if charts:
        details["charts"] = charts
    warnings = density_warnings(slides)
    if warnings:
        details["warnings"] = warnings
    return package.to_bytes(), details


_CHART_TYPE = "application/vnd.openxmlformats-officedocument.drawingml.chart+xml"
_WORKBOOK_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
_CHART_URI = "http://schemas.openxmlformats.org/drawingml/2006/chart"
_CHART_KINDS = {"column", "bar", "line", "pie"}


def _number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise OfficeError("chart values are numbers")
    try:
        return float(str(value).replace(",", "").rstrip("%"))
    except ValueError:
        raise OfficeError(f"chart values are numbers, not {value!r}") from None


def _add_chart(package: Package, slide_part: str, spec: dict[str, Any]) -> str:
    """A native PowerPoint chart (editable in PowerPoint, its data in an embedded workbook);
    returns the slide's relationship id to it."""
    kind = str(spec.get("type") or "column")
    if kind not in _CHART_KINDS:
        raise OfficeError(f"chart types: {', '.join(sorted(_CHART_KINDS))}")
    categories = [str(item) for item in spec.get("categories") or []]
    series = spec.get("series") or []
    if not isinstance(series, list) or not series or len(series) > 8:
        raise OfficeError("a chart has 1 to 8 series, each {name, values}")
    values = [[_number(item) for item in entry.get("values") or []] for entry in series]
    count = len(categories) or len(values[0])
    if not count or count > 60 or any(len(row) != count for row in values):
        raise OfficeError("each series needs one value per category (at most 60)")
    if not categories:
        categories = [str(index + 1) for index in range(count)]
    names = [str(entry.get("name") or f"系列{index + 1}") for index, entry in enumerate(series)]
    rows: list[list[Any]] = [["", *names]]
    rows += [[categories[r], *[values[s][r] for s in range(len(series))]] for r in range(count)]
    workbook, _ = xlsx.build(
        {
            "sheets": [
                {"name": "Sheet1", "rows": rows, "header": False, "borders": False, "freeze": ""}
            ]
        }
    )
    number = 1
    while package.has(f"ppt/charts/chart{number}.xml"):
        number += 1
    chart_part = f"ppt/charts/chart{number}.xml"
    embedded = f"Microsoft_Excel_Worksheet{number}.xlsx"
    package.set(f"ppt/embeddings/{embedded}", workbook)
    package.default_type("xlsx", _WORKBOOK_TYPE)
    external = package.add_relationship(chart_part, "package", f"../embeddings/{embedded}")
    last = count + 1
    layout_spec = {
        "type": kind,
        "title": spec.get("title") or "",
        "stacked": bool(spec.get("stacked")),
        "categories": f"A2:A{last}",
        "series": [
            {
                "name": name,
                "values": f"{xlsx.column_letter(index + 1)}2:{xlsx.column_letter(index + 1)}{last}",
            }
            for index, name in enumerate(names)
        ],
    }
    package.set(
        chart_part,
        xlsx.chart_xml(
            layout_spec,
            "Sheet1",
            caches=(categories, values),
            external=external,
            text_size=1400,
            theme_fonts=True,
        ),
    )
    package.content_type(chart_part, _CHART_TYPE)
    return package.add_relationship(slide_part, "chart", f"../charts/chart{number}.xml")


def _chart_frame(shape_id: int, rid: str, box: tuple[int, int, int, int]) -> str:
    x, y, cx, cy = box
    return (
        f'<p:graphicFrame><p:nvGraphicFramePr><p:cNvPr id="{shape_id}" name="Chart {shape_id}"/>'
        '<p:cNvGraphicFramePr><a:graphicFrameLocks noGrp="1"/></p:cNvGraphicFramePr><p:nvPr/></p:nvGraphicFramePr>'
        f'<p:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/></p:xfrm>'
        f'<a:graphic><a:graphicData uri="{_CHART_URI}"><c:chart xmlns:c="{_CHART_URI}" r:id="{rid}"/></a:graphicData></a:graphic>'
        "</p:graphicFrame>"
    )


def _bullet_text(item: Any) -> str:
    if isinstance(item, (list, tuple)) and item:
        return str(item[0])
    if isinstance(item, dict):
        return str(item.get("text", ""))
    return str(item)


def _width(text: str) -> float:
    """Reading width: a Chinese character counts 1, a Latin letter or digit about a half."""
    return sum(1.0 if ord(char) > 0x2E80 else 0.5 for char in text)


def density_warnings(slides: list[dict[str, Any]]) -> list[str]:
    """Slides likely to overflow or read as a wall of text: too many points, long points, long
    titles. (One claim per slide; the speaker notes carry the explanation.)"""
    out = []
    for number, slide in enumerate(slides, start=1):
        bullets = [_bullet_text(item) for item in slide.get("bullets") or []]
        title = str(slide.get("title") or "")
        problems = []
        if _width(title) > 28:
            problems.append(f"title is long ({int(_width(title))} characters; keep it under 28)")
        if len(bullets) > 6:
            problems.append(f"{len(bullets)} points (keep to 6 at most; split the slide)")
        long_points = [text for text in bullets if _width(text) > 40]
        if long_points:
            problems.append(
                f"{len(long_points)} point(s) over 40 characters (shorten; put the detail in the notes)"
            )
        total = sum(_width(text) for text in bullets)
        limit = 120 if slide.get("picture") else 180
        if total > limit:
            problems.append(f"{int(total)} characters of points (over {limit}; it will crowd)")
        if problems:
            out.append(f"slide {number} ({title[:20]}): " + "; ".join(problems))
    return out


def installed_templates(extra: list[tuple[str, Path]] | None = None) -> list[dict[str, str]]:
    """PowerPoint templates on this computer: the app's templates folder, the user's own
    (Documents\\Custom Office Templates, %APPDATA%\\Microsoft\\Templates) and the ones that come
    with Microsoft Office. Listed by id ("installed:<source>/<name>") with their names."""
    folders: list[tuple[str, Path]] = list(extra or [])
    home = Path(os.path.expanduser("~"))
    folders += [
        ("personal", home / "Documents" / "Custom Office Templates"),
        ("personal", home / "Documents" / "自定义 Office 模板"),
        ("personal", Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Templates"),
    ]
    for root in {os.environ.get("PROGRAMFILES", ""), os.environ.get("PROGRAMFILES(X86)", "")}:
        if root:
            base = Path(root) / "Microsoft Office"
            folders += [("office", base / "root" / "Templates"), ("office", base / "Templates")]
    seen: set[str] = set()
    out: list[dict[str, str]] = []
    for source, folder in folders:
        if not str(folder) or not folder.is_dir():
            continue
        try:
            found = sorted(
                path
                for path in folder.rglob("*")
                if path.suffix.lower() in {".potx", ".pptx"} and not path.name.startswith("~$")
            )
        except OSError:
            continue
        for path in found[:200]:
            key = str(path.resolve()).casefold()
            if key in seen:
                continue
            seen.add(key)
            relative = path.relative_to(folder).with_suffix("").as_posix()
            identifier = f"installed:{source}/{relative}"
            if any(item["id"] == identifier for item in out):
                continue
            out.append({"id": identifier, "name": path.stem, "source": source, "path": str(path)})
    return out


def installed_template(identifier: str, extra: list[tuple[str, Path]] | None = None) -> bytes:
    for item in installed_templates(extra):
        if item["id"] == identifier:
            return Path(item["path"]).read_bytes()
    raise OfficeError(f"no template {identifier}; office_read deck_templates lists them")


def _full_box(package: Package) -> tuple[int, int, int, int]:
    size = package.xml(_PRESENTATION).root.find(q(P, "sldSz"))
    width = int(size.get("cx", "12192000")) if size is not None else 12192000
    height = int(size.get("cy", "6858000")) if size is not None else 6858000
    return (width // 10, height // 5, width * 8 // 10, height * 7 // 10)


def describe(package: Package) -> list[dict[str, Any]]:
    """The template's layouts: name, kind and placeholders, for choosing."""
    return [
        {
            "name": layout.name,
            "type": layout.type,
            "placeholders": sorted({placeholder.type for placeholder in layout.placeholders}),
        }
        for layout in layouts(package)
    ]


def slide_texts(package: Package) -> list[str]:
    """The text of each slide (to check a built deck)."""
    root = package.xml(_PRESENTATION).root
    targets = {
        rid: package.resolve(_PRESENTATION, target)
        for rid, _kind, target in package.relationships(_PRESENTATION)
    }
    listing = root.find(q(P, "sldIdLst"))
    out = []
    for entry in listing if listing is not None else []:
        part = targets.get(entry.get(_REL_ID, ""))
        if part and package.has(part):
            texts = [text.text or "" for text in package.xml(part).root.iter(q(A, "t"))]
            out.append(" | ".join(text for text in texts if text))
    return out


__all__ = [
    "Layout",
    "build",
    "choose_layout",
    "describe",
    "layouts",
    "open_template",
    "slide_texts",
]
