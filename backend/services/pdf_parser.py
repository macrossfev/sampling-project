"""Parse contract PDF files to extract structured data using pdfplumber.

Supports OCR fallback for scanned PDFs via PyMuPDF + pytesseract.
"""

import logging
import re
from collections import OrderedDict
from io import BytesIO

import pdfplumber

logger = logging.getLogger(__name__)

_OCR_TOTAL_THRESHOLD = 50
_OCR_CJK_MIN_RATIO = 0.05


def _ocr_available() -> bool:
    try:
        import fitz
        import pytesseract
        return True
    except ImportError:
        return False


def _ocr_pdf_pages(file_bytes: bytes) -> str:
    import fitz
    import pytesseract
    from PIL import Image

    doc = fitz.open(stream=file_bytes, filetype="pdf")
    all_text = ""
    for page_num, page in enumerate(doc):
        mat = fitz.Matrix(300 / 72, 300 / 72)
        pix = page.get_pixmap(matrix=mat)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        try:
            text = pytesseract.image_to_string(img, lang="chi_sim+eng")
        except Exception as e:
            logger.warning("OCR failed on page %d: %s", page_num + 1, e)
            text = ""
        all_text += text + "\n"
    doc.close()
    return all_text.strip()


def parse_contract_pdf(file_bytes: bytes) -> dict:
    result = {
        "contract_no": None,
        "company_name": None,
        "year": None,
        "start_date": None,
        "end_date": None,
        "total_amount": None,
        "raw_text": "",
        "water_plants": [],
        "ocr_used": False,
    }

    try:
        pdf = pdfplumber.open(BytesIO(file_bytes))
    except Exception:
        result["raw_text"] = "[无法打开PDF文件]"
        return result

    all_text = ""
    for page in pdf.pages:
        try:
            text = page.extract_text() or ""
            all_text += text + "\n"
        except Exception:
            pass

    all_tables = []
    for page in pdf.pages:
        try:
            tables = page.extract_tables() or []
            all_tables.extend(tables)
        except Exception:
            pass

    pdf.close()

    # OCR fallback
    stripped = re.sub(r'\s+', '', all_text)
    cjk_count = len(re.findall(r'[\u4e00-\u9fff]', all_text))
    total_len = len(stripped)
    cjk_ratio = cjk_count / total_len if total_len > 0 else 0

    need_ocr = (
        total_len < _OCR_TOTAL_THRESHOLD
        or (total_len > 0 and cjk_ratio < _OCR_CJK_MIN_RATIO)
    )

    if need_ocr:
        if _ocr_available():
            logger.info(
                "pdfplumber text insufficient (chars=%d, cjk=%d, ratio=%.3f), "
                "falling back to OCR",
                total_len, cjk_count, cjk_ratio,
            )
            try:
                ocr_text = _ocr_pdf_pages(file_bytes)
                if ocr_text:
                    all_text = ocr_text
                    result["ocr_used"] = True
            except Exception as e:
                logger.error("OCR fallback failed: %s", e)
        else:
            logger.warning(
                "PDF appears to need OCR but dependencies "
                "(PyMuPDF, pytesseract) are not installed"
            )

    result["raw_text"] = all_text.strip()
    _parse_basic_fields(all_text, result)
    result["water_plants"] = _parse_fee_tables(all_tables)

    return result


def _parse_basic_fields(text: str, result: dict):
    for pattern in [
        r'合同编号[：:\s]*([A-Za-z0-9/\-_]+)',
        r'编号[：:\s]*([A-Za-z0-9/\-_]+)',
        r'([A-Z]{2,}[/\-][A-Z]{2,}[/\-][A-Z]{2,}[/\-]\d{4}[/\-]\d+)',
    ]:
        m = re.search(pattern, text)
        if m:
            result["contract_no"] = m.group(1).strip()
            break

    for pattern in [
        r'甲方[（(]委托方[）)][：:\s]*(.+)',
        r'委托方[（(]甲方[）)][：:\s]*(.+)',
        r'甲方[：:\s]*(.+)',
        r'委托方[：:\s]*(.+)',
    ]:
        m = re.search(pattern, text)
        if m:
            name = m.group(1).strip()
            name = re.split(r'[\n\r]', name)[0].strip()
            name = re.split(r'\s{2,}|乙方|签章|地址|电话', name)[0].strip()
            if name:
                result["company_name"] = name
                break

    if not result["company_name"]:
        for pattern in [
            r'[：:]\s*([\u4e00-\u9fff]{2,}(?:有限责任公司|有限公司|集团公司))',
            r'([\u4e00-\u9fff]{4,}(?:有限责任公司|有限公司|集团公司))',
        ]:
            matches = re.findall(pattern, text)
            if matches:
                result["company_name"] = matches[0].strip()
                break

    date_matches = re.findall(r'(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日', text)
    if len(date_matches) >= 2:
        period_text = ""
        for kw in ['有效期', '期限', '合同期', '服务期']:
            idx = text.find(kw)
            if idx >= 0:
                period_text = text[idx:idx + 200]
                break
        if period_text:
            period_dates = re.findall(
                r'(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日', period_text
            )
            if len(period_dates) >= 2:
                date_matches = period_dates
        try:
            y1, m1, d1 = date_matches[0]
            result["start_date"] = f"{y1}-{int(m1):02d}-{int(d1):02d}"
            y2, m2, d2 = date_matches[1]
            result["end_date"] = f"{y2}-{int(m2):02d}-{int(d2):02d}"
            result["year"] = int(y1)
        except (ValueError, IndexError):
            pass
    elif len(date_matches) == 1:
        try:
            y1, m1, d1 = date_matches[0]
            result["start_date"] = f"{y1}-{int(m1):02d}-{int(d1):02d}"
            result["year"] = int(y1)
        except (ValueError, IndexError):
            pass

    # Total amount: all amounts stored in 元
    for pattern in [
        r'合同总金额[^0-9]*?([\d.]+)\s*万元',
        r'总金额[^0-9]*?([\d.]+)\s*万元',
        r'合同金额[^0-9]*?([\d.]+)\s*万元',
        r'总价[^0-9]*?([\d.]+)\s*万元',
        r'合计[^0-9]*?([\d.]+)\s*万元',
    ]:
        m = re.search(pattern, text)
        if m:
            try:
                result["total_amount"] = round(float(m.group(1)) * 10000, 2)
            except ValueError:
                pass
            break

    if result["total_amount"] is None:
        for pattern in [
            r'合同总金额[^0-9]*?([\d,]+\.?\d*)\s*元',
            r'总金额[^0-9]*?([\d,]+\.?\d*)\s*元',
            r'合同金额[^0-9]*?([\d,]+\.?\d*)\s*元',
            r'总价[^0-9]*?([\d,]+\.?\d*)\s*元',
            r'合计[^0-9]*?([\d,]+\.?\d*)\s*元',
        ]:
            m = re.search(pattern, text)
            if m:
                try:
                    result["total_amount"] = round(float(m.group(1).replace(',', '')), 2)
                except ValueError:
                    pass
                break

    if result["total_amount"] is None:
        m = re.search(r'总金额[^0-9]*?([\d,]+\.?\d*)', text)
        if m:
            try:
                result["total_amount"] = round(float(m.group(1).replace(',', '')), 2)
            except ValueError:
                pass


def _parse_fee_tables(tables: list) -> list:
    if not tables:
        return []

    plants: OrderedDict[str, dict] = OrderedDict()

    for table in tables:
        if not table or len(table) < 2:
            continue

        header_idx = _find_header_row(table)
        if header_idx is None:
            continue

        header = [_clean_cell(c) for c in table[header_idx]]
        col_map = _build_column_map(header)

        if "water_plant" not in col_map and "sample_type" not in col_map:
            continue

        last_plant_name = None

        for row in table[header_idx + 1:]:
            if not row or all(_clean_cell(c) == "" for c in row):
                continue

            cells = [_clean_cell(c) for c in row]

            row_text = "".join(cells)
            if any(kw in row_text for kw in ["合计", "总计", "总金额", "备注"]):
                continue

            wp_name = _get_col(cells, col_map, "water_plant")
            if wp_name:
                last_plant_name = wp_name
            elif last_plant_name:
                wp_name = last_plant_name
            else:
                wp_name = "未知水厂"

            sample_type = _normalize_sample_type(_get_col(cells, col_map, "sample_type"))
            detection_project = _normalize_detection_project(_get_col(cells, col_map, "detection_project"))
            detection_standard = _get_col(cells, col_map, "detection_standard")
            frequency_raw = _get_col(cells, col_map, "frequency")
            unit_price = _get_col_float(cells, col_map, "unit_price")
            annual_count = _get_col_int(cells, col_map, "annual_count")
            subtotal = round(annual_count * unit_price, 2) if annual_count and unit_price else None

            if not sample_type and not detection_project and unit_price == 0:
                continue

            freq_type, freq_value = _parse_frequency(frequency_raw)

            # Auto-detect detection level
            detect_text = (detection_project or "") + " " + (sample_type or "")
            detection_level = None
            if any(kw in detect_text for kw in ["全分析", "全项", "97项", "106项"]):
                detection_level = "全分析"
            elif any(kw in detect_text for kw in ["常规", "42项", "43项", "9项", "7项"]):
                detection_level = "常规"

            if wp_name not in plants:
                plants[wp_name] = {"name": wp_name, "scale": "", "items": []}

            plants[wp_name]["items"].append({
                "sample_type": sample_type or None,
                "detection_project": detection_project or None,
                "detection_standard": detection_standard or None,
                "frequency_type": freq_type,
                "frequency_value": freq_value,
                "unit_price": unit_price if unit_price else None,
                "annual_count": annual_count if annual_count else None,
                "subtotal": subtotal if subtotal else None,
                "detection_level": detection_level,
            })

    return list(plants.values())


def _normalize_sample_type(s: str) -> str:
    if not s:
        return s
    if "管网末梢" in s:
        return "管网水"
    if re.search(r'水源水[（(]原水[）)]', s):
        return "水源水"
    return s


def _normalize_detection_project(s: str) -> str:
    if not s:
        return s
    m = re.search(r'(\d+)\s*项', s)
    if m:
        return f"{m.group(1)}项"
    return s


def _find_header_row(table: list) -> int | None:
    keywords = ["水厂", "样品", "检测", "频率", "频次", "单价", "小计", "项目", "标准"]
    for i, row in enumerate(table):
        if not row:
            continue
        row_text = "".join(_clean_cell(c) for c in row)
        matches = sum(1 for kw in keywords if kw in row_text)
        if matches >= 3:
            return i
    return None


def _build_column_map(header: list) -> dict:
    col_map = {}
    for i, h in enumerate(header):
        if not h:
            continue
        h_lower = h.strip()
        if any(kw in h_lower for kw in ["水厂", "厂名"]):
            col_map["water_plant"] = i
        elif "样品" in h_lower or "样本" in h_lower or "类别" in h_lower:
            col_map["sample_type"] = i
        elif "项目" in h_lower and "检测" in h_lower:
            col_map["detection_project"] = i
        elif "项目" in h_lower and "detection_project" not in col_map:
            col_map["detection_project"] = i
        elif "标准" in h_lower:
            col_map["detection_standard"] = i
        elif "频" in h_lower and "次" in h_lower:
            col_map["frequency"] = i
        elif "频率" in h_lower or "频次" in h_lower:
            col_map["frequency"] = i
        elif "单价" in h_lower or "价格" in h_lower:
            col_map["unit_price"] = i
        elif ("年" in h_lower and "次" in h_lower) or "年检" in h_lower:
            col_map["annual_count"] = i
        elif "小计" in h_lower or "金额" in h_lower:
            col_map["subtotal"] = i
    return col_map


def _parse_frequency(raw: str) -> tuple:
    if not raw:
        return (None, 1)
    raw = raw.strip()
    for pat, typ in [
        (r'每月\s*(\d+)\s*次', "月"), (r'每季度?\s*(\d+)\s*次', "季"),
        (r'每半年\s*(\d+)\s*次', "半年"), (r'每年\s*(\d+)\s*次', "年"),
        (r'(\d+)\s*次\s*/\s*月', "月"), (r'(\d+)\s*次\s*/\s*季', "季"),
        (r'(\d+)\s*次\s*/\s*半年', "半年"), (r'(\d+)\s*次\s*/\s*年', "年"),
    ]:
        m = re.search(pat, raw)
        if m:
            return (typ, int(m.group(1)))
    m = re.search(r'(\d+)', raw)
    if m:
        return (None, int(m.group(1)))
    return (None, 1)


def _clean_cell(cell) -> str:
    if cell is None:
        return ""
    s = str(cell).strip()
    s = re.sub(r'[\n\r]+', ' ', s)
    return s


def _get_col(cells, col_map, key, default=""):
    idx = col_map.get(key)
    if idx is not None and idx < len(cells):
        return cells[idx]
    return default


def _get_col_float(cells, col_map, key, default=0.0):
    val = _get_col(cells, col_map, key)
    if not val:
        return default
    try:
        return float(re.sub(r'[,，元万]', '', val))
    except (ValueError, TypeError):
        return default


def _get_col_int(cells, col_map, key, default=0):
    val = _get_col(cells, col_map, key)
    if not val:
        return default
    try:
        return int(float(re.sub(r'[,，次]', '', val)))
    except (ValueError, TypeError):
        return default
