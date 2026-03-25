from io import BytesIO
from zipfile import ZipFile

from openpyxl import Workbook
from sqlalchemy import select

from app.db.models import SimpleTabulationCode
from app.services.importer import SimpleTabulationImporter


def build_test_zip() -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "SimpleTabulation-ICD-11-MMS-en"
    sheet.append(
        [
            "Foundation URI",
            "Linearization URI",
            "Code",
            "BlockId",
            "Title",
            "ClassKind",
            "DepthInKind",
            "IsResidual",
            "ChapterNo",
            "BrowserLink",
            "isLeaf",
            "Primary tabulation",
            "Grouping1",
            "Grouping2",
            "Grouping3",
            "Grouping4",
            "Grouping5",
        ]
    )
    sheet.append(
        [
            "foundation://1",
            "linear://1",
            "AB12",
            "",
            "- Alpha condition",
            "category",
            1,
            False,
            "01",
            "",
            True,
            True,
            "BlockL1-AB12",
            "",
            "",
            "",
            "",
        ]
    )
    sheet.append(
        [
            "foundation://2",
            "linear://2",
            "AB12.0",
            "",
            "- - Alpha subtype",
            "category",
            2,
            False,
            "01",
            "",
            True,
            True,
            "BlockL1-AB12",
            "",
            "",
            "",
            "",
        ]
    )
    sheet.append(
        [
            "foundation://3",
            "linear://3",
            "XT9",
            "",
            "- Theta extension",
            "category",
            1,
            False,
            "X",
            "",
            True,
            True,
            "BlockL1-XT9",
            "",
            "",
            "",
            "",
        ]
    )

    workbook_buffer = BytesIO()
    workbook.save(workbook_buffer)

    zip_buffer = BytesIO()
    with ZipFile(zip_buffer, "w") as archive:
        archive.writestr("SimpleTabulation-ICD-11-MMS-en.xlsx", workbook_buffer.getvalue())

    return zip_buffer.getvalue()


def test_importer_loads_reference_rows_and_preserves_sort_order(db_session):
    zip_bytes = build_test_zip()
    summary = SimpleTabulationImporter(db_session).import_from_zip_bytes(
        zip_bytes=zip_bytes,
        source_name="memory://test.zip",
        replace=True,
    )

    imported_rows = db_session.scalars(
        select(SimpleTabulationCode).order_by(SimpleTabulationCode.sort_key)
    ).all()

    assert summary.imported_rows == 3
    assert [row.code for row in imported_rows] == ["AB12", "AB12.0", "XT9"]
    assert imported_rows[1].parent_code == "AB12"
    assert imported_rows[2].is_extension is True

