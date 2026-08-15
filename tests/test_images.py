"""图片保存逻辑单测。"""

import base64
from hashlib import md5

import pytest
from nonebot.adapters.onebot.v11 import MessageSegment

from helpers import load_module

img = load_module("images")


def test_save_image_bytes_dedup(tmp_path):
    data = b"fake-image-bytes"
    name1 = img.save_image_bytes(data, tmp_path, ".png")
    name2 = img.save_image_bytes(data, tmp_path, ".png")
    assert name1 == name2 == md5(data).hexdigest() + ".png"
    assert (tmp_path / name1).read_bytes() == data
    assert len(list(tmp_path.iterdir())) == 1


def test_guess_ext():
    assert img.guess_ext("a.PNG", None) == ".png"
    assert img.guess_ext("https://x.com/a.jpg?t=1", None) == ".jpg"
    assert img.guess_ext("https://x.com/0", "image/jpeg") == ".jpg"
    assert img.guess_ext("https://x.com/0", None) == ".png"


@pytest.mark.asyncio
async def test_save_base64_segment(tmp_path):
    data = b"base64-image"
    seg = MessageSegment.image(file=f"base64://{base64.b64encode(data).decode()}")
    name = await img.save_image_segment(seg, tmp_path)
    assert name == md5(data).hexdigest() + ".png"
    assert (tmp_path / name).read_bytes() == data


@pytest.mark.asyncio
async def test_save_file_segment(tmp_path):
    src = tmp_path / "src.jpg"
    src.write_bytes(b"jpg-data")
    seg = MessageSegment.image(file=f"file:///{src.as_posix()}")
    name = await img.save_image_segment(seg, tmp_path)
    assert name == md5(b"jpg-data").hexdigest() + ".jpg"


@pytest.mark.asyncio
async def test_save_url_segment(tmp_path, monkeypatch):
    async def fake_download(url):
        return b"url-image", "image/jpeg"

    monkeypatch.setattr(img, "download_image", fake_download)
    seg = MessageSegment("image", {"file": "x", "url": "https://example.com/0"})
    name = await img.save_image_segment(seg, tmp_path)
    assert name == md5(b"url-image").hexdigest() + ".jpg"


@pytest.mark.asyncio
async def test_save_url_failure(tmp_path, monkeypatch):
    async def fake_download(url):
        return None

    monkeypatch.setattr(img, "download_image", fake_download)
    seg = MessageSegment("image", {"file": "x", "url": "https://example.com/0"})
    assert await img.save_image_segment(seg, tmp_path) is None


@pytest.mark.asyncio
async def test_save_no_source(tmp_path):
    seg = MessageSegment("image", {"file": "x"})
    assert await img.save_image_segment(seg, tmp_path) is None
