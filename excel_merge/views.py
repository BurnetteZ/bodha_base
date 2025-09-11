from django.shortcuts import render

# Create your views here.
from io import BytesIO
import os
from zipfile import BadZipFile
import logging

import pandas as pd
from openpyxl.utils.exceptions import InvalidFileException
from xlrd.biffh import XLRDError
from django.conf import settings
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import render
from django.utils import timezone

logger = logging.getLogger(__name__)

MAX_FILES = 100


def _save_uploaded_file(user, uploaded_file):
    """Save uploaded file to MEDIA_ROOT/excel_merge/<username>/.

    If a file with the same name already exists, a timestamp is appended to
    the filename before saving. The uploaded file's pointer is reset after
    saving so it can be read again.
    """
    username = getattr(user, "username", "anonymous")
    user_dir = os.path.join(settings.MEDIA_ROOT, "excel_merge", username)
    os.makedirs(user_dir, exist_ok=True)

    filename = uploaded_file.name
    file_path = os.path.join(user_dir, filename)
    if os.path.exists(file_path):
        name, ext = os.path.splitext(filename)
        timestamp = timezone.now().strftime("%Y%m%d%H%M%S")
        filename = f"{name}_{timestamp}{ext}"
        file_path = os.path.join(user_dir, filename)

    with open(file_path, "wb+") as destination:
        for chunk in uploaded_file.chunks():
            destination.write(chunk)
    uploaded_file.seek(0)
    return file_path


def upload(request):
    if request.method == 'POST':
        files = request.FILES.getlist('files')
        logger.info("Received %d files for merging", len(files))
        if not files:
            return HttpResponseBadRequest('未上传文件')
        if len(files) > MAX_FILES:
            return HttpResponseBadRequest(f'一次最多提交 {MAX_FILES} 个Excel文件')

        data = {}
        column_order = []
        for f in files:
            _save_uploaded_file(request.user, f)
            logger.info("Processing file %s", f.name)
            try:
                df = pd.read_excel(f, engine="openpyxl")
            except (ValueError, BadZipFile, KeyError, InvalidFileException, XLRDError):
                logger.exception("Invalid Excel file: %s", f.name)
                return HttpResponseBadRequest(
                    f"文件 {f.name} 不是有效的Excel文件，请检查后重新上传"
                )
            df.columns = [str(c).strip() for c in df.columns]
            for col in df.columns:
                if col not in data:
                    data[col] = []
                    column_order.append(col)
                values = df[col].dropna().tolist()
                data[col].extend(values)

        max_len = max((len(v) for v in data.values()), default=0)
        for col, values in data.items():
            if len(values) < max_len:
                values.extend([''] * (max_len - len(values)))

        merged_df = pd.DataFrame({col: data[col] for col in column_order})
        output = BytesIO()
        merged_df.to_excel(output, index=False)
        output.seek(0)
        logger.info("Merging completed, returning file")
        response = HttpResponse(
            output.read(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = 'attachment; filename=merged.xlsx'
        return response

    return render(request, 'excel_merge/upload.html')
