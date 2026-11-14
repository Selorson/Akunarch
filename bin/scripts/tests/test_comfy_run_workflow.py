"""Phần thuần của bộ chạy workflow ComfyUI (không cần máy chủ): đổi tham số node, gom file đầu ra từ history,
dựng gói multipart tải ảnh."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from comfy_run_workflow import apply_sets, collect_outputs, multipart  # noqa: E402

WF = {"122": {"class_type": "LoadImage", "inputs": {"image": "x.png"}},
      "316": {"class_type": "PrimitiveBoolean", "inputs": {"value": False}},
      "6": {"class_type": "CLIPTextEncode", "inputs": {"text": "", "clip": ["30", 1]}}}


class ComfyRunnerTest(unittest.TestCase):
    def test_apply_sets_parses_json_values_and_keeps_links(self):
        wf = apply_sets(WF, ["316.value=true", '6.text="bronze gothic tracery, ánh đồng"', "122.image=a b.png"])
        self.assertIs(wf["316"]["inputs"]["value"], True)
        self.assertEqual(wf["6"]["inputs"]["text"], "bronze gothic tracery, ánh đồng")
        self.assertEqual(wf["122"]["inputs"]["image"], "a b.png")      # không phải JSON → giữ chuỗi
        self.assertEqual(wf["6"]["inputs"]["clip"], ["30", 1])
        self.assertIs(WF["316"]["inputs"]["value"], False)             # không sửa bản gốc

    def test_apply_sets_unknown_node_is_clear_error(self):
        with self.assertRaisesRegex(KeyError, "999"):
            apply_sets(WF, ["999.value=1"])

    def test_collect_outputs_finds_images_and_3d(self):
        hist = {"outputs": {
            "9": {"images": [{"filename": "a_00001_.png", "subfolder": "", "type": "output"}]},
            "164": {"images": [{"filename": "p.png", "subfolder": "", "type": "temp"}]},
            "322": {"3d": [{"filename": "m_00001_.glb", "subfolder": "3d", "type": "output"}], "text": ["ok"]}}}
        got = collect_outputs(hist)
        self.assertEqual([(f["filename"], f["subfolder"]) for f in got], [("a_00001_.png", ""), ("m_00001_.glb", "3d")])

    def test_multipart_contains_file_and_boundary(self):
        body, ctype = multipart("image", "ảnh.png", b"\x89PNG", {"overwrite": "true"})
        self.assertIn("multipart/form-data; boundary=", ctype)
        boundary = ctype.split("boundary=")[1].encode()
        self.assertIn(boundary, body)
        self.assertIn(b"\x89PNG", body)
        self.assertIn('filename="ảnh.png"'.encode(), body)
        self.assertIn(b'name="overwrite"', body)


if __name__ == "__main__":
    unittest.main()
