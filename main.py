import process
import os
import shutil
from PyPDF2 import PdfReader, PdfWriter
from precipy.main import render_file
from parameters import REPORT_YEAR, REPORT_ARCHIVES_DIR, DATA_FOLDER

render_file('config.json', [process], storages=[])

reader = PdfReader('output_files/report_template.pdf')
writer = PdfWriter()
[writer.add_page(reader.pages[i]) for i in range(0, len(reader.pages))]

archive_dir = REPORT_ARCHIVES_DIR / str(REPORT_YEAR)
if not os.path.isdir(archive_dir):
    os.mkdir(archive_dir)
if not os.path.isdir(archive_dir / 'data'):
    os.mkdir(archive_dir / 'data')

with open(archive_dir / f'OA Report {REPORT_YEAR}.pdf', 'wb') as f:
    writer.write(f)

for f in [child for child in DATA_FOLDER.iterdir() if child.is_file()]:
    shutil.copy(f, archive_dir / 'data')