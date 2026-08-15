"""占位符渲染的单元测试（纯逻辑，无需 NoneBot 环境）。"""

from datetime import datetime

from helpers import load_module

ph = load_module("placeholders")

NOW = datetime(2026, 5, 31, 10, 30, 0)  # 周日


def test_date_default():
    assert ph.render_placeholders("{date}", NOW) == "2026-05-31"


def test_date_custom_format():
    assert ph.render_placeholders("{date:%Y年%m月%d日}", NOW) == "2026年05月31日"


def test_time_default():
    assert ph.render_placeholders("现在 {time}", NOW) == "现在 10:30:00"


def test_time_custom_format():
    assert ph.render_placeholders("{time:%H:%M}", NOW) == "10:30"


def test_datetime_default():
    assert ph.render_placeholders("{datetime}", NOW) == "2026-05-31 10:30:00"


def test_datetime_custom_format():
    assert (
        ph.render_placeholders("{datetime:%Y/%m/%d %H:%M}", NOW)
        == "2026/05/31 10:30"
    )


def test_weekday():
    assert ph.render_placeholders("{weekday}", NOW) == "周日"
    assert ph.render_placeholders("{weekday}", datetime(2026, 6, 1, 9, 0)) == "周一"


def test_days_until_future():
    assert ph.render_placeholders("{days_until:2026-06-07}", NOW) == "7"


def test_days_until_today():
    assert ph.render_placeholders("{days_until:2026-05-31}", NOW) == "0"


def test_days_until_past():
    assert ph.render_placeholders("{days_until:2026-05-01}", NOW) == "-30"


def test_days_until_with_time():
    # 距 2026-06-01 09:00 不足一天 => 1
    assert ph.render_placeholders("{days_until:2026-06-01 09:00}", NOW) == "1"
    # 精确到秒，同一时刻 => 0
    assert ph.render_placeholders("{days_until:2026-05-31 10:30:00}", NOW) == "0"
    # 超过一天之前 => -1
    assert ph.render_placeholders("{days_until:2026-05-30 10:00:00}", NOW) == "-1"


def test_days_until_invalid_kept():
    assert (
        ph.render_placeholders("{days_until:不是日期}", NOW)
        == "{days_until:不是日期}"
    )


def test_days_until_missing_arg_kept():
    assert ph.render_placeholders("{days_until}", NOW) == "{days_until}"


def test_days_until_cn_future():
    assert ph.render_placeholders("{days_until_cn:2026-06-07}", NOW) == "还有 7 天"


def test_days_until_cn_today():
    assert ph.render_placeholders("{days_until_cn:2026-05-31}", NOW) == "就是今天"


def test_days_until_cn_past():
    assert ph.render_placeholders("{days_until_cn:2026-05-01}", NOW) == "已过 30 天"


def test_days_until_cn_invalid_kept():
    assert ph.render_placeholders("{days_until_cn:x}", NOW) == "{days_until_cn:x}"


def test_image_url():
    assert (
        ph.render_placeholders("{image:https://example.com/a.png}", NOW)
        == "[CQ:image,file=https://example.com/a.png]"
    )


def test_image_absolute_path():
    assert (
        ph.render_placeholders(r"{image:E:\Pictures\a.png}", NOW)
        == r"[CQ:image,file=E:\Pictures\a.png]"
    )


def test_image_base64():
    assert (
        ph.render_placeholders("{image:base64://aGVsbG8=}", NOW)
        == "[CQ:image,file=base64://aGVsbG8=]"
    )


def test_image_bare_filename(tmp_path):
    images_dir = tmp_path / "images"
    expected = (images_dir / "a.png").as_posix()
    assert (
        ph.render_placeholders("{image:a.png}", NOW, images_dir=images_dir)
        == f"[CQ:image,file={expected}]"
    )


def test_image_bare_filename_without_dir():
    # 未提供 images_dir 时裸文件名原样返回
    assert ph.render_placeholders("{image:a.png}", NOW) == "[CQ:image,file=a.png]"


def test_image_escapes_special_chars():
    assert (
        ph.render_placeholders("{image:https://ex.com/a.png?x=1&y=2}", NOW)
        == "[CQ:image,file=https://ex.com/a.png?x=1&amp;y=2]"
    )


def test_image_missing_arg_kept():
    assert ph.render_placeholders("{image}", NOW) == "{image}"
    assert ph.render_placeholders("{image:}", NOW) == "{image:}"


def test_cq_code_text_passthrough():
    text = "早上好 [CQ:image,file=abc.png]"
    assert ph.render_placeholders(text, NOW) == text


def test_image_with_text(tmp_path):
    images_dir = tmp_path / "images"
    expected = (images_dir / "x.png").as_posix()
    assert (
        ph.render_placeholders("早安 {image:x.png}", NOW, images_dir=images_dir)
        == f"早安 [CQ:image,file={expected}]"
    )


def test_unknown_placeholder_kept():
    assert ph.render_placeholders("你好 {foo} 世界", NOW) == "你好 {foo} 世界"


def test_combined():
    assert (
        ph.render_placeholders(
            "今天是{date} {weekday}，{days_until_cn:2026-06-07}", NOW
        )
        == "今天是2026-05-31 周日，还有 7 天"
    )


def test_no_placeholder():
    assert ph.render_placeholders("纯文本", NOW) == "纯文本"


def test_empty_text():
    assert ph.render_placeholders("", NOW) == ""


def test_now_default():
    # 不注入 now 时应使用真实当前时间，结果应为 10 位日期
    out = ph.render_placeholders("{date}")
    assert len(out) == 10 and out[4] == "-"
