import mimetypes
import os
from typing import Union

from django.http import FileResponse, HttpResponseNotFound
from django.shortcuts import render, get_object_or_404


# Create your views here.
from .models import BitsDigitalContent


def bits_digital_file(request, token: str) -> Union[FileResponse, HttpResponseNotFound]:
    """Return the direct download link to content if given token is still valid."""

    qs = BitsDigitalContent.objects.prefetch_related("line__order__user")
    digital_content = get_object_or_404(qs, token=token)  # type: BitsDigitalContent

    digital_content.content_file.open()
    opened_file = digital_content.content_file.file
    filename = os.path.basename(digital_content.content_file.name)
    file_expr = 'filename="{}"'.format(filename)

    content_type = mimetypes.guess_type(str(filename))[0]
    response = FileResponse(opened_file)
    response["Content-Length"] = digital_content.content_file.size

    response["Content-Type"] = str(content_type)
    response["Content-Disposition"] = "attachment; {}".format(file_expr)

    return response
